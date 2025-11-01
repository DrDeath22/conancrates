from django.shortcuts import render, get_object_or_404
from django.db.models import Count
from django.core.paginator import Paginator
from packages.models import Topic


def topic_list(request):
    """List all topics"""
    topics = Topic.objects.annotate(pkg_count=Count('packages')).order_by('-pkg_count')

    context = {
        'topics': topics,
    }
    return render(request, 'packages/topic_list.html', context)


def topic_detail(request, slug):
    """Show packages for a specific topic"""
    topic = get_object_or_404(Topic, slug=slug)
    packages = topic.packages.all().order_by('name')

    # Pagination
    paginator = Paginator(packages, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'topic': topic,
        'page_obj': page_obj,
    }
    return render(request, 'packages/topic_detail.html', context)
