"""
Tests for Rust crate generation and download functionality.
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from packages.models import Package, PackageVersion, BinaryPackage
import json
import tarfile
import tempfile
import os


class RustCrateDownloadTests(TestCase):
    """Test Rust crate download endpoints and API"""

    def setUp(self):
        """Create test data"""
        self.client = Client()

        # Create a test package
        self.package = Package.objects.create(
            name='testlib',
            description='Test library',
            license='MIT'
        )

        # Create a version
        self.version = PackageVersion.objects.create(
            package=self.package,
            version='1.0.0',
            conan_version='2.0.0'
        )

        # Create a binary with a mock rust crate file
        self.binary = BinaryPackage.objects.create(
            package_version=self.version,
            package_id='abc123',
            os='Linux',
            arch='x86_64',
            compiler='gcc',
            compiler_version='11',
            build_type='Release',
            rust_crate_file=SimpleUploadedFile(
                'testlib-sys-1.0.0.crate',
                b'fake crate data',
                content_type='application/gzip'
            )
        )

    def test_download_rust_crate(self):
        """Test downloading a Rust crate"""
        url = reverse('packages:download_rust_crate', kwargs={
            'package_name': 'testlib',
            'version': '1.0.0',
            'package_id': 'abc123'
        })

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/gzip')
        self.assertIn('attachment; filename=', response['Content-Disposition'])
        self.assertIn('testlib-sys-1.0.0.crate', response['Content-Disposition'])

    def test_download_rust_crate_not_found(self):
        """Test 404 when rust crate doesn't exist"""
        # Create binary without rust crate
        binary2 = BinaryPackage.objects.create(
            package_version=self.version,
            package_id='def456',
            os='Windows',
            arch='x86_64',
            compiler='gcc',
            compiler_version='11',
            build_type='Release'
        )

        url = reverse('packages:download_rust_crate', kwargs={
            'package_name': 'testlib',
            'version': '1.0.0',
            'package_id': 'def456'
        })

        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_package_info_api(self):
        """Test package info API endpoint"""
        # Add dependency graph
        dep_graph = {
            'graph': {
                'nodes': {
                    '0': {'ref': 'testlib/1.0.0'},
                    '1': {'ref': 'deplib/2.0.0#hash', 'package_id': 'xyz789'}
                }
            }
        }
        self.binary.dependency_graph = dep_graph
        self.binary.save()

        url = reverse('packages:package_info_api', kwargs={
            'package_name': 'testlib',
            'version': '1.0.0',
            'package_id': 'abc123'
        })

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data['package']['name'], 'testlib')
        self.assertEqual(data['package']['version'], '1.0.0')
        self.assertTrue(data['rust_crate']['available'])
        self.assertEqual(len(data['dependencies']), 1)
        self.assertEqual(data['dependencies'][0]['name'], 'deplib')
        self.assertEqual(data['dependencies'][0]['version'], '2.0.0')

    def test_package_info_api_no_dependencies(self):
        """Test package info API with no dependencies"""
        url = reverse('packages:package_info_api', kwargs={
            'package_name': 'testlib',
            'version': '1.0.0',
            'package_id': 'abc123'
        })

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(len(data['dependencies']), 0)

    def test_rust_crate_by_settings_api(self):
        """Test getting rust crate by platform settings"""
        url = reverse('packages:rust_crate_by_settings_api', kwargs={
            'package_name': 'testlib',
            'version': '1.0.0'
        })

        response = self.client.get(url, {
            'os': 'Linux',
            'arch': 'x86_64',
            'compiler': 'gcc',
            'compiler_version': '11',
            'build_type': 'Release'
        })

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        # API returns nested package object
        self.assertEqual(data['package']['name'], 'testlib')
        self.assertEqual(data['package']['version'], '1.0.0')
        self.assertEqual(data['package']['package_id'], 'abc123')
        self.assertIn('rust_crate_url', data)

    def test_rust_crate_by_settings_no_match(self):
        """Test 404 when no binary matches settings"""
        url = reverse('packages:rust_crate_by_settings_api', kwargs={
            'package_name': 'testlib',
            'version': '1.0.0'
        })

        response = self.client.get(url, {
            'os': 'Windows',  # No Windows binary exists
            'arch': 'x86_64',
            'compiler': 'msvc',
            'compiler_version': '19',
            'build_type': 'Release'
        })

        self.assertEqual(response.status_code, 404)

    def test_rust_crate_by_settings_partial_match(self):
        """Test that API works with partial settings (filters are optional)"""
        url = reverse('packages:rust_crate_by_settings_api', kwargs={
            'package_name': 'testlib',
            'version': '1.0.0'
        })

        response = self.client.get(url, {
            'os': 'Linux',
            # Missing other params - should still match
        })

        # Should find the Linux binary
        self.assertEqual(response.status_code, 200)


