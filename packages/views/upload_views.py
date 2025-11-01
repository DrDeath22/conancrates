"""
Upload views for ConanCrates

Implements Conan V2 REST API for package uploads
"""
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.core.files.base import ContentFile
from packages.models import Package, PackageVersion, BinaryPackage
import json
import hashlib


@csrf_exempt
@require_http_methods(["GET"])
def ping(request):
    """
    Ping endpoint - Conan client uses this to check server availability
    """
    return JsonResponse({
        "status": "ok",
        "version": "1.0.0",
        "server": "ConanCrates"
    })


@csrf_exempt
@require_http_methods(["GET"])
def check_credentials(request):
    """
    Check credentials endpoint - Conan uses this to verify authentication
    """
    # For now, we'll accept all requests
    # TODO: Implement proper authentication
    return JsonResponse({
        "authenticated": True,
        "user": request.user.username if request.user.is_authenticated else "anonymous"
    })


@csrf_exempt
@require_http_methods(["POST"])
def upload_recipe(request, package_name, package_version):
    """
    Upload recipe (conanfile.py, conandata.yml, etc.)

    URL: /v2/conans/{package_name}/{package_version}/upload
    """
    try:
        # Get or create package
        package, created = Package.objects.get_or_create(
            name=package_name,
            defaults={
                'description': f'Package {package_name}',
                'license': 'Unknown'
            }
        )

        # Get or create package version
        version, created = PackageVersion.objects.get_or_create(
            package=package,
            version=package_version,
            defaults={
                'uploaded_by': request.user if request.user.is_authenticated else None
            }
        )

        return JsonResponse({
            "status": "ok",
            "message": f"Recipe {package_name}/{package_version} uploaded successfully"
        })

    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def upload_package(request, package_name, package_version, package_id):
    """
    Upload binary package

    URL: /v2/conans/{package_name}/{package_version}/packages/{package_id}/upload
    """
    try:
        # Get package version
        package = get_object_or_404(Package, name=package_name)
        version = get_object_or_404(PackageVersion, package=package, version=package_version)

        # Get or create binary package
        binary, created = BinaryPackage.objects.get_or_create(
            package_version=version,
            package_id=package_id,
            defaults={
                'os': 'Linux',  # TODO: Extract from package_id or metadata
                'arch': 'x86_64',
                'compiler': 'gcc',
                'compiler_version': '11',
                'build_type': 'Release'
            }
        )

        # Check if file was uploaded
        if 'file' in request.FILES:
            uploaded_file = request.FILES['file']

            # Calculate SHA256
            sha256_hash = hashlib.sha256()
            for chunk in uploaded_file.chunks():
                sha256_hash.update(chunk)

            # Save file
            binary.binary_file.save(
                f'{package_name}-{package_version}-{package_id}.tar.gz',
                uploaded_file,
                save=False
            )
            binary.sha256 = sha256_hash.hexdigest()
            binary.file_size = uploaded_file.size
            binary.save()

            return JsonResponse({
                "status": "ok",
                "message": f"Binary {package_name}/{package_version}:{package_id} uploaded successfully",
                "sha256": binary.sha256,
                "size": binary.file_size
            })
        else:
            return JsonResponse({
                "status": "error",
                "message": "No file provided"
            }, status=400)

    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def get_recipe_manifest(request, package_name, package_version):
    """
    Get recipe manifest - list of files in recipe

    URL: /v2/conans/{package_name}/{package_version}/recipe/manifest
    """
    try:
        package = get_object_or_404(Package, name=package_name)
        version = get_object_or_404(PackageVersion, package=package, version=package_version)

        # Return empty manifest for now
        # TODO: Implement proper recipe file tracking
        return JsonResponse({
            "files": {}
        })

    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": str(e)
        }, status=404)


@csrf_exempt
@require_http_methods(["GET"])
def search_packages(request):
    """
    Search packages endpoint

    URL: /v2/conans/search
    """
    query = request.GET.get('q', '')

    packages = Package.objects.filter(name__icontains=query)[:20]

    results = []
    for pkg in packages:
        for version in pkg.versions.all():
            results.append({
                "recipe": {
                    "id": f"{pkg.name}/{version.version}"
                }
            })

    return JsonResponse({
        "results": results
    })
