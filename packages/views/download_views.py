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
    Uses Conan's actual dependency resolution for accurate results.
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
        'conan_available': check_conan_available(),
        'conan_version': get_conan_version()
    }

    # Check if Conan is available
    if not check_conan_available():
        preview_data['error'] = (
            "Conan is not available. Install it with: pip install conan. "
            "Bundle generation requires Conan for accurate dependency resolution."
        )
        preview_data['resolution_method'] = 'unavailable'
        return JsonResponse(preview_data, status=503, json_dumps_params={'indent': 2})

    try:
        # Use Conan to resolve dependencies
        resolution = resolve_dependencies(
            package_name=package_name,
            version=version,
            os_name=os_filter,
            arch=arch_filter,
            compiler=compiler_filter,
            compiler_version=compiler_version_filter,
            build_type=build_type_filter
        )

        if not resolution.get('success'):
            preview_data['error'] = resolution.get('error', 'Unknown error')
            preview_data['resolution_method'] = 'error'
            return JsonResponse(preview_data, status=500, json_dumps_params={'indent': 2})

        # Process resolved packages
        for pkg in resolution.get('packages', []):
            pkg_name = pkg['name']
            pkg_version = pkg['version']
            pkg_id = pkg.get('package_id', 'unknown')

            # Look up this package in our database
            try:
                db_package = Package.objects.get(name=pkg_name)
                db_version = PackageVersion.objects.get(package=db_package, version=pkg_version)

                # Find matching binary
                binaries = db_version.binaries.filter(
                    os=os_filter,
                    arch=arch_filter,
                    compiler=compiler_filter,
                    build_type=build_type_filter
                )

                if binaries.exists():
                    binary = binaries.first()
                    preview_data['files'].append({
                        'package': pkg_name,
                        'version': pkg_version,
                        'type': 'main' if pkg_name == package_name else 'dependency',
                        'package_id': pkg_id,
                        'config': binary.get_config_string(),
                        'size': binary.file_size
                    })
                    preview_data['total_size'] += binary.file_size
                    preview_data['file_count'] += 1
                else:
                    # Binary not in database but resolved by Conan
                    preview_data['files'].append({
                        'package': pkg_name,
                        'version': pkg_version,
                        'type': 'main' if pkg_name == package_name else 'dependency',
                        'package_id': pkg_id,
                        'config': f"OS: {os_filter}, Arch: {arch_filter}, Compiler: {compiler_filter}",
                        'size': 0,
                        'note': 'Binary not in local database'
                    })

            except (Package.DoesNotExist, PackageVersion.DoesNotExist):
                # Package resolved by Conan but not in our database
                preview_data['files'].append({
                    'package': pkg_name,
                    'version': pkg_version,
                    'type': 'dependency',
                    'package_id': pkg_id,
                    'config': f"OS: {os_filter}, Arch: {arch_filter}, Compiler: {compiler_filter}",
                    'size': 0,
                    'note': 'Package not in local database'
                })

        preview_data['resolution_method'] = 'conan'

    except ConanError as e:
        preview_data['error'] = f"Conan resolution failed: {str(e)}"
        preview_data['resolution_method'] = 'error'
        return JsonResponse(preview_data, status=500, json_dumps_params={'indent': 2})

    return JsonResponse(preview_data, json_dumps_params={'indent': 2})


