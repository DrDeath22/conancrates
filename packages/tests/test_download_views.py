"""
Tests for download views and Conan integration
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from packages.models import Package, PackageVersion, BinaryPackage, Dependency
from unittest.mock import patch, MagicMock
import json


class DownloadBinaryTests(TestCase):
    """Tests for direct binary downloads"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass')

        # Create test package
        self.package = Package.objects.create(
            name='zlib',
            description='Compression library',
            license='Zlib'
        )
        self.version = PackageVersion.objects.create(
            package=self.package,
            version='1.2.13',
            uploaded_by=self.user
        )
        self.binary = BinaryPackage.objects.create(
            package_version=self.version,
            package_id='test123',
            os='Linux',
            arch='x86_64',
            compiler='gcc',
            compiler_version='11',
            build_type='Release',
            file_size=1024 * 1024
        )

    def test_download_binary_success(self):
        """Test successful binary download"""
        url = reverse('packages:download_binary', args=['zlib', '1.2.13', 'test123'])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/plain')
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertIn('zlib-1.2.13-test123.tar.gz', response['Content-Disposition'])

    def test_download_binary_increments_count(self):
        """Test that download increments download count"""
        initial_count = self.binary.download_count
        package_initial_count = self.package.download_count

        url = reverse('packages:download_binary', args=['zlib', '1.2.13', 'test123'])
        self.client.get(url)

        self.binary.refresh_from_db()
        self.package.refresh_from_db()

        self.assertEqual(self.binary.download_count, initial_count + 1)
        self.assertEqual(self.package.download_count, package_initial_count + 1)

    def test_download_binary_not_found(self):
        """Test 404 for non-existent binary"""
        url = reverse('packages:download_binary', args=['zlib', '1.2.13', 'nonexistent'])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


