# ConanCrates CLI Tool Guide

Complete guide for using the `conancrates.py` CLI tool to upload and download packages.

## Overview

The `conancrates.py` CLI tool provides commands for:
- **Upload**: Upload packages from your local Conan cache to ConanCrates server
- **Download**: Download packages with dependencies using profile-based matching

**Location**: `conancrates/conancrates.py`

## Installation

No installation needed - the CLI tool is included in the repository.

**Requirements**:
- Python 3.11+
- Conan 2.x (must be installed and packages built in local cache)
- ConanCrates server running (default: http://localhost:8000)

## Quick Start

```bash
# Upload a package
python conancrates/conancrates.py upload simple_test/1.0.0

# Download a package with profile
python conancrates/conancrates.py download simple_test/1.0.0 -pr default

# Download with custom output directory
python conancrates/conancrates.py download boost/1.81.0 -pr release -o ./my_packages
```

## Upload Command

### Basic Usage

```bash
python conancrates/conancrates.py upload <package_ref>
```

**Example**:
```bash
python conancrates/conancrates.py upload zlib/1.2.13
```

### What It Does

1. Finds the package in your local Conan cache (`~/.conan2/p/`)
2. Locates all binaries for that package version
3. For each binary:
   - Creates a tarball of the package files
   - Extracts metadata (os, arch, compiler, build_type, package_id)
   - Generates dependency graph using `conan graph info`
   - Uploads tarball + metadata to ConanCrates server
4. Shows upload progress and results

### Upload Workflow

```
Local Conan Cache
    ↓
Find package by reference (name/version)
    ↓
For each binary:
  - Create tarball
  - Extract settings from package_id
  - Run conan graph info (get dependencies)
  - Upload to server
```

### Options

```bash
python conancrates/conancrates.py upload <package_ref> [options]

Options:
  --with-dependencies    Also upload all dependencies (interactive confirmation)
  --server SERVER        Server URL (default: http://localhost:8000)
```

### Upload with Dependencies

```bash
python conancrates/conancrates.py upload boost/1.81.0 --with-dependencies
```

This will:
1. Upload boost/1.81.0
2. Query server for missing dependencies
3. Ask for confirmation
4. Upload each missing dependency

### Examples

**Upload a simple package**:
```bash
# First, create the package with Conan
cd /path/to/package
conan create . --version=1.0.0

# Then upload to ConanCrates
python conancrates/conancrates.py upload mypackage/1.0.0
```

**Upload with dependencies**:
```bash
python conancrates/conancrates.py upload boost/1.81.0 --with-dependencies
```

**Upload to different server**:
```bash
python conancrates/conancrates.py upload zlib/1.2.13 --server http://192.168.1.100:8000
```

### What Gets Uploaded

For each binary package:
- **Package tarball** (.tar.gz) - All package files
- **Metadata**:
  - Package name and version
  - OS (Linux, Windows, macOS)
  - Architecture (x86_64, armv8, etc.)
  - Compiler (gcc, msvc, clang, apple-clang)
  - Compiler version (11, 13, 19.29, etc.)
  - Build type (Release, Debug)
  - Package ID (unique hash)
- **Dependency graph** (JSON) - Full dependency tree with package_ids

### Troubleshooting Upload

**Error: "Package not found in Conan cache"**
- Solution: Build the package first with `conan create .`

**Error: "Connection refused"**
- Solution: Make sure ConanCrates server is running (`python manage.py runserver`)

**Error: "Upload failed with 500"**
- Solution: Check server logs for details

## Download Command

### Basic Usage

```bash
python conancrates/conancrates.py download <package_ref> -pr <profile_name>
```

**Example**:
```bash
python conancrates/conancrates.py download testlib/1.0.0 -pr default
```

### What It Does

1. Reads your Conan profile (from `~/.conan2/profiles/`)
2. Extracts platform settings (os, arch, compiler, compiler_version, build_type)
3. Requests bundle from server with matching settings
4. Downloads ZIP bundle containing:
   - Main package binary
   - All dependency binaries (matching your profile)
5. Extracts to output directory
6. Optionally restores to Conan cache

### Profile-Based Matching

Downloads **only match binaries that have the same settings as your profile**:
- OS must match
- Architecture must match
- Compiler must match
- Compiler version must match
- Build type must match

**Options are ignored** - if multiple binaries exist with the same settings but different options, all matching binaries are downloaded.

### Options

```bash
python conancrates/conancrates.py download <package_ref> [options]

Options:
  -pr, --profile PROFILE   Conan profile to use (required!)
  -o, --output OUTPUT      Output directory (default: ./conan_packages)
  --keep-zip               Keep the downloaded ZIP file after extraction
  --server SERVER          Server URL (default: http://localhost:8000)
```

### Examples

**Download with default profile**:
```bash
python conancrates/conancrates.py download zlib/1.2.13 -pr default
```

**Download with custom profile**:
```bash
python conancrates/conancrates.py download boost/1.81.0 -pr gcc11_release
```

**Download to specific directory**:
```bash
python conancrates/conancrates.py download fmt/10.1.1 -pr default -o /path/to/packages
```

**Keep the ZIP file**:
```bash
python conancrates/conancrates.py download testlib/1.0.0 -pr default --keep-zip
```

### What Gets Downloaded

The bundle ZIP contains:
- **Main package**: The package you requested
- **All dependencies**: Resolved dependencies matching your profile
- **Metadata**: `bundle_info.json` with package details
- **README**: Info about the bundle

Directory structure after extraction:
```
./conan_packages/packagename-version/
├── packagename-version-packageid.tar.gz
├── dependency1-version-packageid.tar.gz
├── dependency2-version-packageid.tar.gz
├── bundle_info.json
└── README.txt
```

### Error Handling

**If no binaries match your profile**, you'll see a helpful error message:

```
Error: No binaries found matching your profile settings
  Requested: Linux/x86_64/gcc 13/Debug

Available binaries for testlib/1.0.0:
┌──────────┬──────────┬──────────┬─────────┬──────────────┬──────────────┐
│ OS       │ Arch     │ Compiler │ Ver     │ Build Type   │ Package ID   │
├──────────┼──────────┼──────────┼─────────┼──────────────┼──────────────┤
│ Windows* │ x86_64   │ gcc      │ 11*     │ Release*     │ abc123...    │
└──────────┴──────────┴──────────┴─────────┴──────────────┴──────────────┘

* = differs from requested profile
```

**Asterisks show which fields don't match** your requested profile settings.

### Conan Profiles

Profiles are stored in `~/.conan2/profiles/` (or `CONAN_USER_HOME/profiles/`).

**View available profiles**:
```bash
conan profile list
```

**View profile contents**:
```bash
conan profile show -pr default
```

**Create custom profile**:
```bash
# Create file: ~/.conan2/profiles/gcc13_release
[settings]
os=Linux
arch=x86_64
compiler=gcc
compiler.version=13
build_type=Release
```

### Troubleshooting Download

**Error: "Profile not found"**
- Solution: Check `conan profile list` for available profiles
- Create profile in `~/.conan2/profiles/`

**Error: "No binaries found matching your profile"**
- Solution: Check available binaries with asterisks in error message
- Upload binaries for your platform or change profile

**Error: "Connection refused"**
- Solution: Make sure ConanCrates server is running

**Error: "Package/version not found (404)"**
- Solution: Check package exists on server web UI

## Complete Workflow Example

### Upload Workflow

```bash
# 1. Create a package with Conan
cd /path/to/mylib
conan create . --version=1.0.0

# 2. Upload to ConanCrates
python conancrates/conancrates.py upload mylib/1.0.0

# 3. Verify on web UI
# Open http://localhost:8000/packages/mylib/1.0.0/
```

### Download Workflow

```bash
# 1. Check your profile
conan profile show -pr default

# 2. Download package + dependencies
python conancrates/conancrates.py download mylib/1.0.0 -pr default

# 3. Check downloaded files
ls ./conan_packages/mylib-1.0.0/

# 4. (Optional) Restore to Conan cache
# The tool shows commands to import to cache after download
```

## Advanced Usage

### Using Different Server

```bash
# Set server for all commands
export CONANCRATES_SERVER=http://192.168.1.100:8000

# Or use --server flag
python conancrates/conancrates.py upload pkg/1.0 --server http://192.168.1.100:8000
python conancrates/conancrates.py download pkg/1.0 -pr default --server http://192.168.1.100:8000
```

### Batch Upload

```bash
#!/bin/bash
# Upload multiple packages

packages=(
    "zlib/1.2.13"
    "openssl/3.0.0"
    "boost/1.81.0"
)

for pkg in "${packages[@]}"; do
    python conancrates/conancrates.py upload "$pkg"
done
```

### Batch Download

```bash
#!/bin/bash
# Download multiple packages with same profile

packages=(
    "zlib/1.2.13"
    "fmt/10.1.1"
    "nlohmann_json/3.11.2"
)

for pkg in "${packages[@]}"; do
    python conancrates/conancrates.py download "$pkg" -pr release
done
```

## API Endpoints Used

The CLI tool interacts with these ConanCrates server endpoints:

### Upload
- `POST /api/upload/` - Upload package metadata and binary
- `GET /api/packages/<name>/<version>/dependencies/` - Check existing dependencies

### Download
- `GET /packages/<name>/<version>/bundle/` - Download bundle ZIP
- `GET /packages/<name>/<version>/binaries/` - List available binaries (for error messages)

## Comparison with Other Tools

| Feature | conancrates.py | conan upload | Django Admin |
|---------|----------------|--------------|--------------|
| Upload from cache | ✅ Yes | ✅ Yes (to remotes) | ❌ Manual file upload |
| Download bundles | ✅ Yes | ❌ No bundles | ❌ No |
| Dependency graphs | ✅ Automatic | ❌ Separate step | ❌ Manual |
| Profile matching | ✅ Automatic | ⚠️ Manual | ❌ No |
| Error messages | ✅ Helpful with * | ⚠️ Basic | ❌ No download |
| Air-gapped support | ✅ Designed for it | ❌ Needs internet | ✅ Yes |

## FAQ

**Q: Why not use `conan upload -r conancrates`?**
A: That would require implementing the full Conan V2 REST API server. ConanCrates uses a simpler custom protocol via `conancrates.py`.

**Q: Can I download without a profile?**
A: No, profile is required to ensure correct platform binaries are downloaded.

**Q: What if I have multiple binaries with same settings but different options?**
A: All binaries matching the settings will be downloaded. Conan options are ignored for matching.

**Q: Can I upload without Conan installed?**
A: No, upload requires Conan to generate dependency graphs.

**Q: Where does download save files?**
A: Default is `./conan_packages/<package>-<version>/` (configurable with `-o`)

**Q: How do I restore downloaded packages to Conan cache?**
A: The tool shows the commands after download, typically:
```bash
cd conan_packages/package-version/
conan cache restore *.tar.gz
```

## Getting Help

```bash
# General help
python conancrates/conancrates.py --help

# Upload help
python conancrates/conancrates.py upload --help

# Download help
python conancrates/conancrates.py download --help
```

## See Also

- [README.md](README.md) - Project overview
- [DEPLOYMENT.md](DEPLOYMENT.md) - Server deployment
- [UPLOAD_GUIDE.md](UPLOAD_GUIDE.md) - Manual upload via Django admin
- [DOWNLOAD_GUIDE.md](DOWNLOAD_GUIDE.md) - Download via web UI and API
