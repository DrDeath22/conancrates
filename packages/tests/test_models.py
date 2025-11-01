"""
Tests for ConanCrates models
"""
from django.test import TestCase
from django.contrib.auth.models import User
from packages.models import Package, PackageVersion, BinaryPackage, Dependency, Topic


class PackageModelTests(TestCase):
    """Tests for the Package model"""

    def setUp(self):
        self.package = Package.objects.create(
            name='test-package',
            description='A test package',
            homepage='https://example.com',
            license='MIT',
            author='Test Author',
            topics='testing, demo'
        )

    def test_package_creation(self):
        """Test that a package can be created"""
        self.assertEqual(self.package.name, 'test-package')
        self.assertEqual(self.package.description, 'A test package')
        self.assertEqual(self.package.license, 'MIT')

    def test_package_str_representation(self):
        """Test string representation of package"""
        self.assertEqual(str(self.package), 'test-package')

    def test_get_topics_list(self):
        """Test that topics are split into a list"""
        topics = self.package.get_topics_list()
        self.assertEqual(len(topics), 2)
        self.assertIn('testing', topics)
        self.assertIn('demo', topics)

    def test_download_count_default(self):
        """Test that download count defaults to 0"""
        self.assertEqual(self.package.download_count, 0)

    def test_package_unique_name(self):
        """Test that package names must be unique"""
        with self.assertRaises(Exception):
            Package.objects.create(name='test-package')


class PackageVersionModelTests(TestCase):
    """Tests for the PackageVersion model"""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.package = Package.objects.create(
            name='test-package',
            description='A test package'
        )
        self.version = PackageVersion.objects.create(
            package=self.package,
            version='1.0.0',
            recipe_revision='abc123',
            uploaded_by=self.user
        )

    def test_version_creation(self):
        """Test that a version can be created"""
        self.assertEqual(self.version.version, '1.0.0')
        self.assertEqual(self.version.package, self.package)
        self.assertEqual(self.version.uploaded_by, self.user)

    def test_version_str_representation(self):
        """Test string representation of version"""
        self.assertEqual(str(self.version), 'test-package/1.0.0')

    def test_full_name_method(self):
        """Test full_name method"""
        self.assertEqual(self.version.full_name(), 'test-package/1.0.0')

    def test_unique_together_constraint(self):
        """Test that package+version must be unique"""
        with self.assertRaises(Exception):
            PackageVersion.objects.create(
                package=self.package,
                version='1.0.0'
            )

    def test_multiple_versions_same_package(self):
        """Test that a package can have multiple versions"""
        version2 = PackageVersion.objects.create(
            package=self.package,
            version='2.0.0'
        )
        self.assertEqual(self.package.versions.count(), 2)

    def test_latest_version(self):
        """Test latest_version method on Package"""
        version2 = PackageVersion.objects.create(
            package=self.package,
            version='2.0.0'
        )
        latest = self.package.latest_version()
        self.assertEqual(latest.version, '2.0.0')


class BinaryPackageModelTests(TestCase):
    """Tests for the BinaryPackage model"""

    def setUp(self):
        self.package = Package.objects.create(name='test-package')
        self.version = PackageVersion.objects.create(
            package=self.package,
            version='1.0.0'
        )
        self.binary = BinaryPackage.objects.create(
            package_version=self.version,
            package_id='abc123def456',
            os='Linux',
            arch='x86_64',
            compiler='gcc',
            compiler_version='11',
            build_type='Release',
            file_size=1024 * 1024  # 1 MB
        )

    def test_binary_creation(self):
        """Test that a binary package can be created"""
        self.assertEqual(self.binary.os, 'Linux')
        self.assertEqual(self.binary.arch, 'x86_64')
        self.assertEqual(self.binary.compiler, 'gcc')

    def test_get_config_string(self):
        """Test configuration string generation"""
        config = self.binary.get_config_string()
        self.assertIn('Linux', config)
        self.assertIn('x86_64', config)
        self.assertIn('gcc 11', config)
        self.assertIn('Release', config)

    def test_file_size(self):
        """Test file size storage"""
        self.assertEqual(self.binary.file_size, 1024 * 1024)

    def test_download_count_default(self):
        """Test download count defaults to 0"""
        self.assertEqual(self.binary.download_count, 0)

    def test_options_json_field(self):
        """Test that options can store JSON data"""
        self.binary.options = {'shared': True, 'fPIC': True}
        self.binary.save()

        binary = BinaryPackage.objects.get(pk=self.binary.pk)
        self.assertEqual(binary.options['shared'], True)
        self.assertEqual(binary.options['fPIC'], True)