class DownloadManifestTests(TestCase):
    """Tests for manifest downloads"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass')

        # Create test package
        self.package = Package.objects.create(
            name='zlib',
            description='Compression library',
            license='Zlib',
            author='Test Author',
            homepage='https://zlib.net'
        )
        self.version = PackageVersion.objects.create(
            package=self.package,
            version='1.2.13',
            uploaded_by=self.user
        )
        self.binary = BinaryPackage.objects.create(
            package_version=self.version,
            package_id='test123',
            os='Linux',
            arch='x86_64',
            compiler='gcc',
            compiler_version='11',
            build_type='Release',
            file_size=1024 * 1024,
            sha256='test_checksum'
        )

    def test_download_manifest_success(self):
        """Test manifest download"""
        url = reverse('packages:download_manifest', args=['zlib', '1.2.13'])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertIn('attachment', response['Content-Disposition'])

        data = json.loads(response.content)
        self.assertEqual(data['name'], 'zlib')
        self.assertEqual(data['version'], '1.2.13')
        self.assertEqual(data['license'], 'Zlib')
        self.assertIn('binaries', data)
        self.assertIn('dependencies', data)

    def test_manifest_includes_binaries(self):
        """Test that manifest includes binary information"""
        url = reverse('packages:download_manifest', args=['zlib', '1.2.13'])
        response = self.client.get(url)

        data = json.loads(response.content)
        self.assertEqual(len(data['binaries']), 1)

        binary = data['binaries'][0]
        self.assertEqual(binary['id'], 'test123')
        self.assertEqual(binary['os'], 'Linux')
        self.assertEqual(binary['arch'], 'x86_64')
        self.assertEqual(binary['checksum'], 'test_checksum')
        self.assertIn('download_url', binary)


class DownloadScriptTests(TestCase):
    """Tests for download script endpoint"""

    def setUp(self):
        self.client = Client()

    def test_download_script_success(self):
        """Test download script generation"""
        url = reverse('packages:download_script')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/plain')
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertIn('download_conan_package.sh', response['Content-Disposition'])

        script_content = response.content.decode('utf-8')
        self.assertIn('#!/bin/bash', script_content)
        self.assertIn('ConanCrates Package Downloader', script_content)


class BundlePreviewTests(TestCase):
    """Tests for bundle preview endpoint with Conan integration"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass')

        # Create test packages
        self.package = Package.objects.create(
            name='boost',
            description='C++ libraries'
        )
        self.version = PackageVersion.objects.create(
            package=self.package,
            version='1.81.0',
            uploaded_by=self.user
        )
        self.binary = BinaryPackage.objects.create(
            package_version=self.version,
            package_id='boost123',
            os='Linux',
            arch='x86_64',
            compiler='gcc',
            compiler_version='11',
            build_type='Release',
            file_size=5 * 1024 * 1024
        )

    @patch('packages.views.download_views.check_conan_available')
    def test_bundle_preview_conan_unavailable(self, mock_check):
        """Test bundle preview when Conan is not available"""
        mock_check.return_value = False

        url = reverse('packages:bundle_preview', args=['boost', '1.81.0'])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 503)
        data = json.loads(response.content)

        self.assertFalse(data['conan_available'])
        self.assertEqual(data['resolution_method'], 'unavailable')
        self.assertIn('error', data)
        self.assertIn('Conan is not available', data['error'])

    @patch('packages.views.download_views.get_conan_version')
    @patch('packages.views.download_views.resolve_dependencies')
    @patch('packages.views.download_views.check_conan_available')
    def test_bundle_preview_conan_success(self, mock_check, mock_resolve, mock_version):
        """Test successful bundle preview with Conan"""
        mock_check.return_value = True
        mock_version.return_value = "Conan version 2.0.0"
        mock_resolve.return_value = {
            'success': True,
            'packages': [
                {
                    'name': 'boost',
                    'version': '1.81.0',
                    'package_id': 'abc123'
                }
            ]
        }

        url = reverse('packages:bundle_preview', args=['boost', '1.81.0'])
        response = self.client.get(url, {
            'os': 'Linux',
            'arch': 'x86_64',
            'compiler': 'gcc',
            'compiler_version': '11',
            'build_type': 'Release'
        })

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertTrue(data['conan_available'])
        self.assertEqual(data['resolution_method'], 'conan')
        self.assertEqual(data['conan_version'], "Conan version 2.0.0")
        self.assertIn('files', data)
        self.assertEqual(len(data['files']), 1)

    @patch('packages.views.download_views.get_conan_version')
    @patch('packages.views.download_views.resolve_dependencies')
    @patch('packages.views.download_views.check_conan_available')
    def test_bundle_preview_conan_resolution_failed(self, mock_check, mock_resolve, mock_version):
        """Test bundle preview when Conan resolution fails"""
        mock_check.return_value = True
        mock_version.return_value = "Conan version 2.0.0"
        mock_resolve.return_value = {
            'success': False,
            'error': 'Package not found in remote'
        }

        url = reverse('packages:bundle_preview', args=['boost', '1.81.0'])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 500)
        data = json.loads(response.content)

        self.assertEqual(data['resolution_method'], 'error')
        self.assertIn('error', data)
        self.assertIn('Package not found', data['error'])

    @patch('packages.views.download_views.get_conan_version')
    @patch('packages.views.download_views.resolve_dependencies')
    @patch('packages.views.download_views.check_conan_available')
    def test_bundle_preview_includes_platform_info(self, mock_check, mock_resolve, mock_version):
        """Test that bundle preview includes platform information"""
        mock_check.return_value = True
        mock_version.return_value = "Conan version 2.0.0"
        mock_resolve.return_value = {
            'success': True,
            'packages': []
        }

        url = reverse('packages:bundle_preview', args=['boost', '1.81.0'])
        response = self.client.get(url, {
            'os': 'Windows',
            'arch': 'x86_64',
            'compiler': 'msvc',
            'compiler_version': '19.29',
            'build_type': 'Debug'
        })

        data = json.loads(response.content)
        platform = data['platform']

        self.assertEqual(platform['os'], 'Windows')
        self.assertEqual(platform['arch'], 'x86_64')
        self.assertEqual(platform['compiler'], 'msvc')
        self.assertEqual(platform['compiler_version'], '19.29')
        self.assertEqual(platform['build_type'], 'Debug')


