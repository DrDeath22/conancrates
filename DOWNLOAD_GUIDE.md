# ConanCrates Download Guide

This guide explains how to download packages from ConanCrates **without** requiring the Conan client.

## Important: Dependency Resolution

**NEW:** ConanCrates now uses Conan's actual dependency resolution logic for bundle downloads. This ensures:
- 100% identical dependency resolution to `conan install`
- Proper version constraint handling
- Correct settings and options propagation
- No conflicts or incompatibilities

**Requirement:** The ConanCrates server **MUST** have Conan installed for bundle generation:
```bash
pip install conan>=2.0
```

**Without Conan installed, bundle requests will fail with HTTP 503 Service Unavailable.** This is intentional - wrong packages are worse than no packages.

## Overview

ConanCrates provides multiple ways to download packages:

1. **Direct Binary Downloads** - Download individual binaries via web UI
2. **Manifest Files** - JSON files with package metadata and download URLs
3. **Bundle Information** - Package + all dependencies info in one JSON (uses Conan resolution)
4. **Download Script** - Automated shell script for batch downloads

## Method 1: Direct Binary Download (Web UI)

The simplest method - use your web browser:

1. Browse to a package page: `http://localhost:8000/packages/zlib/`
2. Select the version you want
3. In the "Available Binaries" table, click the **Download** link for your platform
4. The binary will download to your computer

**Pros:**
- No tools required
- Works in any web browser
- Simple and visual

**Cons:**
- Manual process
- Need to download dependencies separately
- One binary at a time

## Method 2: Package Manifest (JSON)

Download a JSON file containing all package information:

### Via Web UI
1. Go to package page: `http://localhost:8000/packages/zlib/1.2.13/`
2. Click "Download Manifest (JSON)" button

### Via Command Line
```bash
curl -O http://localhost:8000/packages/zlib/1.2.13/manifest/
```

### Manifest Format

```json
{
  "name": "zlib",
  "version": "1.2.13",
  "description": "...",
  "license": "Zlib",
  "author": "...",
  "homepage": "https://www.zlib.net/",
  "dependencies": [],
  "binaries": [
    {
      "id": "linx86gccrel...",
      "os": "Linux",
      "arch": "x86_64",
      "compiler": "gcc",
      "compiler_version": "11",
      "build_type": "Release",
      "size": 5242880,
      "checksum": "sha256:...",
      "download_url": "http://localhost:8000/packages/zlib/1.2.13/binaries/.../download/"
    }
  ]
}
```

### Using the Manifest

Parse the JSON and download binaries:

```python
import json
import urllib.request

# Load manifest
with open('zlib-1.2.13-manifest.json') as f:
    manifest = json.load(f)

# Download binaries
for binary in manifest['binaries']:
    if binary['os'] == 'Linux' and binary['arch'] == 'x86_64':
        url = binary['download_url']
        filename = f"{manifest['name']}-{manifest['version']}.tar.gz"
        urllib.request.urlretrieve(url, filename)
        print(f"Downloaded {filename}")
```

## Method 3: Bundle with Dependencies

Get package **plus all dependencies** resolved using Conan's logic:

### Via Web UI
1. Go to package page: `http://localhost:8000/packages/boost/1.81.0/`
2. Click "Download Bundle Info (with dependencies)"
3. Bundle info uses Conan's actual dependency resolution

### Via Command Line - Bundle Preview (JSON)

```bash
# Basic - uses default platform (Linux, x86_64, gcc 11, Release)
curl http://localhost:8000/packages/boost/1.81.0/bundle/preview/

# Specify platform and compiler version
curl "http://localhost:8000/packages/boost/1.81.0/bundle/preview/?os=Linux&arch=x86_64&compiler=gcc&compiler_version=11&build_type=Release" \
  > boost-bundle-preview.json
```

### Via Command Line - Bundle Download (ZIP)

```bash
# Download actual ZIP bundle with binaries
curl "http://localhost:8000/packages/boost/1.81.0/bundle/?os=Linux&arch=x86_64&compiler=gcc&compiler_version=11&build_type=Release" \
  -o boost-1.81.0-bundle.zip
```

