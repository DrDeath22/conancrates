"""
Views for downloading packages and binaries
"""
import os
import json
import zipfile
import tarfile
import tempfile
import shutil
from pathlib import Path
from django.shortcuts import get_object_or_404
from django.http import FileResponse, JsonResponse, HttpResponse
from packages.models import Package, PackageVersion, BinaryPackage
from packages.conan_wrapper import (
    resolve_dependencies,
    check_conan_available,
    get_conan_version,
    ConanError
)


def download_binary(request, package_name, version, binary_id):
    """
    Direct download of a specific binary package
    """
    package = get_object_or_404(Package, name=package_name)
    package_version = get_object_or_404(PackageVersion, package=package, version=version)
    binary = get_object_or_404(BinaryPackage, package_version=package_version, package_id=binary_id)

    # Increment download count
    binary.download_count += 1
    binary.save()

    package.download_count += 1
    package.save()

    # Serve actual file if it exists
    if binary.binary_file and binary.binary_file.name:
        try:
            # For cloud storage (MinIO/S3), you could return a redirect:
            # from django.http import HttpResponseRedirect
            # return HttpResponseRedirect(binary.binary_file.url)

            # For local filesystem, stream the file
            return FileResponse(
                binary.binary_file.open('rb'),
                as_attachment=True,
                filename=f"{package_name}-{version}-{binary_id}.tar.gz",
                content_type='application/gzip'
            )
        except Exception as e:
            return HttpResponse(
                f"Error reading file: {str(e)}\n"
                f"File path: {binary.binary_file.name}",
                status=500,
                content_type='text/plain'
            )

    # No file uploaded yet - return helpful placeholder
    response = HttpResponse(
        f"Binary download: {package_name}/{version} - {binary.get_config_string()}\n"
        f"Package ID: {binary_id}\n\n"
        f"No file uploaded yet for this binary.\n\n"
        f"To upload a file:\n"
        f"1. Log into Django admin at /admin/\n"
        f"2. Navigate to Binary Packages\n"
        f"3. Edit this binary and upload a file\n",
        content_type='text/plain',
        status=404
    )
    response['Content-Disposition'] = f'attachment; filename="{package_name}-{version}-{binary_id}.txt"'
    return response


def bundle_preview(request, package_name, version):
    """
    Preview what will be in the bundle before downloading (JSON response)
    Uses stored dependency graph from upload time for accurate results.
    """
    package = get_object_or_404(Package, name=package_name)
    package_version = get_object_or_404(PackageVersion, package=package, version=version)

    # Get platform info from query params or use defaults
    os_filter = request.GET.get('os', 'Linux')
    arch_filter = request.GET.get('arch', 'x86_64')
    compiler_filter = request.GET.get('compiler', 'gcc')
    compiler_version_filter = request.GET.get('compiler_version', '11')
    build_type_filter = request.GET.get('build_type', 'Release')

    preview_data = {
        'package': package_name,
        'version': version,
        'platform': {
            'os': os_filter,
            'arch': arch_filter,
            'compiler': compiler_filter,
            'compiler_version': compiler_version_filter,
            'build_type': build_type_filter,
        },
        'files': [],
        'total_size': 0,
        'file_count': 0,
        'resolution_method': 'stored_graph'
    }

    # Find the binary for the requested platform
    binaries = package_version.binaries.filter(
        os=os_filter,
        arch=arch_filter,
        compiler=compiler_filter,
        compiler_version=compiler_version_filter,
        build_type=build_type_filter
    )

    if not binaries.exists():
        preview_data['error'] = (
            f"No binary found for {package_name}/{version} with settings: "
            f"{os_filter}/{arch_filter}/{compiler_filter}-{compiler_version_filter}/{build_type_filter}"
        )
        preview_data['resolution_method'] = 'error'
        return JsonResponse(preview_data, status=404, json_dumps_params={'indent': 2})

    binary = binaries.first()

    # Add the main package
    preview_data['files'].append({
        'package': package_name,
        'version': version,
        'type': 'main',
        'package_id': binary.package_id,
        'config': binary.get_config_string(),
        'size': binary.file_size
    })
    preview_data['total_size'] += binary.file_size
    preview_data['file_count'] += 1

    # Process dependency graph if it exists
    if binary.dependency_graph:
        graph = binary.dependency_graph
        nodes = graph.get('graph', {}).get('nodes', {})

        for node_id, node in nodes.items():
            # Skip root node (the package itself)
            if node_id == "0":
                continue

            # Parse package reference (e.g., "boost/1.81.0" or "boost/1.81.0#hash")
            ref = node.get('ref', '')
            if '/' not in ref:
                continue

            dep_name, dep_version_with_hash = ref.split('/', 1)
            # Remove recipe revision hash if present (e.g., "1.0.0#hash" -> "1.0.0")
            dep_version = dep_version_with_hash.split('#')[0]
            dep_package_id = node.get('package_id', 'unknown')

            # Look up the dependency binary in database
            try:
                dep_binary = BinaryPackage.objects.get(
                    package_version__package__name=dep_name,
                    package_version__version=dep_version,
                    package_id=dep_package_id
                )

                preview_data['files'].append({
                    'package': dep_name,
                    'version': dep_version,
                    'type': 'dependency',
                    'package_id': dep_package_id,
                    'config': dep_binary.get_config_string(),
                    'size': dep_binary.file_size
                })
                preview_data['total_size'] += dep_binary.file_size
                preview_data['file_count'] += 1

            except BinaryPackage.DoesNotExist:
                # Dependency binary not in database
                preview_data['files'].append({
                    'package': dep_name,
                    'version': dep_version,
                    'type': 'dependency',
                    'package_id': dep_package_id,
                    'config': 'Unknown',
                    'size': 0,
                    'note': f'Missing dependency: {dep_name}/{dep_version} with package_id {dep_package_id}'
                })

    return JsonResponse(preview_data, json_dumps_params={'indent': 2})