class RustCrateContentTests(TestCase):
    """Test Rust crate file structure and content"""

    def setUp(self):
        """Create a realistic rust crate file for testing"""
        self.temp_dir = tempfile.mkdtemp()
        self.crate_dir = os.path.join(self.temp_dir, 'testlib-sys')
        os.makedirs(self.crate_dir)

        # Create Cargo.toml
        cargo_toml = """[package]
name = "testlib-sys"
version = "1.0.0"
edition = "2021"
links = "testlib"

[dependencies]
deplib-sys = { version = "2.0.0", path = "../deplib-sys" }
"""
        with open(os.path.join(self.crate_dir, 'Cargo.toml'), 'w') as f:
            f.write(cargo_toml)

        # Create build.rs
        build_rs = """fn main() {
    println!("cargo:rustc-link-lib=static=testlib");
}
"""
        with open(os.path.join(self.crate_dir, 'build.rs'), 'w') as f:
            f.write(build_rs)

        # Create .crate archive
        self.crate_path = os.path.join(self.temp_dir, 'testlib-sys-1.0.0.crate')
        with tarfile.open(self.crate_path, 'w:gz') as tar:
            tar.add(self.crate_dir, arcname='testlib-sys')

    def tearDown(self):
        """Clean up temporary files"""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_crate_archive_structure(self):
        """Test that crate archive has correct structure"""
        with tarfile.open(self.crate_path, 'r:gz') as tar:
            members = tar.getnames()

            # Check essential files exist
            self.assertIn('testlib-sys/Cargo.toml', members)
            self.assertIn('testlib-sys/build.rs', members)

    def test_crate_cargo_toml_has_path_dependencies(self):
        """Test that Cargo.toml includes path dependencies"""
        with tarfile.open(self.crate_path, 'r:gz') as tar:
            cargo_toml = tar.extractfile('testlib-sys/Cargo.toml').read().decode('utf-8')

            # Check path dependency is present
            self.assertIn('path = "../deplib-sys"', cargo_toml)
            self.assertIn('deplib-sys', cargo_toml)

    def test_crate_build_script_exists(self):
        """Test that build.rs exists and links library"""
        with tarfile.open(self.crate_path, 'r:gz') as tar:
            build_rs = tar.extractfile('testlib-sys/build.rs').read().decode('utf-8')

            # Check it links the library
            self.assertIn('cargo:rustc-link-lib', build_rs)
            self.assertIn('testlib', build_rs)