def download_bundle(request, package_name, version):
    """
    Download package with all its dependencies as a ZIP bundle
    Uses Conan's actual dependency resolution for 100% accurate bundles.
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
        'conan_available': check_conan_available(),
        'conan_version': get_conan_version()
    }

    binaries_to_bundle = []

    # Check if Conan is available
    if not check_conan_available():
        error_response = {
            'error': (
                "Conan is not available. Install it with: pip install conan. "
                "Bundle generation requires Conan for accurate dependency resolution."
            ),
            'package': package_name,
            'version': version,
            'conan_available': False,
            'resolution_method': 'unavailable'
        }
        return JsonResponse(error_response, status=503, json_dumps_params={'indent': 2})

    try:
        # Use Conan to resolve dependencies
        resolution = resolve_dependencies(
            package_name=package_name,
            version=version,
            os_name=os_filter,
            arch=arch_filter,
            compiler=compiler_filter,
            compiler_version=compiler_version_filter,
            build_type=build_type_filter
        )

        if not resolution.get('success'):
            error_msg = resolution.get('error', 'Unknown error')
            error_response = {
                'error': f"Conan resolution failed: {error_msg}",
                'package': package_name,
                'version': version,
                'platform': bundle_metadata['platform'],
                'conan_available': True,
                'conan_version': bundle_metadata['conan_version'],
                'resolution_method': 'error'
            }
            return JsonResponse(error_response, status=500, json_dumps_params={'indent': 2})

        # Process resolved packages
        for pkg in resolution.get('packages', []):
            pkg_name = pkg['name']
            pkg_version = pkg['version']
            pkg_id = pkg.get('package_id', 'unknown')

            # Look up this package in our database
            try:
                db_package = Package.objects.get(name=pkg_name)
                db_version = PackageVersion.objects.get(package=db_package, version=pkg_version)

                # Find matching binary
                binaries = db_version.binaries.filter(
                    os=os_filter,
                    arch=arch_filter,
                    compiler=compiler_filter,
                    build_type=build_type_filter
                )

                if binaries.exists():
                    binary = binaries.first()
                    binaries_to_bundle.append((binary, pkg_name, pkg_version))
                    bundle_metadata['contents'].append({
                        'package': pkg_name,
                        'version': pkg_version,
                        'type': 'main' if pkg_name == package_name else 'dependency',
                        'package_id': pkg_id,
                        'config': binary.get_config_string()
                    })
                else:
                    # Binary resolved by Conan but not in database
                    bundle_metadata['contents'].append({
                        'package': pkg_name,
                        'version': pkg_version,
                        'type': 'main' if pkg_name == package_name else 'dependency',
                        'package_id': pkg_id,
                        'config': f"OS: {os_filter}, Arch: {arch_filter}, Compiler: {compiler_filter}",
                        'note': 'Binary not in local database - not included in bundle'
                    })

            except (Package.DoesNotExist, PackageVersion.DoesNotExist):
                # Package resolved by Conan but not in our database
                bundle_metadata['contents'].append({
                    'package': pkg_name,
                    'version': pkg_version,
                    'type': 'dependency',
                    'package_id': pkg_id,
                    'config': f"OS: {os_filter}, Arch: {arch_filter}, Compiler: {compiler_filter}",
                    'note': 'Package not in local database - not included in bundle'
                })

        bundle_metadata['resolution_method'] = 'conan'

    except ConanError as e:
        error_response = {
            'error': f"Conan resolution failed: {str(e)}",
            'package': package_name,
            'version': version,
            'platform': bundle_metadata['platform'],
            'conan_available': True,
            'conan_version': bundle_metadata['conan_version'],
            'resolution_method': 'error'
        }
        return JsonResponse(error_response, status=500, json_dumps_params={'indent': 2})

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

            # Add binaries (or placeholders in prototype)
            for binary, pkg_name, pkg_ver in binaries_to_bundle:
                # In production: zipf.write(binary.binary_file.path, f'{pkg_name}/{pkg_name}-{pkg_ver}.tar.gz')
                # For prototype: add placeholder
                placeholder = f"""Package: {pkg_name}/{pkg_ver}
Binary ID: {binary.package_id}
Configuration: {binary.get_config_string()}
Size: {binary.file_size} bytes

This is a placeholder file.
In production, this would be the actual binary package.
"""
                zipf.writestr(
                    f'{pkg_name}/{pkg_name}-{pkg_ver}-{binary.package_id}.txt',
                    placeholder
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