def download_bundle(request, package_name, version):
    """
    Download package with all its dependencies as a ZIP bundle
    Uses stored dependency graph from upload time for 100% accurate bundles.
    """
    package = get_object_or_404(Package, name=package_name)
    package_version = get_object_or_404(PackageVersion, package=package, version=version)

    # Get platform info from query params or use defaults
    os_filter = request.GET.get('os', 'Linux')
    arch_filter = request.GET.get('arch', 'x86_64')
    compiler_filter = request.GET.get('compiler', 'gcc')
    compiler_version_filter = request.GET.get('compiler_version', '11')
    build_type_filter = request.GET.get('build_type', 'Release')

    bundle_metadata = {
        'package': package_name,
        'version': version,
        'platform': {
            'os': os_filter,
            'arch': arch_filter,
            'compiler': compiler_filter,
            'compiler_version': compiler_version_filter,
            'build_type': build_type_filter,
        },
        'contents': [],
        'resolution_method': 'stored_graph'
    }

    binaries_to_bundle = []

    # Find the binary for the requested platform
    binaries = package_version.binaries.filter(
        os=os_filter,
        arch=arch_filter,
        compiler=compiler_filter,
        compiler_version=compiler_version_filter,
        build_type=build_type_filter
    )

    if not binaries.exists():
        error_response = {
            'error': (
                f"No binary found for {package_name}/{version} with settings: "
                f"{os_filter}/{arch_filter}/{compiler_filter}-{compiler_version_filter}/{build_type_filter}"
            ),
            'package': package_name,
            'version': version,
            'platform': bundle_metadata['platform'],
            'resolution_method': 'error'
        }
        return JsonResponse(error_response, status=404, json_dumps_params={'indent': 2})

    binary = binaries.first()

    # Add the main package to bundle
    binaries_to_bundle.append((binary, package_name, version))
    bundle_metadata['contents'].append({
        'package': package_name,
        'version': version,
        'type': 'main',
        'package_id': binary.package_id,
        'config': binary.get_config_string()
    })

    # Process dependency graph if it exists
    if binary.dependency_graph:
        graph = binary.dependency_graph
        nodes = graph.get('graph', {}).get('nodes', {})

        for node_id, node in nodes.items():
            # Skip root node (the package itself)
            if node_id == "0":
                continue

            # Parse package reference (e.g., "boost/1.81.0" or "boost/1.81.0#hash")
            ref = node.get('ref', '')
            if '/' not in ref:
                continue

            dep_name, dep_version_with_hash = ref.split('/', 1)
            # Remove recipe revision hash if present (e.g., "1.0.0#hash" -> "1.0.0")
            dep_version = dep_version_with_hash.split('#')[0]
            dep_package_id = node.get('package_id', 'unknown')

            # Look up the dependency binary in database
            try:
                dep_binary = BinaryPackage.objects.get(
                    package_version__package__name=dep_name,
                    package_version__version=dep_version,
                    package_id=dep_package_id
                )

                binaries_to_bundle.append((dep_binary, dep_name, dep_version))
                bundle_metadata['contents'].append({
                    'package': dep_name,
                    'version': dep_version,
                    'type': 'dependency',
                    'package_id': dep_package_id,
                    'config': dep_binary.get_config_string()
                })

            except BinaryPackage.DoesNotExist:
                # Dependency binary not in database - add to metadata but not bundle
                bundle_metadata['contents'].append({
                    'package': dep_name,
                    'version': dep_version,
                    'type': 'dependency',
                    'package_id': dep_package_id,
                    'config': 'Unknown',
                    'note': f'Missing dependency: {dep_name}/{dep_version} with package_id {dep_package_id} - not included in bundle'
                })

    # Create ZIP file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_file:
        with zipfile.ZipFile(tmp_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add metadata file
            zipf.writestr('bundle_info.json', json.dumps(bundle_metadata, indent=2))

            # Add README
            readme_content = f"""# {package_name}/{version} Bundle

This bundle contains {package_name} version {version} and all its dependencies
for {os_filter}/{arch_filter}/{compiler_filter}/{compiler_version_filter}/{build_type_filter}.

## Resolution Method

Dependencies resolved using: {bundle_metadata.get('resolution_method', 'unknown')}
Conan version: {bundle_metadata.get('conan_version', 'N/A')}

## Contents

"""
            for item in bundle_metadata['contents']:
                note = f" - {item['note']}" if 'note' in item else ""
                readme_content += f"- {item['package']}/{item['version']} ({item['type']}){note}\n"

            readme_content += """
## Note

This is a prototype. In production, actual binary files would be included.
Currently, placeholder files are provided for packages in the local database.

## Installation

Extract this bundle and follow your project's installation instructions.
"""
            zipf.writestr('README.txt', readme_content)

            # Add binaries and recipes
            for binary, pkg_name, pkg_ver in binaries_to_bundle:
                # Create package directory in ZIP
                pkg_dir = f'{pkg_name}-{pkg_ver}'

                # Add recipe (conanfile.py) if available
                try:
                    pkg_version_obj = PackageVersion.objects.get(
                        package__name=pkg_name,
                        version=pkg_ver
                    )
                    if pkg_version_obj.recipe_content:
                        zipf.writestr(
                            f'{pkg_dir}/conanfile.py',
                            pkg_version_obj.recipe_content
                        )
                except PackageVersion.DoesNotExist:
                    pass

                # Add binary file from MinIO/storage
                if binary.binary_file and binary.binary_file.name:
                    try:
                        # Read from storage backend (works with both local and MinIO)
                        binary_content = binary.binary_file.read()
                        zipf.writestr(
                            f'{pkg_dir}/{pkg_name}-{pkg_ver}-{binary.package_id}.tar.gz',
                            binary_content
                        )
                    except Exception as e:
                        # If binary file can't be read, add a note
                        error_note = f"""Package: {pkg_name}/{pkg_ver}
Binary ID: {binary.package_id}
Configuration: {binary.get_config_string()}
Size: {binary.file_size} bytes

Error: Could not read binary file: {e}
"""
                        zipf.writestr(
                            f'{pkg_dir}/ERROR.txt',
                            error_note
                        )

        # Return the ZIP file
        tmp_file.seek(0)
        response = FileResponse(
            open(tmp_file.name, 'rb'),
            content_type='application/zip',
            as_attachment=True,
            filename=f'{package_name}-{version}-bundle.zip'
        )

        return response


def download_manifest(request, package_name, version):
    """
    Generate a dependency manifest (JSON) that can be used by scripts
    """
    package = get_object_or_404(Package, name=package_name)
    package_version = get_object_or_404(PackageVersion, package=package, version=version)

    manifest = {
        'name': package_name,
        'version': version,
        'description': package.description,
        'license': package.license,
        'author': package.author,
        'homepage': package.homepage,
        'dependencies': [],
        'binaries': []
    }

    # Add dependencies
    for dep in package_version.dependencies.all():
        dep_version = dep.requires_package.latest_version()
        manifest['dependencies'].append({
            'name': dep.requires_package.name,
            'version': dep_version.version if dep_version else 'unknown',
            'version_requirement': dep.version_requirement,
            'type': dep.dependency_type,
        })

    # Add available binaries
    for binary in package_version.binaries.all():
        manifest['binaries'].append({
            'id': binary.package_id,
            'os': binary.os,
            'arch': binary.arch,
            'compiler': binary.compiler,
            'compiler_version': binary.compiler_version,
            'build_type': binary.build_type,
            'size': binary.file_size,
            'checksum': binary.sha256,
            'download_url': request.build_absolute_uri(
                f'/packages/{package_name}/{version}/binaries/{binary.package_id}/download/'
            )
        })

    response = JsonResponse(manifest, json_dumps_params={'indent': 2})
    response['Content-Disposition'] = f'attachment; filename="{package_name}-{version}-manifest.json"'
    return response


def download_script(request):
    """
    Provide a shell script for downloading packages
    """
    script = """#!/bin/bash
# ConanCrates Package Downloader
# Usage: ./download.sh <package>/<version> [os] [arch] [compiler] [build_type]

set -e

PACKAGE_VERSION=$1
OS=${2:-Linux}
ARCH=${3:-x86_64}
COMPILER=${4:-gcc}
BUILD_TYPE=${5:-Release}

if [ -z "$PACKAGE_VERSION" ]; then
    echo "Usage: $0 <package>/<version> [os] [arch] [compiler] [build_type]"
    echo "Example: $0 zlib/1.2.13 Linux x86_64 gcc Release"
    exit 1
fi

REGISTRY_URL="http://localhost:8000"

echo "Downloading $PACKAGE_VERSION for $OS/$ARCH/$COMPILER/$BUILD_TYPE..."

# Get the bundle manifest
MANIFEST=$(curl -s "$REGISTRY_URL/packages/$PACKAGE_VERSION/bundle/?os=$OS&arch=$ARCH&compiler=$COMPILER&build_type=$BUILD_TYPE")

# Create download directory
DOWNLOAD_DIR="conan_packages"
mkdir -p "$DOWNLOAD_DIR"

# Save manifest
echo "$MANIFEST" > "$DOWNLOAD_DIR/manifest.json"

echo "Manifest saved to $DOWNLOAD_DIR/manifest.json"
echo ""
echo "Files to download:"
echo "$MANIFEST" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for file in data.get('files', []):
    print(f\"  - {file['package']}/{file['version']} ({file['size']} bytes)\")
"

echo ""
echo "To download the files, run:"
echo "  cd $DOWNLOAD_DIR"
echo "  cat manifest.json | python3 -c \\"
import sys, json, urllib.request, os
data = json.load(sys.stdin)
for file in data.get('files', []):
    url = 'http://localhost:8000' + file['download_url']
    filename = f\\\"{file['package']}-{file['version']}-{file['binary_id']}.tar.gz\\\"
    print(f'Downloading {filename}...')
    urllib.request.urlretrieve(url, filename)
\\""

echo ""
echo "Done! Manifest created."
"""

    response = HttpResponse(script, content_type='text/plain')
    response['Content-Disposition'] = 'attachment; filename="download_conan_package.sh"'
    return response


def download_recipe(request, package_name, version):
    """
    Download the conanfile.py (recipe) for a package version
    """
    package = get_object_or_404(Package, name=package_name)
    package_version = get_object_or_404(PackageVersion, package=package, version=version)

    if not package_version.recipe_content:
        return HttpResponse(
            "Recipe not available for this package version",
            status=404,
            content_type='text/plain'
        )

    response = HttpResponse(package_version.recipe_content, content_type='text/plain')
    response['Content-Disposition'] = f'attachment; filename="conanfile.py"'
    return response


def view_recipe(request, package_name, version):
    """
    View the conanfile.py (recipe) for a package version in the browser
    """
    package = get_object_or_404(Package, name=package_name)
    package_version = get_object_or_404(PackageVersion, package=package, version=version)

    if not package_version.recipe_content:
        return HttpResponse(
            "Recipe not available for this package version",
            status=404,
            content_type='text/plain'
        )

    # Return as plain text with syntax highlighting hint
    response = HttpResponse(package_version.recipe_content, content_type='text/plain')
    response['X-Content-Type-Options'] = 'nosniff'
    return response


def download_extracted_binary(request, package_name, version, binary_id):
    """
    Download a single binary package in extracted format (include/, lib/, bin/, cmake/)
    This is for non-Conan users who want the compiled binaries directly.
    """
    package = get_object_or_404(Package, name=package_name)
    package_version = get_object_or_404(PackageVersion, package=package, version=version)
    binary = get_object_or_404(BinaryPackage, package_version=package_version, package_id=binary_id)

    if not binary.binary_file or not binary.binary_file.name:
        return HttpResponse(
            "Binary file not available for this package",
            status=404,
            content_type='text/plain'
        )

    # Increment download count
    binary.download_count += 1
    binary.save()
    package.download_count += 1
    package.save()

    # Create temporary directory for extraction
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Save the Conan .tar.gz file
        conan_tarball = tmpdir_path / 'package.tar.gz'
        with open(conan_tarball, 'wb') as f:
            f.write(binary.binary_file.read())

        # Extract the Conan tarball
        extract_dir = tmpdir_path / 'extracted'
        extract_dir.mkdir()

        try:
            with tarfile.open(conan_tarball, 'r:gz') as tar:
                tar.extractall(extract_dir)
        except Exception as e:
            return HttpResponse(
                f"Error extracting package: {e}",
                status=500,
                content_type='text/plain'
            )

        # Find the standard C++ directories (include/, lib/, bin/, cmake/)
        # Conan packages typically store these in the package root
        standard_dirs = ['include', 'lib', 'bin', 'cmake']

        # Files to exclude from extraction (Conan metadata and recipe)
        exclude_files = {'conaninfo.txt', 'conanmanifest.txt', 'pkglist.json', 'conan_sources.tgz', 'conanfile.py'}
        # Directories to exclude (Conan internals)
        exclude_dirs = {'e', 'd', 'b'}  # Conan cache structure directories

        # Create output ZIP
        output_zip = tmpdir_path / 'output.zip'
        with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add README
            readme_content = f"""# {package_name} {version} - Extracted Binary

This package has been extracted from Conan format for direct use.

## Package Information
- Name: {package_name}
- Version: {version}
- Package ID: {binary_id}
- Configuration: {binary.get_config_string()}

## Directory Structure

The following directories may be present:
- include/ - Header files
- lib/ - Library files (.a, .so, .dll, .lib)
- bin/ - Binary executables
- cmake/ - CMake package configuration files

## Usage with CMake

If cmake/ directory is present, you can use this package in your CMakeLists.txt:

```cmake
# Add to CMAKE_PREFIX_PATH
list(APPEND CMAKE_PREFIX_PATH "${{CMAKE_CURRENT_SOURCE_DIR}}/path/to/extracted/package")

# Find the package
find_package({package_name} REQUIRED)

# Link against it
target_link_libraries(your_target {package_name}::{package_name})
```

## Manual Usage

If cmake/ is not present, you can manually specify include and library paths:

```cmake
target_include_directories(your_target PRIVATE "${{CMAKE_CURRENT_SOURCE_DIR}}/path/to/include")
target_link_directories(your_target PRIVATE "${{CMAKE_CURRENT_SOURCE_DIR}}/path/to/lib")
target_link_libraries(your_target library_name)
```

Generated by ConanCrates
"""
            zipf.writestr('README.txt', readme_content)

            # Walk through extracted directory and add standard dirs
            # Maps found standard directories to their files: {std_dir: [(src_path, archive_path), ...]}
            found_files = {}

            for root, dirs, files in os.walk(extract_dir):
                for file in files:
                    # Skip Conan metadata files
                    if file in exclude_files:
                        continue

                    file_path = Path(root) / file
                    # Get relative path from extract_dir
                    rel_path = file_path.relative_to(extract_dir)

                    # Skip files that are in export/recipe directories (not in b/.../p/)
                    # Conan binary packages are in b/<hash>/p/ directory
                    parts_str = '/'.join(rel_path.parts)
                    if '/e/' in parts_str or '/d/' in parts_str or '/s/' in parts_str or '/es/' in parts_str:
                        continue  # Skip recipe and metadata directories

                    # Check if this file is in a standard directory (anywhere in the path)
                    parts = rel_path.parts
                    for i, part in enumerate(parts):
                        if part in standard_dirs:
                            # Found a standard directory!
                            # Reorganize path: std_dir/remaining/path
                            std_dir = part
                            remaining_parts = parts[i+1:]  # Everything after the std_dir
                            archive_path = Path(std_dir) / Path(*remaining_parts) if remaining_parts else Path(std_dir)

                            if std_dir not in found_files:
                                found_files[std_dir] = []
                            found_files[std_dir].append((file_path, archive_path))
                            break

            # Add found files to ZIP
            for std_dir, file_list in found_files.items():
                for src_path, archive_path in file_list:
                    # Use ZipInfo to avoid timestamp issues (some files have pre-1980 timestamps)
                    zinfo = zipfile.ZipInfo(str(archive_path))
                    zinfo.date_time = (1980, 1, 1, 0, 0, 0)  # Safe default timestamp
                    with open(src_path, 'rb') as src_f:
                        zipf.writestr(zinfo, src_f.read())

            # If no standard directories found, include everything (except metadata)
            file_count = len(zipf.namelist()) - 1  # -1 for README
            if file_count == 0:
                # Add all files except Conan metadata
                for root, dirs, files in os.walk(extract_dir):
                    for file in files:
                        # Skip Conan metadata files
                        if file in exclude_files:
                            continue

                        file_path = Path(root) / file
                        rel_path = file_path.relative_to(extract_dir)
                        # Use ZipInfo to avoid timestamp issues
                        zinfo = zipfile.ZipInfo(str(rel_path))
                        zinfo.date_time = (1980, 1, 1, 0, 0, 0)
                        with open(file_path, 'rb') as src_f:
                            zipf.writestr(zinfo, src_f.read())

                # Check if we actually added any files
                if len(zipf.namelist()) <= 1:  # Only README
                    # Package has no files!
                    zipf.writestr('NOTE.txt',
                        "This package appears to be empty or header-only with no files.\n"
                        "No compiled binaries, headers, or other artifacts were found.\n"
                        "This may be a metapackage that only declares dependencies.")

        # Return the ZIP file
        with open(output_zip, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/zip')
            response['Content-Disposition'] = f'attachment; filename="{package_name}-{version}-extracted.zip"'
            return response


def list_available_binaries(request, package_name, version):
    """
    List all available binary configurations for a package version.
    Returns JSON with platform configurations available for download.
    """
    package = get_object_or_404(Package, name=package_name)
    package_version = get_object_or_404(PackageVersion, package=package, version=version)

    binaries = package_version.binaries.all()

    if not binaries.exists():
        return JsonResponse({
            'package': package_name,
            'version': version,
            'error': 'No binaries available for this package version',
            'binaries': []
        }, status=404, json_dumps_params={'indent': 2})

    # Group binaries by configuration
    configurations = []
    for binary in binaries:
        config = {
            'os': binary.os,
            'arch': binary.arch,
            'compiler': binary.compiler,
            'compiler_version': binary.compiler_version,
            'build_type': binary.build_type,
            'package_id': binary.package_id,
            'file_size': binary.file_size,
            'download_count': binary.download_count,
            'created_at': binary.created_at.isoformat() if binary.created_at else None,
        }
        configurations.append(config)

    response_data = {
        'package': package_name,
        'version': version,
        'binary_count': len(configurations),
        'binaries': configurations
    }

    return JsonResponse(response_data, json_dumps_params={'indent': 2})


def download_extracted_bundle(request, package_name, version):
    """
    Download package with dependencies in extracted format with interlaced cmake files.
    All packages are extracted and cmake/ directories from all packages are merged
    so users can point to one cmake folder and find all packages.
    """
    package = get_object_or_404(Package, name=package_name)
    package_version = get_object_or_404(PackageVersion, package=package, version=version)

    # Get platform info from query params
    os_filter = request.GET.get('os', 'Linux')
    arch_filter = request.GET.get('arch', 'x86_64')
    compiler_filter = request.GET.get('compiler', 'gcc')
    compiler_version_filter = request.GET.get('compiler_version', '11')
    build_type_filter = request.GET.get('build_type', 'Release')

    # Find the binary for the requested platform
    binaries = package_version.binaries.filter(
        os=os_filter,
        arch=arch_filter,
        compiler=compiler_filter,
        compiler_version=compiler_version_filter,
        build_type=build_type_filter
    )

    if not binaries.exists():
        return HttpResponse(
            f"No binary found for {package_name}/{version} with specified settings",
            status=404,
            content_type='text/plain'
        )

    binary = binaries.first()

    # Collect all binaries to include (main + dependencies)
    binaries_to_extract = [(binary, package_name, version)]
    package_list = [f"{package_name}/{version}"]

    # Process dependency graph
    if binary.dependency_graph:
        graph = binary.dependency_graph
        nodes = graph.get('graph', {}).get('nodes', {})

        for node_id, node in nodes.items():
            if node_id == "0":  # Skip root node
                continue

            ref = node.get('ref', '')
            if '/' not in ref:
                continue

            dep_name, dep_version_with_hash = ref.split('/', 1)
            dep_version = dep_version_with_hash.split('#')[0]
            dep_package_id = node.get('package_id', 'unknown')

            try:
                dep_binary = BinaryPackage.objects.get(
                    package_version__package__name=dep_name,
                    package_version__version=dep_version,
                    package_id=dep_package_id
                )
                binaries_to_extract.append((dep_binary, dep_name, dep_version))
                package_list.append(f"{dep_name}/{dep_version}")
            except BinaryPackage.DoesNotExist:
                pass  # Skip missing dependencies

    # Log bundle generation start
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Generating bundle for {package_name}/{version} with {len(binaries_to_extract)} package(s)")

    # Create temporary directory for extraction
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Directories for interlaced content
        merged_include = tmpdir_path / 'include'
        merged_lib = tmpdir_path / 'lib'
        merged_bin = tmpdir_path / 'bin'
        merged_cmake = tmpdir_path / 'cmake'

        merged_include.mkdir()
        merged_lib.mkdir()
        merged_bin.mkdir()
        merged_cmake.mkdir()

        # Extract each package and merge into common directories
        for idx, (bin_pkg, pkg_name, pkg_ver) in enumerate(binaries_to_extract, 1):
            logger.info(f"  [{idx}/{len(binaries_to_extract)}] Extracting {pkg_name}/{pkg_ver}...")
            if not bin_pkg.binary_file or not bin_pkg.binary_file.name:
                continue

            # Extract this package's tarball
            pkg_tarball = tmpdir_path / f'{pkg_name}-{pkg_ver}.tar.gz'
            with open(pkg_tarball, 'wb') as f:
                f.write(bin_pkg.binary_file.read())

            pkg_extract_dir = tmpdir_path / f'extract_{pkg_name}_{pkg_ver}'
            pkg_extract_dir.mkdir()

            try:
                with tarfile.open(pkg_tarball, 'r:gz') as tar:
                    tar.extractall(pkg_extract_dir)
            except Exception:
                continue  # Skip packages that fail to extract

            # Merge standard directories
            # For include/, create subdirectories per package
            # For lib/ and bin/, put all files together
            # For cmake/, merge all cmake files together
            standard_dirs = ['include', 'lib', 'bin', 'cmake']

            for root, dirs, files in os.walk(pkg_extract_dir):
                for file in files:
                    file_path = Path(root) / file
                    rel_path = file_path.relative_to(pkg_extract_dir)
                    parts = rel_path.parts

                    # Find if this file is in a standard directory (anywhere in path)
                    for i, part in enumerate(parts):
                        if part in standard_dirs:
                            std_dir = part
                            remaining_parts = parts[i+1:]  # Everything after std_dir

                            if std_dir == 'include':
                                # Copy to merged_include/package_name/remaining/path
                                dest = merged_include / pkg_name / Path(*remaining_parts) if remaining_parts else merged_include / pkg_name
                                dest.parent.mkdir(parents=True, exist_ok=True)
                                shutil.copy2(file_path, dest)

                            elif std_dir == 'lib':
                                # Copy to merged_lib/ (just the filename)
                                dest = merged_lib / file
                                if dest.exists():
                                    # Avoid overwriting - add package name prefix
                                    dest = merged_lib / f"{pkg_name}_{file}"
                                shutil.copy2(file_path, dest)

                            elif std_dir == 'bin':
                                # Copy to merged_bin/ (just the filename)
                                dest = merged_bin / file
                                if dest.exists():
                                    dest = merged_bin / f"{pkg_name}_{file}"
                                shutil.copy2(file_path, dest)

                            elif std_dir == 'cmake':
                                # Copy to merged_cmake/remaining/path
                                dest = merged_cmake / Path(*remaining_parts) if remaining_parts else merged_cmake
                                dest.parent.mkdir(parents=True, exist_ok=True)
                                shutil.copy2(file_path, dest)

                            break  # Only match first standard dir in path

        # Create output ZIP
        output_zip = tmpdir_path / 'output.zip'
        with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add README
            readme_content = f"""# {package_name} {version} - Extracted Bundle

This bundle contains {package_name} and all its dependencies extracted for direct use.

## Package Information
- Main Package: {package_name}/{version}
- Platform: {os_filter}/{arch_filter}/{compiler_filter} {compiler_version_filter}
- Build Type: {build_type_filter}

## Included Packages
"""
            for pkg_ref in package_list:
                readme_content += f"- {pkg_ref}\n"

            readme_content += """
## Directory Structure

This bundle uses an "interlaced" structure where all packages are merged:

- **include/** - Header files organized by package (include/package_name/...)
- **lib/** - All library files from all packages (.a, .so, .dll, .lib)
- **bin/** - All binary executables from all packages
- **cmake/** - CMake package configuration files from ALL packages in one directory

## Usage with CMake

The cmake/ directory contains CMake package configs for all included packages.
You can use them in your CMakeLists.txt:

```cmake
# Add the cmake directory to CMAKE_PREFIX_PATH
list(APPEND CMAKE_PREFIX_PATH "${CMAKE_CURRENT_SOURCE_DIR}/path/to/extracted/cmake")

# Now you can find all packages
find_package(package1 REQUIRED)
find_package(package2 REQUIRED)

# Link against them
target_link_libraries(your_target package1::package1 package2::package2)
```

## Manual Usage

```cmake
# Include directories
target_include_directories(your_target PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/path/to/include"
)

# Library directories
target_link_directories(your_target PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/path/to/lib"
)

# Link libraries
target_link_libraries(your_target library_name1 library_name2)
```

Generated by ConanCrates
"""
            zipf.writestr('README.txt', readme_content)

            # Add all merged directories to ZIP
            for merged_dir in [merged_include, merged_lib, merged_bin, merged_cmake]:
                if merged_dir.exists():
                    for root, dirs, files in os.walk(merged_dir):
                        for file in files:
                            file_path = Path(root) / file
                            # Path relative to tmpdir
                            rel_path = file_path.relative_to(tmpdir_path)
                            # Use ZipInfo to avoid timestamp issues
                            zinfo = zipfile.ZipInfo(str(rel_path))
                            zinfo.date_time = (1980, 1, 1, 0, 0, 0)
                            with open(file_path, 'rb') as src_f:
                                zipf.writestr(zinfo, src_f.read())

        # Return the ZIP file
        with open(output_zip, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/zip')
            response['Content-Disposition'] = f'attachment; filename="{package_name}-{version}-extracted-bundle.zip"'
            return response


def download_rust_crate(request, package_name, version, package_id):
    """
    Download the Rust crate (.crate file) for a specific binary package.
    The .crate file is a tar.gz archive containing the Rust -sys crate.
    """
    package = get_object_or_404(Package, name=package_name)
    package_version = get_object_or_404(PackageVersion, package=package, version=version)

    # Find the binary package
    binary = get_object_or_404(BinaryPackage, package_version=package_version, package_id=package_id)

    # Check if rust crate file exists
    if not binary.rust_crate_file or not binary.rust_crate_file.name:
        return HttpResponse(
            f"Rust crate not available for {package_name}/{version} (package_id: {package_id})",
            status=404,
            content_type='text/plain'
        )

    # Increment download count
    binary.download_count += 1
    binary.save(update_fields=['download_count'])

    # Return the .crate file
    response = HttpResponse(binary.rust_crate_file.read(), content_type='application/gzip')
    crate_name = f"{package_name.replace('_', '-')}-sys-{version}.crate"
    response['Content-Disposition'] = f'attachment; filename="{crate_name}"'
    return response