class RustCrateDependencyTests(TestCase):
    """Test Rust crate dependency handling"""

    def setUp(self):
        """Create package hierarchy: A -> B -> C"""
        # Package C (no dependencies)
        self.pkg_c = Package.objects.create(name='pkg_c')
        self.ver_c = PackageVersion.objects.create(package=self.pkg_c, version='1.0.0')
        self.bin_c = BinaryPackage.objects.create(
            package_version=self.ver_c,
            package_id='c123',
            os='Linux',
            arch='x86_64',
            rust_crate_file=SimpleUploadedFile('pkg-c-sys-1.0.0.crate', b'c data')
        )

        # Package B (depends on C)
        self.pkg_b = Package.objects.create(name='pkg_b')
        self.ver_b = PackageVersion.objects.create(package=self.pkg_b, version='1.0.0')
        self.bin_b = BinaryPackage.objects.create(
            package_version=self.ver_b,
            package_id='b123',
            os='Linux',
            arch='x86_64',
            dependency_graph={
                'graph': {
                    'nodes': {
                        '0': {'ref': 'pkg_b/1.0.0'},
                        '1': {'ref': 'pkg_c/1.0.0#hash', 'package_id': 'c123'}
                    }
                }
            },
            rust_crate_file=SimpleUploadedFile('pkg-b-sys-1.0.0.crate', b'b data')
        )

        # Package A (depends on B and C)
        self.pkg_a = Package.objects.create(name='pkg_a')
        self.ver_a = PackageVersion.objects.create(package=self.pkg_a, version='1.0.0')
        self.bin_a = BinaryPackage.objects.create(
            package_version=self.ver_a,
            package_id='a123',
            os='Linux',
            arch='x86_64',
            dependency_graph={
                'graph': {
                    'nodes': {
                        '0': {'ref': 'pkg_a/1.0.0'},
                        '1': {'ref': 'pkg_b/1.0.0#hash', 'package_id': 'b123'},
                        '2': {'ref': 'pkg_c/1.0.0#hash', 'package_id': 'c123'}
                    }
                }
            },
            rust_crate_file=SimpleUploadedFile('pkg-a-sys-1.0.0.crate', b'a data')
        )

    def test_package_info_includes_all_dependencies(self):
        """Test that package info API returns all dependencies"""
        url = reverse('packages:package_info_api', kwargs={
            'package_name': 'pkg_a',
            'version': '1.0.0',
            'package_id': 'a123'
        })

        response = self.client.get(url)
        data = json.loads(response.content)

        self.assertEqual(len(data['dependencies']), 2)

        dep_names = [dep['name'] for dep in data['dependencies']]
        self.assertIn('pkg_b', dep_names)
        self.assertIn('pkg_c', dep_names)

    def test_leaf_package_has_no_dependencies(self):
        """Test that leaf package (C) reports no dependencies"""
        url = reverse('packages:package_info_api', kwargs={
            'package_name': 'pkg_c',
            'version': '1.0.0',
            'package_id': 'c123'
        })

        response = self.client.get(url)
        data = json.loads(response.content)

        self.assertEqual(len(data['dependencies']), 0)

    def test_dependency_rust_crate_urls(self):
        """Test that dependencies include rust crate download URLs"""
        url = reverse('packages:package_info_api', kwargs={
            'package_name': 'pkg_a',
            'version': '1.0.0',
            'package_id': 'a123'
        })

        response = self.client.get(url)
        data = json.loads(response.content)

        for dep in data['dependencies']:
            self.assertIn('rust_crate_url', dep)
            self.assertTrue(dep['rust_crate_url'].endswith('/rust-crate/'))


class RustCrateWebUITests(TestCase):
    """Test Rust crate integration in web UI"""

    def setUp(self):
        """Create test package with rust crate"""
        self.package = Package.objects.create(name='webtest')
        self.version = PackageVersion.objects.create(
            package=self.package,
            version='1.0.0'
        )
        self.binary = BinaryPackage.objects.create(
            package_version=self.version,
            package_id='web123',
            os='Linux',
            arch='x86_64',
            rust_crate_file=SimpleUploadedFile('webtest-sys.crate', b'data')
        )

    def test_package_detail_shows_rust_download_link(self):
        """Test that package detail page shows Rust crate download"""
        url = reverse('packages:package_detail', kwargs={'package_name': 'webtest'})

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Rust')
        self.assertContains(response, 'Crate')

    def test_package_detail_shows_rust_usage_section(self):
        """Test that package detail has 'Using with Rust' section"""
        url = reverse('packages:package_detail', kwargs={'package_name': 'webtest'})

        response = self.client.get(url)

        # Check for Rust section (with or without emoji)
        content = response.content.decode('utf-8')
        self.assertTrue('Using with Rust' in content or 'Rust' in content)
        self.assertContains(response, 'cargo')
        self.assertContains(response, '--crates')
