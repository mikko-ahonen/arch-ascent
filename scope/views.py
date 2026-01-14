"""Views for the scope app - first step before vision."""
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from dependencies.models import Project
from .classifier import (
    STATUS_COLORS,
    get_status_counts, get_connectivity_counts,
    classify_project,
)


def scoping(request):
    """
    Main scoping view - the first step before vision.

    Allows users to filter and select which projects to focus on.
    """
    projects = Project.objects.select_related('group').prefetch_related('tags').order_by('name')

    # Get counts for display
    status_counts = get_status_counts()
    connectivity_counts = get_connectivity_counts()

    # Classify each project
    projects_with_status = []
    for project in projects:
        status = classify_project(project)
        projects_with_status.append({
            'project': project,
            'status': status,
        })

    context = {
        'projects': projects_with_status,
        'project_count': projects.count(),
        'status_counts': status_counts,
        'status_colors': STATUS_COLORS,
        'connectivity_counts': connectivity_counts,
    }

    return render(request, 'scope/scoping.html', context)


@require_POST
def update_project_description(request, project_id):
    """Update a project's description."""
    import json
    project = get_object_or_404(Project, id=project_id)
    data = json.loads(request.body) if request.body else {}
    project.description = data.get('description', '')
    project.save(update_fields=['description'])
    return JsonResponse({'success': True, 'description': project.description})


@require_POST
def bulk_update_status(request):
    """Update status for multiple projects."""
    import json
    data = json.loads(request.body) if request.body else {}
    project_ids = data.get('project_ids', [])
    status = data.get('status', '')

    valid_statuses = [choice[0] for choice in Project.STATUS_CHOICES]
    if status not in valid_statuses:
        return JsonResponse({'error': 'Invalid status'}, status=400)

    updated = Project.objects.filter(id__in=project_ids).update(status=status)
    return JsonResponse({'success': True, 'updated': updated})


def get_all_tags(request):
    """Get all unique tags across projects."""
    from taggit.models import Tag
    tags = list(Tag.objects.values_list('name', flat=True).order_by('name'))
    return JsonResponse({'tags': tags})


@require_POST
def bulk_update_tags(request):
    """Add or remove a tag from multiple projects."""
    import json
    data = json.loads(request.body) if request.body else {}
    project_ids = data.get('project_ids', [])
    tag = data.get('tag', '').strip()
    action = data.get('action', 'add')

    if not tag:
        return JsonResponse({'error': 'Tag is required'}, status=400)

    projects = Project.objects.filter(id__in=project_ids)

    if action == 'add':
        for project in projects:
            project.tags.add(tag)
    elif action == 'remove':
        for project in projects:
            project.tags.remove(tag)
    else:
        return JsonResponse({'error': 'Invalid action'}, status=400)

    return JsonResponse({'success': True, 'count': projects.count()})
