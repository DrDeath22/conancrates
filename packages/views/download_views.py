"""
Views for downloading packages and binaries
"""
import os
import json
import zipfile
import tempfile
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
