from django.shortcuts import render
from django.db.models import Count
from packages.models import Package, PackageVersion, BinaryPackage, Topic


def index(request):
    """Homepage - show recent packages and statistics"""
    recent_packages = Package.objects.all().order_by('-created_at')[:6]
    total_packages = Package.objects.count()
    total_versions = PackageVersion.objects.count()
    total_binaries = BinaryPackage.objects.count()
    popular_topics = Topic.objects.annotate(pkg_count=Count('packages')).order_by('-pkg_count')[:10]

    context = {
        'recent_packages': recent_packages,
        'total_packages': total_packages,
        'total_versions': total_versions,
        'total_binaries': total_binaries,
        'popular_topics': popular_topics,
    }
    return render(request, 'packages/index.html', context)
