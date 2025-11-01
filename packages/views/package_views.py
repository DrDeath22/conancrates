from django.shortcuts import render, get_object_or_404
from django.db.models import Q
from django.core.paginator import Paginator
from packages.models import Package, PackageVersion, Topic


def package_list(request):
    """List all packages with search and filtering"""
    packages = Package.objects.all()

    # Search
    search_query = request.GET.get('q', '')
    if search_query:
        packages = packages.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(topics__icontains=search_query)
        )

    # Filter by topic
    topic_slug = request.GET.get('topic', '')
    if topic_slug:
        topic = get_object_or_404(Topic, slug=topic_slug)
        packages = topic.packages.all()
    else:
        topic = None

    # Filter by license
    license_filter = request.GET.get('license', '')
    if license_filter:
        packages = packages.filter(license=license_filter)

    # Order by
    order_by = request.GET.get('order', '-created_at')
    packages = packages.order_by(order_by)

    # Pagination
    paginator = Paginator(packages, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Get all unique licenses for filter dropdown
    all_licenses = Package.objects.values_list('license', flat=True).distinct().exclude(license='')

    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'current_topic': topic,
        'current_license': license_filter,
        'current_order': order_by,
        'all_licenses': all_licenses,
    }
    return render(request, 'packages/package_list.html', context)


def package_detail(request, package_name):
    """Show details of a specific package"""
    package = get_object_or_404(Package, name=package_name)
    versions = package.versions.all().order_by('-created_at')

    # Get selected version or latest
    version_str = request.GET.get('version', '')
    if version_str:
        selected_version = get_object_or_404(PackageVersion, package=package, version=version_str)
    else:
        selected_version = versions.first()

    # Get binaries for selected version
    binaries = None
    dependencies = None
    if selected_version:
        binaries = selected_version.binaries.all()
        dependencies = selected_version.dependencies.select_related('requires_package')

    context = {
        'package': package,
        'versions': versions,
        'selected_version': selected_version,
        'binaries': binaries,
        'dependencies': dependencies,
        'topics': package.get_topics_list(),
    }
    return render(request, 'packages/package_detail.html', context)
