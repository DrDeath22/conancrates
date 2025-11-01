"""
Script to create sample Conan packages for demonstration
"""
import os
import sys
import django

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'conancrates.settings')
django.setup()

from django.contrib.auth.models import User
from packages.models import Package, PackageVersion, BinaryPackage, Dependency, Topic

# Set admin password
admin = User.objects.get(username='admin')
admin.set_password('admin')
admin.save()
print("✓ Admin password set to 'admin'")

# Create topics
topics_data = [
    {'name': 'Compression', 'slug': 'compression', 'description': 'Data compression libraries'},
    {'name': 'Graphics', 'slug': 'graphics', 'description': 'Graphics and image processing'},
    {'name': 'Networking', 'slug': 'networking', 'description': 'Network communication libraries'},
    {'name': 'Testing', 'slug': 'testing', 'description': 'Testing frameworks and utilities'},
    {'name': 'Serialization', 'slug': 'serialization', 'description': 'Data serialization formats'},
]

topics = {}
for topic_data in topics_data:
    topic, created = Topic.objects.get_or_create(**topic_data)
    topics[topic.name] = topic
    if created:
        print(f"✓ Created topic: {topic.name}")

# Create sample packages
packages_data = [
    {
        'name': 'zlib',
        'description': 'A massively spiffy yet delicately unobtrusive compression library',
        'homepage': 'https://www.zlib.net/',
        'license': 'Zlib',
        'author': 'Jean-loup Gailly and Mark Adler',
        'topics': 'compression, core',
        'versions': [
            {'version': '1.2.13', 'binaries': [
                {'os': 'Linux', 'arch': 'x86_64', 'compiler': 'gcc', 'compiler_version': '11', 'build_type': 'Release'},
                {'os': 'Linux', 'arch': 'x86_64', 'compiler': 'gcc', 'compiler_version': '11', 'build_type': 'Debug'},
                {'os': 'Windows', 'arch': 'x86_64', 'compiler': 'msvc', 'compiler_version': '193', 'build_type': 'Release'},
            ]},
            {'version': '1.2.12', 'binaries': [
                {'os': 'Linux', 'arch': 'x86_64', 'compiler': 'gcc', 'compiler_version': '9', 'build_type': 'Release'},
            ]},
        ]
    },
    {
        'name': 'boost',
        'description': 'Boost provides free peer-reviewed portable C++ source libraries',
        'homepage': 'https://www.boost.org/',
        'license': 'BSL-1.0',
        'author': 'Boost Community',
        'topics': 'core, utilities',
        'versions': [
            {'version': '1.81.0', 'binaries': [
                {'os': 'Linux', 'arch': 'x86_64', 'compiler': 'gcc', 'compiler_version': '11', 'build_type': 'Release'},
                {'os': 'Windows', 'arch': 'x86_64', 'compiler': 'msvc', 'compiler_version': '193', 'build_type': 'Release'},
            ]},
            {'version': '1.80.0', 'binaries': [
                {'os': 'Linux', 'arch': 'x86_64', 'compiler': 'gcc', 'compiler_version': '11', 'build_type': 'Release'},
            ]},
        ]
    },
    {
        'name': 'openssl',
        'description': 'A robust, commercial-grade, and full-featured toolkit for TLS and SSL',
        'homepage': 'https://www.openssl.org/',
        'license': 'Apache-2.0',
        'author': 'OpenSSL Software Foundation',
        'topics': 'security, cryptography',
        'versions': [
            {'version': '3.1.0', 'binaries': [
                {'os': 'Linux', 'arch': 'x86_64', 'compiler': 'gcc', 'compiler_version': '11', 'build_type': 'Release'},
                {'os': 'Windows', 'arch': 'x86_64', 'compiler': 'msvc', 'compiler_version': '193', 'build_type': 'Release'},
                {'os': 'macOS', 'arch': 'armv8', 'compiler': 'apple-clang', 'compiler_version': '14', 'build_type': 'Release'},
            ]},
        ]
    },
    {
        'name': 'fmt',
        'description': 'A modern formatting library',
        'homepage': 'https://fmt.dev/',
        'license': 'MIT',
        'author': 'Victor Zverovich',
        'topics': 'formatting, utilities',
        'versions': [
            {'version': '10.0.0', 'binaries': [
                {'os': 'Linux', 'arch': 'x86_64', 'compiler': 'gcc', 'compiler_version': '11', 'build_type': 'Release'},
                {'os': 'Windows', 'arch': 'x86_64', 'compiler': 'msvc', 'compiler_version': '193', 'build_type': 'Release'},
            ]},
            {'version': '9.1.0', 'binaries': [
                {'os': 'Linux', 'arch': 'x86_64', 'compiler': 'gcc', 'compiler_version': '11', 'build_type': 'Release'},
            ]},
        ]
    },
    {
        'name': 'gtest',
        'description': "Google's C++ test framework",
        'homepage': 'https://github.com/google/googletest',
        'license': 'BSD-3-Clause',
        'author': 'Google Inc.',
        'topics': 'testing, quality',
        'versions': [
            {'version': '1.13.0', 'binaries': [
                {'os': 'Linux', 'arch': 'x86_64', 'compiler': 'gcc', 'compiler_version': '11', 'build_type': 'Release'},
                {'os': 'Windows', 'arch': 'x86_64', 'compiler': 'msvc', 'compiler_version': '193', 'build_type': 'Release'},
            ]},
        ]
    },
    {
        'name': 'nlohmann_json',
        'description': 'JSON for Modern C++',
        'homepage': 'https://json.nlohmann.me/',
        'license': 'MIT',
        'author': 'Niels Lohmann',
        'topics': 'json, serialization, parsing',
        'versions': [
            {'version': '3.11.2', 'binaries': [
                {'os': 'Linux', 'arch': 'x86_64', 'compiler': 'gcc', 'compiler_version': '11', 'build_type': 'Release'},
                {'os': 'Windows', 'arch': 'x86_64', 'compiler': 'msvc', 'compiler_version': '193', 'build_type': 'Release'},
            ]},
        ]
    },
]

