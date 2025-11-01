"""
Tests for ConanCrates views
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from packages.models import Package, PackageVersion, BinaryPackage, Dependency, Topic


class PackageViewTests(TestCase):
    """Tests for package-related views"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass')

        # Create test packages
        self.package1 = Package.objects.create(
            name='zlib',
            description='Compression library',
            license='Zlib',
            author='Test Author'
        )
        self.package2 = Package.objects.create(
            name='boost',
            description='C++ libraries',
            license='BSL-1.0',
            author='Boost Community'
        )

        # Create versions
        self.version1 = PackageVersion.objects.create(
            package=self.package1,
            version='1.2.13',
            uploaded_by=self.user
        )
        self.version2 = PackageVersion.objects.create(
            package=self.package2,
            version='1.81.0',
            uploaded_by=self.user
        )

        # Create binaries
        self.binary = BinaryPackage.objects.create(
            package_version=self.version1,
            package_id='test123',
            os='Linux',
            arch='x86_64',
            compiler='gcc',
            compiler_version='11',
            build_type='Release',
            file_size=1024 * 1024
        )

    def test_index_view(self):
        """Test the homepage view"""
        response = self.client.get(reverse('packages:index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ConanCrates')
        self.assertContains(response, 'Total Packages')

    def test_index_view_shows_statistics(self):
        """Test that index shows correct statistics"""
        response = self.client.get(reverse('packages:index'))
        self.assertContains(response, '2')  # 2 packages
        self.assertContains(response, 'Total Packages')

    def test_package_list_view(self):
        """Test the package list view"""
        response = self.client.get(reverse('packages:package_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'zlib')
        self.assertContains(response, 'boost')

    def test_package_list_search(self):
        """Test search functionality"""
        response = self.client.get(reverse('packages:package_list'), {'q': 'Compression'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'zlib')
        # Boost description is "C++ libraries" so shouldn't match "Compression"

    def test_package_list_filter_by_license(self):
        """Test filtering by license"""
        response = self.client.get(reverse('packages:package_list'), {'license': 'Zlib'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'zlib')

    def test_package_list_ordering(self):
        """Test ordering functionality"""
        response = self.client.get(reverse('packages:package_list'), {'order': 'name'})
        self.assertEqual(response.status_code, 200)

    def test_package_detail_view(self):
        """Test package detail view"""
        response = self.client.get(reverse('packages:package_detail', args=['zlib']))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'zlib')
        self.assertContains(response, '1.2.13')
        self.assertContains(response, 'Compression library')

    def test_package_detail_shows_binaries(self):
        """Test that package detail shows binary packages"""
        response = self.client.get(reverse('packages:package_detail', args=['zlib']))
        self.assertContains(response, 'Linux')
        self.assertContains(response, 'x86_64')
        self.assertContains(response, 'gcc')

    def test_package_detail_version_selection(self):
        """Test selecting specific version"""
        # Create another version
        version2 = PackageVersion.objects.create(
            package=self.package1,
            version='1.2.12',
            uploaded_by=self.user
        )

        response = self.client.get(
            reverse('packages:package_detail', args=['zlib']),
            {'version': '1.2.12'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '1.2.12')

    def test_package_detail_shows_dependencies(self):
        """Test that dependencies are shown"""
        # Create dependency
        Dependency.objects.create(
            package_version=self.version2,
            requires_package=self.package1,
            version_requirement='>=1.2.11'
        )

        response = self.client.get(reverse('packages:package_detail', args=['boost']))
        self.assertContains(response, 'zlib')
        # HTML escapes >= to &gt;=
        self.assertContains(response, '&gt;=1.2.11')

    def test_package_not_found(self):
        """Test 404 for non-existent package"""
        response = self.client.get(reverse('packages:package_detail', args=['nonexistent']))
        self.assertEqual(response.status_code, 404)


class TopicViewTests(TestCase):
    """Tests for topic-related views"""

    def setUp(self):
        self.client = Client()

        # Create topics
        self.topic1 = Topic.objects.create(
            name='Compression',
            slug='compression',
            description='Data compression libraries'
        )
        self.topic2 = Topic.objects.create(
            name='Testing',
            slug='testing',
            description='Testing frameworks'
        )

        # Create packages
        self.package1 = Package.objects.create(name='zlib')
        self.package2 = Package.objects.create(name='gtest')

        # Add packages to topics
        self.topic1.packages.add(self.package1)
        self.topic2.packages.add(self.package2)

    def test_topic_list_view(self):
        """Test topic list view"""
        response = self.client.get(reverse('packages:topic_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Compression')
        self.assertContains(response, 'Testing')

    def test_topic_detail_view(self):
        """Test topic detail view"""
        response = self.client.get(reverse('packages:topic_detail', args=['compression']))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Compression')
        self.assertContains(response, 'zlib')

    def test_topic_shows_package_count(self):
        """Test that topic shows correct package count"""
        response = self.client.get(reverse('packages:topic_detail', args=['compression']))
        self.assertContains(response, '1 package')

    def test_topic_not_found(self):
        """Test 404 for non-existent topic"""
        response = self.client.get(reverse('packages:topic_detail', args=['nonexistent']))
        self.assertEqual(response.status_code, 404)


class PaginationTests(TestCase):
    """Tests for pagination functionality"""

    def setUp(self):
        self.client = Client()

        # Create 25 packages to test pagination (page size is 20)
        for i in range(25):
            Package.objects.create(
                name=f'package-{i:02d}',
                description=f'Test package {i}'
            )

    def test_package_list_pagination(self):
        """Test that package list is paginated"""
        response = self.client.get(reverse('packages:package_list'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['page_obj']), 20)

    def test_package_list_second_page(self):
        """Test accessing second page"""
        response = self.client.get(reverse('packages:package_list'), {'page': 2})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['page_obj']), 5)