### Platform Parameters

- `os`: Linux, Windows, macOS
- `arch`: x86_64, armv8, x86
- `compiler`: gcc, msvc, apple-clang, clang
- `compiler_version`: Compiler version (e.g., 11, 13, 19.29)
- `build_type`: Release, Debug

### Bundle Preview Format (JSON)

The bundle preview endpoint returns detailed information about what will be included:

```json
{
  "package": "boost",
  "version": "1.81.0",
  "platform": {
    "os": "Linux",
    "arch": "x86_64",
    "compiler": "gcc",
    "compiler_version": "11",
    "build_type": "Release"
  },
  "conan_available": true,
  "conan_version": "Conan version 2.x.x",
  "resolution_method": "conan",
  "files": [
    {
      "package": "boost",
      "version": "1.81.0",
      "type": "main",
      "package_id": "abc123...",
      "config": "OS: Linux, Arch: x86_64, Compiler: gcc 11, Build: Release",
      "size": 5242880
    },
    {
      "package": "zlib",
      "version": "1.2.13",
      "type": "dependency",
      "package_id": "def456...",
      "config": "OS: Linux, Arch: x86_64, Compiler: gcc 11, Build: Release",
      "size": 2097152
    }
  ],
  "total_size": 7340032,
  "file_count": 2
}
```

**Key fields:**
- `conan_available`: Whether Conan is installed on the server
- `conan_version`: Version of Conan being used
- `resolution_method`: "conan" (accurate) or "database_fallback" (less accurate)
- `files`: List of all packages resolved by Conan

### Download All Files from Bundle

```python
import json
import urllib.request
import os

# Load bundle
with open('boost-bundle.json') as f:
    bundle = json.load(f)

# Create download directory
os.makedirs('packages', exist_ok=True)

# Download all files
for file in bundle['files']:
    url = 'http://localhost:8000' + file['download_url']
    filename = f"{file['package']}-{file['version']}.tar.gz"
    filepath = os.path.join('packages', filename)

    print(f"Downloading {filename}...")
    urllib.request.urlretrieve(url, filepath)
    print(f"  Saved to {filepath}")

print(f"\nDownloaded {len(bundle['files'])} packages")
```

## Method 4: Automated Download Script

Download our shell script for automated downloads:

```bash
# Get the script
curl -O http://localhost:8000/download-script/

# Make it executable
chmod +x download_conan_package.sh

# Use it
./download_conan_package.sh zlib/1.2.13 Linux x86_64 gcc Release
```

The script will:
1. Fetch the bundle manifest
2. Show what will be downloaded
3. Provide commands to download all files

## Method 5: Direct URL Access

If you know the exact binary ID, download directly:

```bash
curl -O http://localhost:8000/packages/zlib/1.2.13/binaries/BINARY_ID/download/
```

## Examples

### Example 1: Download Single Package

```bash
# Get manifest
curl http://localhost:8000/packages/zlib/1.2.13/manifest/ > manifest.json

# Find the binary ID you want
cat manifest.json | jq '.binaries[] | select(.os=="Linux" and .arch=="x86_64")'

# Download it
curl -O http://localhost:8000/packages/zlib/1.2.13/binaries/BINARY_ID/download/
```

### Example 2: Download Package with Dependencies

```bash
# Get bundle for your platform
curl "http://localhost:8000/packages/boost/1.81.0/bundle/?os=Linux&arch=x86_64&compiler=gcc&build_type=Release" \
  > bundle.json

# Extract download URLs
cat bundle.json | jq -r '.files[].download_url' > urls.txt

# Download all files
while read url; do
  curl -O "http://localhost:8000$url"
done < urls.txt
```

### Example 3: Python Script for Automated Download