for pkg_data in packages_data:
    versions_data = pkg_data.pop('versions')

    package, created = Package.objects.get_or_create(
        name=pkg_data['name'],
        defaults=pkg_data
    )

    if created:
        print(f"✓ Created package: {package.name}")

        # Add topics
        if 'Compression' in pkg_data.get('topics', ''):
            topics['Compression'].packages.add(package)
        if 'Testing' in pkg_data.get('topics', ''):
            topics['Testing'].packages.add(package)
        if 'Serialization' in pkg_data.get('topics', ''):
            topics['Serialization'].packages.add(package)

        # Create versions
        for ver_data in versions_data:
            binaries_data = ver_data.pop('binaries')

            version = PackageVersion.objects.create(
                package=package,
                version=ver_data['version'],
                uploaded_by=admin,
                description=pkg_data['description']
            )
            print(f"  ✓ Created version: {version.full_name()}")

            # Create binaries
            for binary_data in binaries_data:
                # Generate a fake package ID
                pkg_id = f"{binary_data['os'][:3]}{binary_data['arch'][:3]}{binary_data['compiler'][:3]}{binary_data['build_type'][:3]}".lower()
                pkg_id = pkg_id + "0" * (16 - len(pkg_id))  # Pad to 16 chars

                binary = BinaryPackage.objects.create(
                    package_version=version,
                    package_id=pkg_id + str(hash(f"{package.name}{version.version}{binary_data}"))[:8],
                    file_size=1024 * 1024 * 5,  # 5 MB fake size
                    **binary_data
                )
                print(f"    ✓ Created binary: {binary.get_config_string()}")

# Create some dependencies
print("\n✓ Creating dependencies...")
zlib = Package.objects.get(name='zlib')
boost = Package.objects.get(name='boost')
openssl = Package.objects.get(name='openssl')

boost_version = PackageVersion.objects.filter(package=boost).first()
openssl_version = PackageVersion.objects.filter(package=openssl).first()

if boost_version:
    Dependency.objects.get_or_create(
        package_version=boost_version,
        requires_package=zlib,
        version_requirement='>=1.2.11',
        dependency_type='requires'
    )
    print(f"  ✓ {boost_version.full_name()} requires zlib>=1.2.11")

if openssl_version:
    Dependency.objects.get_or_create(
        package_version=openssl_version,
        requires_package=zlib,
        version_requirement='>=1.2.11',
        dependency_type='requires'
    )
    print(f"  ✓ {openssl_version.full_name()} requires zlib>=1.2.11")

print("\n" + "="*50)
print("Sample data created successfully!")
print("="*50)
print("\nYou can now login to the admin panel:")
print("  URL: http://localhost:8000/admin/")
print("  Username: admin")
print("  Password: admin")
