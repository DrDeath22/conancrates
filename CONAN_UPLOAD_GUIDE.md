# Conan Upload Guide

This guide shows you how to upload real Conan packages to ConanCrates using the `conan upload` command.

## Prerequisites

✅ Conan 2.11.0 installed (included in venv)
✅ ConanCrates server running (http://localhost:8000)
✅ MinIO storage backend configured

## Quick Start

### 1. Add ConanCrates as a Conan Remote

```bash
# Using the venv's conan
./venv/Scripts/conan remote add conancrates http://localhost:8000/v2

# Or if using system conan
conan remote add conancrates http://localhost:8000/v2
```

### 2. Build a Package

```bash
# Example: Build zlib
cd /path/to/conan-center-index/recipes/zlib/all
./venv/Scripts/conan create . --version=1.2.13
```

### 3. Upload to ConanCrates

```bash
./venv/Scripts/conan upload zlib/1.2.13 -r conancrates --confirm
```

## Detailed Workflow

### Creating a Simple Test Package

Let me create a simple test package:

```bash
mkdir -p test_package
cd test_package
```

Create `conanfile.py`:
```python
from conan import ConanFile

class HelloConan(ConanFile):
    name = "hello"
    version = "1.0"
    settings = "os", "compiler", "build_type", "arch"

    def package_info(self):
        self.cpp_info.libs = ["hello"]
```

Build it:
```bash
./venv/Scripts/conan create . --name=hello --version=1.0
```

Upload it:
```bash
./venv/Scripts/conan upload hello/1.0 -r conancrates --confirm
```

## API Endpoints

ConanCrates implements the following Conan V2 API endpoints:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v2/ping` | GET | Check server availability |
| `/v2/users/check_credentials` | GET | Verify authentication |
| `/v2/conans/{name}/{version}/upload` | POST | Upload recipe |
| `/v2/conans/{name}/{version}/packages/{id}/upload` | POST | Upload binary |
| `/v2/conans/search` | GET | Search packages |

## Current Limitations

### What Works:
✅ Basic upload API endpoints
✅ Binary file storage in MinIO
✅ Package metadata creation
✅ Download of uploaded packages

### What's Missing:
❌ Recipe file storage (conanfile.py, conandata.yml)
❌ Authentication/authorization
❌ Automatic metadata extraction from conanfile.py
❌ Package revision tracking
❌ Full Conan V2 API compatibility

## Manual Upload Workflow (Simpler)

If the automated upload doesn't work yet, you can manually upload package binaries:

### 1. Find Your Package in Conan Cache

```bash
# List packages
./venv/Scripts/conan list "*"

# Find package location
./venv/Scripts/conan cache path zlib/1.2.13
```

### 2. Copy Binary to Temp Location

The binary `.tar.gz` file is in the package cache.

### 3. Upload via Django Admin

1. Go to http://localhost:8000/admin/
2. Create Package and PackageVersion if needed
3. Create or edit BinaryPackage
4. Upload the `.tar.gz` file
5. File goes directly to MinIO!

## Troubleshooting

### "Remote not found"

Make sure you added the remote:
```bash
./venv/Scripts/conan remote list
```

Should show:
```
conancrates: http://localhost:8000/v2 [Verify SSL: True, Enabled: True]
```

### "Upload failed"

Check Django server logs for errors. The upload API is basic and may not handle all cases yet.

### "Authentication failed"

Currently, authentication is not enforced. All uploads are accepted.

## Next Steps

To make this production-ready, we need to implement:

1. **Recipe file handling** - Store and serve conanfile.py, conandata.yml
2. **Metadata extraction** - Parse conanfile.py to extract dependencies, settings, options
3. **Authentication** - Token-based auth for uploads
4. **Full API** - Complete Conan V2 REST API implementation
5. **Revision tracking** - Handle package revisions

## Example: Real World Package

```bash
# 1. Clone conan-center-index
git clone https://github.com/conan-io/conan-center-index.git
cd conan-center-index

# 2. Build a package
cd recipes/fmt/all
../../../venv/Scripts/conan create . --version=10.1.1

# 3. Upload to ConanCrates
../../../venv/Scripts/conan upload fmt/10.1.1 -r conancrates --confirm

# 4. Verify in ConanCrates UI
# Open http://localhost:8000/packages/
# You should see fmt/10.1.1!
```

## Architecture

```
Conan Client
    ↓ (conan upload)
ConanCrates REST API (/v2/*)
    ↓
Django Views (upload_views.py)
    ↓
Database (metadata) + MinIO (binaries)
```

ConanCrates acts as a lightweight Conan server, storing:
- Package metadata in PostgreSQL/SQLite
- Binary files (.tar.gz) in MinIO
- Recipe files (TODO)

## Comparison with Artifactory

| Feature | Artifactory | ConanCrates |
|---------|-------------|-------------|
| Conan V2 API | ✅ Full | ⚠️ Partial (upload basic, download working) |
| Binary storage | ✅ | ✅ |
| Recipe storage | ✅ | ❌ (TODO) |
| Authentication | ✅ | ❌ (TODO) |
| Web UI | ⚠️ Basic | ✅ Beautiful |
| Dependency resolution | ⚠️ Basic | ✅ Uses Conan CLI |
| Storage backend | ✅ Built-in | ✅ MinIO/S3 (flexible) |
| Cost | 💰 Commercial | 🆓 Free |

ConanCrates is perfect for:
- Air-gapped environments
- Custom workflows
- Teams that want control
- Testing and development
