# ConanCrates

A private C++ package registry for Conan packages, similar to Kellnr for Rust or crates.io.

## Project Structure

```
ConanCrates/
├── conancrates/          # Django project settings
│   ├── settings.py       # Main settings
│   ├── urls.py          # URL routing
│   └── wsgi.py          # WSGI configuration
├── packages/            # Main application
│   ├── models/          # Database models (organized by entity)
│   │   ├── package.py            # Package model
│   │   ├── package_version.py    # PackageVersion model
│   │   ├── binary_package.py     # BinaryPackage model
│   │   ├── dependency.py         # Dependency model
│   │   └── topic.py              # Topic model
│   ├── views/           # View functions (organized by feature)
│   │   ├── index.py              # Homepage view
│   │   ├── package_views.py      # Package list/detail views
│   │   └── topic_views.py        # Topic views
│   ├── admin/           # Django admin configuration (one file per model)
│   │   ├── package_admin.py
│   │   ├── package_version_admin.py
│   │   ├── binary_package_admin.py
│   │   ├── dependency_admin.py
│   │   └── topic_admin.py
│   ├── templates/       # HTML templates
│   │   └── packages/
│   │       ├── base.html
│   │       ├── index.html
│   │       ├── package_list.html
│   │       ├── package_detail.html
│   │       ├── topic_list.html
│   │       └── topic_detail.html
│   ├── tests/           # Comprehensive test suite (51 tests)
│   │   ├── test_models.py       # Model tests
│   │   ├── test_views.py        # View tests
│   │   └── test_admin.py        # Admin tests
│   ├── urls.py          # App URL routing
│   └── apps.py          # App configuration
├── media/               # Uploaded files (packages, recipes, binaries)
├── db.sqlite3           # Database (SQLite for development)
├── manage.py            # Django management script
├── requirements.txt     # Python dependencies
└── create_sample_data.py  # Script to populate sample data
```

## Features

- **Package Management**: Browse, search, and manage Conan packages
- **Version Tracking**: Multiple versions per package with full metadata
- **Binary Packages**: Support for pre-compiled binaries across different platforms/configurations
- **Dependencies**: Track package dependencies and requirements
- **Topics/Tags**: Categorize packages by topic
- **Search & Filtering**: Find packages by name, description, license, or topic
- **Admin Interface**: Full-featured Django admin for package management
- **Clean UI**: User-friendly web interface for browsing packages
- **Direct Downloads**: Download packages without Conan client (manifests, bundles, scripts)
- **Conan-Powered Resolution**: Uses Conan's actual dependency resolution for accurate bundles
- **Comprehensive Tests**: 66 automated tests covering models, views, admin, and download functionality

## Getting Started

### 1. Install Dependencies

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
.\venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 2. Run Migrations

```bash
python manage.py migrate
```

### 3. Create Sample Data (Optional)

```bash
python create_sample_data.py
```

This will create:
- Admin user (username: `admin`, password: `admin`)
- 6 sample packages (zlib, boost, openssl, fmt, gtest, nlohmann_json)
- Multiple versions and binaries for each package
- Sample dependencies and topics

### 4. Run Development Server

```bash
python manage.py runserver
```

Visit:
- **Homepage**: http://localhost:8000/
- **Admin Panel**: http://localhost:8000/admin/ (login: admin/admin)
- **Packages**: http://localhost:8000/packages/
- **Topics**: http://localhost:8000/topics/

## Architecture Decisions

### Modular Structure
The project is organized into small, focused modules instead of monolithic files:
- **models/**: Each model in its own file for easier maintenance
- **views/**: Views grouped by feature (packages, topics, etc.)
- **admin/**: Admin configurations separated by model
- **templates/**: Clean template hierarchy with base template

### Benefits
- Easier to navigate and understand
- Simpler to test individual components
- Reduces merge conflicts in team environments
- Follows Django best practices for larger projects

## Technology Stack

- **Backend**: Django 5.2 (Python)
- **Database**: SQLite (development) / PostgreSQL (production ready)
- **Frontend**: Django Templates + CSS (no heavy JavaScript framework)
- **Admin**: Django Admin (customized)
- **API**: Django REST Framework (ready for future API endpoints)

## Next Steps

- [ ] Add REST API for Conan client integration
- [ ] Implement actual file upload/download
- [ ] Add user authentication and permissions
- [ ] Implement package upload via web interface
- [ ] Add statistics and analytics
- [x] Create comprehensive test suite (66 tests covering models, views, admin, downloads)
- [x] Direct download support (manifests, bundles, individual binaries)
- [x] **Conan-powered dependency resolution** - Bundle downloads use Conan's actual resolution logic
- [x] Strict error handling - Returns HTTP 503 if Conan unavailable (no wrong packages)
- [ ] Add Docker support
- [ ] Implement S3/MinIO storage backend

## Download Without Conan Client

ConanCrates supports downloading packages without the Conan client. See [DOWNLOAD_GUIDE.md](DOWNLOAD_GUIDE.md) for details.

### Dependency Resolution

**NEW:** Bundle downloads now use Conan's actual dependency resolution logic for 100% accurate results!

- **Conan installation required** on server: `pip install conan>=2.0`
- Bundle downloads use Conan's resolver (100% accurate)
- **Fails with HTTP 503** if Conan not installed (wrong packages are worse than no packages)
- See [CONAN_INTEGRATION.md](CONAN_INTEGRATION.md) for technical details

**Quick examples:**

```bash
# Download package manifest (JSON with all metadata)
curl http://localhost:8000/packages/zlib/1.2.13/manifest/ > manifest.json

# Bundle preview with Conan resolution (includes compiler_version)
curl "http://localhost:8000/packages/boost/1.81.0/bundle/preview/?os=Linux&arch=x86_64&compiler=gcc&compiler_version=11&build_type=Release"

# Download ZIP bundle (uses Conan resolution)
curl "http://localhost:8000/packages/boost/1.81.0/bundle/?os=Linux&arch=x86_64&compiler=gcc&compiler_version=11&build_type=Release" -o boost-bundle.zip

# Get automated download script
curl -O http://localhost:8000/download-script/
```

Or use the web UI - each package page has download buttons!

## Development

### Running Tests

The project includes a comprehensive test suite with 66 tests:

```bash
# Run all tests
python manage.py test

# Run specific test module
python manage.py test packages.tests.test_models
python manage.py test packages.tests.test_views
python manage.py test packages.tests.test_admin
python manage.py test packages.tests.test_download_views

# Run with verbose output
python manage.py test --verbosity=2
```

**Test Coverage:**
- **Model Tests** (30 tests): Package, PackageVersion, BinaryPackage, Dependency, Topic
- **View Tests** (15 tests): Homepage, package list/detail, topics, search, filtering, pagination
- **Admin Tests** (6 tests): Admin interface functionality, authentication, CRUD operations
- **Download Tests** (15 tests): Binary downloads, manifests, bundles, Conan integration, error handling

### Creating a Superuser
```bash
python manage.py createsuperuser
```

### Making Model Changes
```bash
python manage.py makemigrations
python manage.py migrate
```

## License

This is a prototype project for evaluation.
