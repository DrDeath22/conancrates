# ConanCrates

A private C++ package registry for Conan packages, similar to crates.io for Rust or npm for JavaScript.

## 🚀 Quick Start

See [DEPLOYMENT.md](DEPLOYMENT.md) for complete setup instructions.

```bash
git clone <repository-url> && cd ConanCrates
python -m venv venv && source venv/bin/activate  # Windows: .\venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

**Key Documentation:**
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Complete deployment guide with MinIO setup
- **[CLI_GUIDE.md](CLI_GUIDE.md)** - CLI tool for uploading and downloading packages
- [DEPENDENCY_RESOLUTION_DESIGN.md](.claude/DEPENDENCY_RESOLUTION_DESIGN.md) - Architecture for dependency resolution
- [RESUME_SESSION.md](RESUME_SESSION.md) - Latest development status and TODO list

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

## ✨ Features

- **📦 Package Management**: Browse, search, and manage Conan packages
- **🔢 Version Tracking**: Multiple versions per package with full metadata
- **💾 Binary Packages**: Pre-compiled binaries for different platforms (OS, arch, compiler)
- **🔗 Smart Dependencies**: Per-binary dependency tracking with stored dependency graphs
- **🏷️ Topics/Tags**: Categorize packages by topic for easy discovery
- **🔍 Search & Filtering**: Find packages by name, description, license, or topic
- **👨‍💼 Admin Interface**: Full-featured Django admin for package management
- **🎨 Clean UI**: User-friendly web interface for browsing packages
- **⬇️ Direct Downloads**: Download binaries and bundles without Conan client
- **📊 Dependency Resolution**: Stores pre-computed dependency graphs (lock file pattern)
- **☁️ MinIO Storage**: S3-compatible object storage for package binaries
- **🔧 CLI Tool**: `conancrates.py` for uploading and downloading packages

## 📋 Getting Started

For complete deployment instructions including MinIO setup, see **[DEPLOYMENT.md](DEPLOYMENT.md)**.

### Quick Development Setup

```bash
# 1. Clone repository
git clone <repository-url>
cd ConanCrates

# 2. Setup Python environment
python -m venv venv
source venv/bin/activate  # Windows: .\venv\Scripts\activate
pip install -r requirements.txt

# 3. Setup MinIO (in separate terminal - see DEPLOYMENT.md)
docker run -p 9000:9000 -p 9001:9001 \
  -e MINIO_ROOT_USER=admin -e MINIO_ROOT_PASSWORD=password123 \
  quay.io/minio/minio server /data --console-address ":9001"

# Create bucket "conancrates" at http://localhost:9001

# 4. Initialize database
python manage.py migrate
python manage.py createsuperuser

# 5. Start server
python manage.py runserver
```

### Access Points

- **Homepage**: http://127.0.0.1:8000/
- **Admin Panel**: http://127.0.0.1:8000/admin/
- **Package List**: http://127.0.0.1:8000/packages/
- **MinIO Console**: http://127.0.0.1:9001/ (admin/password123)

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

## 🛠️ Technology Stack

- **Backend**: Django 5.2.7 (Python 3.13)
- **Database**: SQLite (development) / PostgreSQL (production)
- **Storage**: MinIO (S3-compatible object storage)
- **Frontend**: Django Templates + CSS
- **Package Manager**: Conan 2.x (for dependency resolution)
- **API**: REST endpoints for package uploads/downloads

## 🎯 How It Works

### Dependency Resolution Architecture

ConanCrates uses a **"lock file" pattern** for dependency resolution:

1. **Client uploads package** with pre-computed dependency graph
   - Client runs `conan graph info` locally (has all deps resolved)
   - Sends graph JSON to server along with binaries

2. **Server stores graph** in `BinaryPackage.dependency_graph` field
   - No Conan needed on server for resolution
   - Each binary has its own graph (deps vary by platform)

3. **Bundle downloads** use stored graphs
   - Look up exact binaries by package_id from graph
   - Simple database queries, no dependency resolution
   - 100% accurate (came from real Conan resolution)

**Benefits:**
- ✅ No Conan needed on server
- ✅ No code execution on server (safe)
- ✅ Fast (just database lookups)
- ✅ Accurate (from real Conan resolution)

See [DEPENDENCY_RESOLUTION_DESIGN.md](.claude/DEPENDENCY_RESOLUTION_DESIGN.md) for details.

## 🚀 Using ConanCrates

### Upload Packages

```bash
# Create package with Conan
conan create . --version=1.0.0

# Upload to ConanCrates
python conancrates/conancrates.py upload package_name/1.0.0

# Upload with all dependencies
python conancrates/conancrates.py upload package_name/1.0.0 --with-dependencies
```

### Download Packages

```bash
# Download package + dependencies using your Conan profile
python conancrates/conancrates.py download package_name/1.0.0 -pr default

# Download to specific directory
python conancrates/conancrates.py download package_name/1.0.0 -pr release -o ./my_packages
```

Downloads to `./conan_packages/package_name-version/` with all dependencies matching your profile settings.

**See [CLI_GUIDE.md](CLI_GUIDE.md) for complete CLI documentation.**

### Direct Binary Downloads

Each package page shows available binaries with two download options:
- **Binary**: Download just the binary package
- **Bundle**: Download binary + all dependencies

Dependencies are listed per binary (they can vary by platform/options).

## 🧪 Development

### Running Tests

```bash
python manage.py test
```

### Creating a Superuser

```bash
python manage.py createsuperuser
```

### Making Model Changes

```bash
python manage.py makemigrations
python manage.py migrate
```

## 📚 Documentation

- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Complete deployment guide
- **[CLI_GUIDE.md](CLI_GUIDE.md)** - CLI tool usage (upload/download)
- **[WEB_UI_GUIDE.md](WEB_UI_GUIDE.md)** - Web UI browsing and downloads
- **[UPLOAD_GUIDE.md](UPLOAD_GUIDE.md)** - Manual upload via Django admin
- **[RESUME_SESSION.md](RESUME_SESSION.md)** - Current development status
- **[DEPENDENCY_RESOLUTION_DESIGN.md](.claude/DEPENDENCY_RESOLUTION_DESIGN.md)** - Technical architecture

## 🎯 Current Status

**Latest Features:**
- ✅ Per-binary dependency tracking and display
- ✅ Individual Binary and Bundle download links per binary
- ✅ Stored dependency graphs (lock file pattern)
- ✅ MinIO integration for binary storage
- ✅ CLI tool for upload/download
- ✅ Web UI for browsing packages

**Next Steps:**
- See [RESUME_SESSION.md](RESUME_SESSION.md) for TODO list

## 📄 License

MIT License - See LICENSE file for details.