class DependencyModelTests(TestCase):
    """Tests for the Dependency model"""

    def setUp(self):
        self.package1 = Package.objects.create(name='package1')
        self.package2 = Package.objects.create(name='package2')
        self.version1 = PackageVersion.objects.create(
            package=self.package1,
            version='1.0.0'
        )

    def test_dependency_creation(self):
        """Test that a dependency can be created"""
        dep = Dependency.objects.create(
            package_version=self.version1,
            requires_package=self.package2,
            version_requirement='>=1.0.0',
            dependency_type='requires'
        )
        self.assertEqual(dep.package_version, self.version1)
        self.assertEqual(dep.requires_package, self.package2)
        self.assertEqual(dep.version_requirement, '>=1.0.0')

    def test_dependency_types(self):
        """Test different dependency types"""
        dep1 = Dependency.objects.create(
            package_version=self.version1,
            requires_package=self.package2,
            version_requirement='>=1.0.0',
            dependency_type='requires'
        )

        # Create version for package2 to test build_requires
        version2 = PackageVersion.objects.create(
            package=self.package2,
            version='1.0.0'
        )
        package3 = Package.objects.create(name='package3')

        dep2 = Dependency.objects.create(
            package_version=self.version1,
            requires_package=package3,
            version_requirement='>=2.0.0',
            dependency_type='build_requires'
        )

        self.assertEqual(dep1.dependency_type, 'requires')
        self.assertEqual(dep2.dependency_type, 'build_requires')

    def test_dependency_str_representation(self):
        """Test string representation of dependency"""
        dep = Dependency.objects.create(
            package_version=self.version1,
            requires_package=self.package2,
            version_requirement='>=1.0.0'
        )
        expected = 'package1/1.0.0 requires package2 >=1.0.0'
        self.assertEqual(str(dep), expected)


class TopicModelTests(TestCase):
    """Tests for the Topic model"""

    def setUp(self):
        self.topic = Topic.objects.create(
            name='Testing',
            slug='testing',
            description='Testing libraries and frameworks'
        )
        self.package1 = Package.objects.create(name='test-lib-1')
        self.package2 = Package.objects.create(name='test-lib-2')

    def test_topic_creation(self):
        """Test that a topic can be created"""
        self.assertEqual(self.topic.name, 'Testing')
        self.assertEqual(self.topic.slug, 'testing')

    def test_topic_str_representation(self):
        """Test string representation of topic"""
        self.assertEqual(str(self.topic), 'Testing')

    def test_topic_packages_relationship(self):
        """Test many-to-many relationship with packages"""
        self.topic.packages.add(self.package1)
        self.topic.packages.add(self.package2)

        self.assertEqual(self.topic.packages.count(), 2)
        self.assertIn(self.package1, self.topic.packages.all())
        self.assertIn(self.package2, self.topic.packages.all())

    def test_package_count_method(self):
        """Test package_count method"""
        self.assertEqual(self.topic.package_count(), 0)

        self.topic.packages.add(self.package1)
        self.assertEqual(self.topic.package_count(), 1)

        self.topic.packages.add(self.package2)
        self.assertEqual(self.topic.package_count(), 2)