```python
#!/usr/bin/env python3
"""
Download a Conan package and its dependencies
"""
import sys
import json
import urllib.request
import os

def download_package(package, version, os_name='Linux', arch='x86_64',
                     compiler='gcc', build_type='Release'):
    # Construct bundle URL
    base_url = 'http://localhost:8000'
    bundle_url = (f"{base_url}/packages/{package}/{version}/bundle/"
                  f"?os={os_name}&arch={arch}&compiler={compiler}&build_type={build_type}")

    # Fetch bundle
    print(f"Fetching bundle for {package}/{version}...")
    with urllib.request.urlopen(bundle_url) as response:
        bundle = json.loads(response.read())

    # Create download directory
    download_dir = f"conan_packages/{package}-{version}"
    os.makedirs(download_dir, exist_ok=True)

    # Download all files
    for file in bundle['files']:
        url = base_url + file['download_url']
        filename = f"{file['package']}-{file['version']}-{file['binary_id']}.tar.gz"
        filepath = os.path.join(download_dir, filename)

        print(f"  Downloading {filename}...")
        urllib.request.urlretrieve(url, filepath)
        print(f"    Saved to {filepath}")

    # Save bundle manifest
    manifest_path = os.path.join(download_dir, 'bundle.json')
    with open(manifest_path, 'w') as f:
        json.dump(bundle, f, indent=2)

    print(f"\nDownloaded {len(bundle['files'])} packages to {download_dir}")
    print(f"Manifest saved to {manifest_path}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: download_package.py <package>/<version> [os] [arch] [compiler] [build_type]")
        print("Example: download_package.py zlib/1.2.13 Linux x86_64 gcc Release")
        sys.exit(1)

    package_version = sys.argv[1].split('/')
    package = package_version[0]
    version = package_version[1]

    os_name = sys.argv[2] if len(sys.argv) > 2 else 'Linux'
    arch = sys.argv[3] if len(sys.argv) > 3 else 'x86_64'
    compiler = sys.argv[4] if len(sys.argv) > 4 else 'gcc'
    build_type = sys.argv[5] if len(sys.argv) > 5 else 'Release'

    download_package(package, version, os_name, arch, compiler, build_type)
```

Save as `download_package.py` and use:

```bash
python3 download_package.py boost/1.81.0 Linux x86_64 gcc Release
```

## API Endpoints Summary

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/packages/<name>/<version>/manifest/` | GET | Package metadata + all binaries |
| `/packages/<name>/<version>/bundle/` | GET | Package + dependencies (filtered by platform) |
| `/packages/<name>/<version>/binaries/<id>/download/` | GET | Download specific binary |
| `/download-script/` | GET | Get shell script for downloads |

## Tips

1. **Always specify platform parameters** for bundle downloads to get the right binaries
2. **Include compiler_version** parameter for accurate Conan resolution
3. **Verify checksums** after download (checksums are in the manifest)
4. **Use JSON tools** like `jq` to parse manifests easily
5. **Save manifests** for reproducible builds
6. **Check file sizes** before downloading large packages
7. **Ensure Conan is installed** on the server for accurate dependency resolution

## Troubleshooting

**Q: Download returns 404**
A: Check that the package version and binary ID exist. Use the manifest to see available binaries.

**Q: Bundle is empty**
A: No binaries match your platform filters. Check what platforms are available in the manifest.

**Q: Bundle request returns HTTP 503 Service Unavailable**
A: Conan is not installed on the server. Bundle generation requires Conan for accurate dependency resolution. Install Conan on the server with `pip install conan>=2.0`. The server will not generate bundles without Conan to prevent distributing incorrect packages.

**Q: Bundle preview shows "resolution_method": "error"**
A: Conan failed to resolve dependencies. Check the error message in the response. This could be due to:
- Package not available in any Conan remote
- Conflicting version constraints
- Missing platform/compiler support

**Q: How do I know what binaries are available?**
A: Download the manifest JSON - it lists all available binaries with their configurations.

**Q: Can I download source recipes instead of binaries?**
A: Currently the prototype serves binaries. Recipe downloads would be at `/packages/<name>/<version>/recipe/`.

## Next Steps

- Check out the web UI for visual package browsing
- Use the REST API for programmatic access
- Contribute download scripts for other platforms (PowerShell, etc.)
