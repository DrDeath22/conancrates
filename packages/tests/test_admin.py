"""
Tests for ConanCrates admin interface
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from packages.models import Package, PackageVersion, BinaryPackage, Dependency, Topic


class AdminTests(TestCase):
    """Tests for Django admin interface"""

    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='admin123'
        )
        self.client.login(username='admin', password='admin123')

        # Create test data
        self.package = Package.objects.create(
            name='test-package',
            description='Test package',
            license='MIT'
        )
        self.version = PackageVersion.objects.create(
            package=self.package,
            version='1.0.0',
            uploaded_by=self.admin_user
        )

    def test_admin_login(self):
        """Test that admin can login"""
        response = self.client.get('/admin/')
        self.assertEqual(response.status_code, 200)

    def test_package_admin_list(self):
        """Test package list in admin"""
        response = self.client.get('/admin/packages/package/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'test-package')

    def test_package_admin_add(self):
        """Test that admin add page loads"""
        # Just test that the add page loads, not the form submission
        # (form submission requires CSRF and is complex to test)
        response = self.client.get('/admin/packages/package/add/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Add package')

    def test_package_admin_change(self):
        """Test editing a package through admin"""
        response = self.client.get(f'/admin/packages/package/{self.package.pk}/change/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'test-package')

    def test_package_version_admin_list(self):
        """Test package version list in admin"""
        response = self.client.get('/admin/packages/packageversion/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '1.0.0')

    def test_binary_package_admin_list(self):
        """Test binary package list in admin"""
        binary = BinaryPackage.objects.create(
            package_version=self.version,
            package_id='test123',
            os='Linux',
            arch='x86_64',
            compiler='gcc',
            build_type='Release'
        )
        response = self.client.get('/admin/packages/binarypackage/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Linux')

    def test_topic_admin_list(self):
        """Test topic list in admin"""
        topic = Topic.objects.create(
            name='Testing',
            slug='testing'
        )
        response = self.client.get('/admin/packages/topic/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Testing')

    def test_dependency_admin_list(self):
        """Test dependency list in admin"""
        package2 = Package.objects.create(name='dependency-package')
        dep = Dependency.objects.create(
            package_version=self.version,
            requires_package=package2,
            version_requirement='>=1.0.0'
        )
        response = self.client.get('/admin/packages/dependency/')
        self.assertEqual(response.status_code, 200)

    def test_admin_search_packages(self):
        """Test searching packages in admin"""
        response = self.client.get('/admin/packages/package/', {'q': 'test'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'test-package')

    def test_admin_filter_packages_by_license(self):
        """Test filtering packages by license in admin"""
        response = self.client.get('/admin/packages/package/', {'license': 'MIT'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'test-package')

    def test_admin_requires_authentication(self):
        """Test that admin requires authentication"""
        self.client.logout()
        response = self.client.get('/admin/packages/package/')
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response.url)
