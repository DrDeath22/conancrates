"""
Simple unified upload API for ConanCrates

Single endpoint that accepts both recipe (conanfile.py) and binary (.tar.gz) files.
"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.files.base import ContentFile
from packages.models import Package, PackageVersion, BinaryPackage
import json
import hashlib
import tarfile
import io
import re


def parse_conanfile(recipe_content):
    """
    Extract metadata from conanfile.py content.

    Returns dict with:
    - name: package name
    - version: package version
    - description: package description
    - license: package license
    - dependencies: list of dependencies
    """
    metadata = {
        'name': None,
        'version': None,
        'description': '',
        'license': 'Unknown',
        'dependencies': []
    }

    # Extract name
    name_match = re.search(r'name\s*=\s*["\']([^"\']+)["\']', recipe_content)
    if name_match:
        metadata['name'] = name_match.group(1)

    # Extract version
    version_match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', recipe_content)
    if version_match:
        metadata['version'] = version_match.group(1)

    # Extract description
    desc_match = re.search(r'description\s*=\s*["\']([^"\']+)["\']', recipe_content)
    if desc_match:
        metadata['description'] = desc_match.group(1)

    # Extract license
    license_match = re.search(r'license\s*=\s*["\']([^"\']+)["\']', recipe_content)
    if license_match:
        metadata['license'] = license_match.group(1)

    # Extract dependencies (basic parsing - looks for requires = [...])
    # This is simplified and won't handle all cases
    requires_match = re.search(r'requires\s*=\s*\[(.*?)\]', recipe_content, re.DOTALL)
    if requires_match:
        requires_str = requires_match.group(1)
        # Extract quoted strings
        deps = re.findall(r'["\']([^"\']+)["\']', requires_str)
        metadata['dependencies'] = deps

    return metadata


def extract_conaninfo(binary_file):
    """
    Extract conaninfo.txt from binary .tar.gz file.

    Returns dict with:
    - os: operating system
    - arch: architecture
    - compiler: compiler name
    - compiler_version: compiler version
    - build_type: build type (Release, Debug, etc.)
    """
    settings = {
        'os': 'Linux',
        'arch': 'x86_64',
        'compiler': 'gcc',
        'compiler_version': '11',
        'build_type': 'Release'
    }

    try:
        # Reset file pointer
        binary_file.seek(0)

        # Open tar.gz
        with tarfile.open(fileobj=binary_file, mode='r:gz') as tar:
            # Look for conaninfo.txt
            for member in tar.getmembers():
                if member.name.endswith('conaninfo.txt'):
                    f = tar.extractfile(member)
                    if f:
                        content = f.read().decode('utf-8')

                        # Parse conaninfo.txt
                        # Format:
                        # [settings]
                        # os=Linux
                        # arch=x86_64
                        # ...

                        for line in content.split('\n'):
                            line = line.strip()
                            if '=' in line:
                                key, value = line.split('=', 1)
                                key = key.strip()
                                value = value.strip()

                                if key == 'os':
                                    settings['os'] = value
                                elif key == 'arch':
                                    settings['arch'] = value
                                elif key == 'compiler':
                                    settings['compiler'] = value
                                elif key == 'compiler.version':
                                    settings['compiler_version'] = value
                                elif key == 'build_type':
                                    settings['build_type'] = value
                        break
    except Exception as e:
        # If we can't extract, use defaults
        print(f"Warning: Could not extract conaninfo.txt: {e}")

    # Reset file pointer again for later use
    binary_file.seek(0)

    return settings


@csrf_exempt
@require_http_methods(["POST"])
def upload_package(request):
    """
    Unified package upload endpoint.

    Accepts multipart form data with:
    - recipe: conanfile.py file
    - binary: .tar.gz binary file
    - package_id: (optional) Real Conan package_id from client
    - dependency_graph: (optional) JSON string of conan graph info output

    Returns JSON response with status and package info.
    """
    try:
        # Check if both files are present
        if 'recipe' not in request.FILES:
            return JsonResponse({
                'status': 'error',
                'message': 'Missing recipe file (conanfile.py)'
            }, status=400)

        if 'binary' not in request.FILES:
            return JsonResponse({
                'status': 'error',
                'message': 'Missing binary file (.tar.gz)'
            }, status=400)

        recipe_file = request.FILES['recipe']
        binary_file = request.FILES['binary']

        # Read recipe content
        recipe_content = recipe_file.read().decode('utf-8')

        # Get package name and version from POST data (sent by CLI tool)
        package_name = request.POST.get('package_name')
        version = request.POST.get('version')

        if not package_name or not version:
            return JsonResponse({
                'status': 'error',
                'message': 'Missing required fields: package_name and version must be provided in POST data'
            }, status=400)

        # Parse conanfile for description and license (still useful)
        metadata = parse_conanfile(recipe_content)
        description = metadata.get('description', '')
        license_info = metadata.get('license', 'Unknown')

        # Extract settings from binary
        settings = extract_conaninfo(binary_file)

        # Get or create package
        package, created = Package.objects.get_or_create(
            name=package_name,
            defaults={
                'description': description,
                'license': license_info
            }
        )

        # Update package if it already exists
        if not created and description:
            package.description = description
            package.license = license_info
            package.save()

        # Get conan_version from client if provided
        conan_version = request.POST.get('conan_version', 'unknown')

        # Get or create package version
        package_version, created = PackageVersion.objects.get_or_create(
            package=package,
            version=version,
            defaults={
                'recipe_content': recipe_content,
                'description': description,
                'conan_version': conan_version,
                'uploaded_by': request.user if request.user.is_authenticated else None
            }
        )

        # Update recipe content if version already exists
        if not created:
            package_version.recipe_content = recipe_content
            package_version.description = description
            package_version.conan_version = conan_version
            package_version.save()

        # Get package_id from client if provided, otherwise generate from settings
        package_id = request.POST.get('package_id')
        if not package_id:
            # Fallback: Generate package_id from settings hash
            # NOTE: This is NOT the real Conan package_id, just a placeholder
            package_id_str = f"{settings['os']}-{settings['arch']}-{settings['compiler']}-{settings['compiler_version']}-{settings['build_type']}"
            package_id = hashlib.md5(package_id_str.encode()).hexdigest()[:16]

        # Get dependency_graph from client if provided
        dependency_graph = {}
        dependency_graph_json = request.POST.get('dependency_graph')
        if dependency_graph_json:
            try:
                dependency_graph = json.loads(dependency_graph_json)
            except json.JSONDecodeError:
                print(f"Warning: Could not parse dependency_graph JSON")

        # Calculate SHA256 of binary
        binary_file.seek(0)
        sha256_hash = hashlib.sha256()
        for chunk in binary_file.chunks():
            sha256_hash.update(chunk)
        sha256 = sha256_hash.hexdigest()

        # Get or create binary package
        binary, created = BinaryPackage.objects.get_or_create(
            package_version=package_version,
            package_id=package_id,
            defaults={
                'os': settings['os'],
                'arch': settings['arch'],
                'compiler': settings['compiler'],
                'compiler_version': settings['compiler_version'],
                'build_type': settings['build_type'],
                'sha256': sha256,
                'file_size': binary_file.size,
                'dependency_graph': dependency_graph
            }
        )

        # Save binary file to MinIO
        binary_file.seek(0)
        binary.binary_file.save(
            f"{package_name}-{version}-{package_id}.tar.gz",
            binary_file,
            save=False
        )
        binary.sha256 = sha256
        binary.file_size = binary_file.size
        binary.dependency_graph = dependency_graph  # Update graph even if binary exists
        binary.save()

        # Create dependencies from metadata (if parsed from requires field)
        from packages.models import Dependency
        for dep_str in metadata.get('dependencies', []):
            # Parse dependency string (e.g., "boost/1.81.0")
            if '/' in dep_str:
                dep_name, dep_version = dep_str.split('/', 1)
                dep_package, _ = Package.objects.get_or_create(
                    name=dep_name,
                    defaults={'description': f'Dependency: {dep_name}', 'license': 'Unknown'}
                )
                dep_version_obj, _ = PackageVersion.objects.get_or_create(
                    package=dep_package,
                    version=dep_version
                )

                Dependency.objects.get_or_create(
                    package_version=package_version,
                    depends_on=dep_version_obj
                )

        return JsonResponse({
            'status': 'success',
            'message': f'Package {package_name}/{version} uploaded successfully',
            'package': {
                'name': package_name,
                'version': version,
                'package_id': package_id,
                'sha256': sha256,
                'size': binary_file.size,
                'settings': settings
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)