class DownloadBundleTests(TestCase):
    """Tests for bundle download endpoint with Conan integration"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass')

        # Create test package
        self.package = Package.objects.create(
            name='zlib',
            description='Compression library'
        )
        self.version = PackageVersion.objects.create(
            package=self.package,
            version='1.2.13',
            uploaded_by=self.user
        )
        self.binary = BinaryPackage.objects.create(
            package_version=self.version,
            package_id='zlib123',
            os='Linux',
            arch='x86_64',
            compiler='gcc',
            compiler_version='11',
            build_type='Release',
            file_size=1024 * 1024
        )

    @patch('packages.views.download_views.check_conan_available')
    def test_bundle_download_conan_unavailable(self, mock_check):
        """Test bundle download fails when Conan is not available"""
        mock_check.return_value = False

        url = reverse('packages:download_bundle', args=['zlib', '1.2.13'])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 503)
        data = json.loads(response.content)

        self.assertFalse(data['conan_available'])
        self.assertEqual(data['resolution_method'], 'unavailable')
        self.assertIn('error', data)

    @patch('packages.views.download_views.get_conan_version')
    @patch('packages.views.download_views.resolve_dependencies')
    @patch('packages.views.download_views.check_conan_available')
    def test_bundle_download_conan_success(self, mock_check, mock_resolve, mock_version):
        """Test successful bundle download with Conan"""
        mock_check.return_value = True
        mock_version.return_value = "Conan version 2.0.0"
        mock_resolve.return_value = {
            'success': True,
            'packages': [
                {
                    'name': 'zlib',
                    'version': '1.2.13',
                    'package_id': 'zlib123'
                }
            ]
        }

        url = reverse('packages:download_bundle', args=['zlib', '1.2.13'])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/zip')
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertIn('zlib-1.2.13-bundle.zip', response['Content-Disposition'])

    @patch('packages.views.download_views.get_conan_version')
    @patch('packages.views.download_views.resolve_dependencies')
    @patch('packages.views.download_views.check_conan_available')
    def test_bundle_download_conan_resolution_failed(self, mock_check, mock_resolve, mock_version):
        """Test bundle download fails when Conan resolution fails"""
        mock_check.return_value = True
        mock_version.return_value = "Conan version 2.0.0"
        mock_resolve.return_value = {
            'success': False,
            'error': 'Dependency conflict detected'
        }

        url = reverse('packages:download_bundle', args=['zlib', '1.2.13'])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 500)
        data = json.loads(response.content)

        self.assertEqual(data['resolution_method'], 'error')
        self.assertIn('error', data)
        self.assertIn('Dependency conflict', data['error'])

    def test_bundle_download_package_not_found(self):
        """Test 404 when package doesn't exist"""
        url = reverse('packages:download_bundle', args=['nonexistent', '1.0.0'])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


class ConanWrapperIntegrationTests(TestCase):
    """Tests for Conan wrapper error handling"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass')

        self.package = Package.objects.create(name='testpkg')
        self.version = PackageVersion.objects.create(
            package=self.package,
            version='1.0.0',
            uploaded_by=self.user
        )

    @patch('packages.views.download_views.resolve_dependencies')
    @patch('packages.views.download_views.check_conan_available')
    def test_conan_error_exception(self, mock_check, mock_resolve):
        """Test handling of ConanError exception"""
        from packages.conan_wrapper import ConanError

        mock_check.return_value = True
        mock_resolve.side_effect = ConanError("Conan subprocess failed")

        url = reverse('packages:bundle_preview', args=['testpkg', '1.0.0'])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 500)
        data = json.loads(response.content)

        self.assertEqual(data['resolution_method'], 'error')
        self.assertIn('Conan subprocess failed', data['error'])
