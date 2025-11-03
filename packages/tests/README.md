# ConanCrates Test Suite

This directory contains all tests for the ConanCrates package registry application.

## Test Organization

### Django Unit Tests

These tests use Django's TestCase framework and cover the web application functionality:

- **`test_models.py`** - Tests for database models
  - Package, PackageVersion, BinaryPackage, Dependency models
  - Model creation, validation, relationships, and methods

- **`test_views.py`** - Tests for web UI views
  - Homepage, package listing, package detail pages
  - Version selection, topic filtering

- **`test_admin.py`** - Tests for Django admin interface
  - Admin authentication and authorization
  - Package management through admin
  - Search and filtering functionality

- **`test_download_views.py`** - Tests for download endpoints
  - Binary downloads, bundle generation
  - Recipe downloads
  - Extracted format downloads for non-Conan users

### CLI Integration Tests

These tests verify the `conancrates.py` CLI tool functionality:

- **`test_profile_download.py`** - Tests for CLI upload and download features
  - **Download Tests:**
    - Non-matching profile error handling (shows available binaries with asterisks)
    - Matching profile successful download
    - Binaries listing endpoint (`/packages/<name>/<version>/binaries/`)
  - **Upload Tests:**
    - Upload with conan create (integration test)
    - Upload error handling for missing packages
    - Upload command structure verification
    - Dependency graph upload verification

## Running Tests

### Run All Tests

```bash
python manage.py test packages.tests
```

### Run Specific Test Files

```bash
# Django unit tests
python manage.py test packages.tests.test_models
python manage.py test packages.tests.test_views
python manage.py test packages.tests.test_admin
python manage.py test packages.tests.test_download_views

# CLI integration test
python packages/tests/test_profile_download.py
```

### Run With Verbose Output

```bash
python manage.py test packages.tests --verbosity=2
```

### Run Specific Test Classes or Methods

```bash
# Run a specific test class
python manage.py test packages.tests.test_models.PackageModelTests

# Run a specific test method
python manage.py test packages.tests.test_models.PackageModelTests.test_package_creation
```

## Test Coverage

### Current Coverage (58 tests)

- **Models**: 16 tests
  - Package: 5 tests
  - PackageVersion: 5 tests
  - BinaryPackage: 5 tests
  - Dependency: 3 tests

- **Views**: 13 tests
  - Web UI views
  - Package detail and listing
  - Version selection and dependencies

- **Admin**: 11 tests
  - Authentication and authorization
  - CRUD operations
  - Search and filtering

- **Download Views**: 8 tests
  - Binary downloads
  - Bundle generation
  - Recipe downloads

- **CLI Integration**: 7 tests (3 download + 4 upload)
  - Profile-based downloads with error handling
  - Upload with conan create workflow
  - Upload error handling
  - Command structure verification
  - Dependency graph uploads
  - Binaries listing API

## Writing New Tests

### Django Unit Tests

Follow the existing pattern in the test files:

```python
from django.test import TestCase
from packages.models import Package

class MyFeatureTests(TestCase):
    def setUp(self):
        # Set up test data
        self.package = Package.objects.create(
            name="testpkg",
            description="Test package"
        )

    def test_my_feature(self):
        # Test your feature
        self.assertEqual(self.package.name, "testpkg")
```

### CLI Integration Tests

For testing CLI functionality that requires a running server:

```python
import subprocess
import sys

def test_cli_feature():
    """Test CLI feature"""
    cmd = [
        sys.executable,
        "conancrates/conancrates.py",
        "command",
        "args"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0
    assert "expected output" in result.stdout
```

## Test Database

Django tests automatically create and destroy a test database for each test run. The test database uses SQLite in-memory mode for speed.

## Fixtures and Test Data

Test data is created in the `setUp()` method of each test class. This ensures:
- Clean state for each test
- No dependencies between tests
- Fast test execution

## Continuous Integration

These tests should be run:
- Before committing changes
- In CI/CD pipelines
- Before deploying to production

## Known Issues

- One test currently fails: `test_package_detail_without_binaries` in `test_views.py`
  - Issue: HTML output format changed due to new `conan_version` field in template
  - Status: Needs update to match new template format

## Contributing

When adding new features:
1. Write tests first (TDD approach recommended)
2. Ensure all existing tests still pass
3. Add tests for edge cases and error conditions
4. Update this README if adding new test files
