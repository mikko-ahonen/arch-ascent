"""
Django component for expanding from a node by degree.
"""
import json

from django_components import Component, register
from django.http import HttpRequest, JsonResponse
from django.db.models import Q
from django.views.decorators.csrf import csrf_exempt

from dependencies.models import Project, Dependency
from dependencies.components.graph.graph import traverse_graph


@register("node_expander")
class NodeExpander(Component):
    template_name = "node_expander/node_expander.html"

    def get_context_data(self):
        return {}


def build_adjacency_directed() -> dict[str, set[str]]:
    """Build directed adjacency list from dependencies."""
    adjacency: dict[str, set[str]] = {}

    # Add all projects as nodes (even if no dependencies)
    for project in Project.objects.all():
        adjacency.setdefault(project.key, set())

    # Add edges from dependencies
    for dep in Dependency.objects.select_related('source', 'target').all():
        adjacency.setdefault(dep.source.key, set()).add(dep.target.key)

    return adjacency


@csrf_exempt
def node_search(request: HttpRequest) -> JsonResponse:
    """Search for projects by name/key for autocomplete."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    data = json.loads(request.body) if request.body else {}
    query = data.get('query', '').strip()

    if not query or len(query) < 2:
        return JsonResponse({'results': []})

    projects = Project.objects.filter(
        Q(name__icontains=query) |
        Q(key__icontains=query) |
        Q(basename__icontains=query)
    ).order_by('basename', 'name')[:15]

    results = [
        {
            'key': p.key,
            'name': p.name,
            'basename': p.basename or p.name,
        }
        for p in projects
    ]

    return JsonResponse({'results': results})


@csrf_exempt
def expand_node(request: HttpRequest) -> JsonResponse:
    """Find all nodes within N degrees of a starting node."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    data = json.loads(request.body) if request.body else {}

    node_key = data.get('node_key')
    if not node_key:
        return JsonResponse({'error': 'node_key required'}, status=400)

    # Validate node exists
    if not Project.objects.filter(key=node_key).exists():
        return JsonResponse({'error': 'Node not found'}, status=404)

    # Parse and validate parameters
    try:
        degree = int(data.get('degree', 1))
        degree = max(1, min(degree, 10))  # Clamp 1-10
    except (ValueError, TypeError):
        degree = 1

    direction = data.get('direction', 'both')
    if direction not in ('downstream', 'upstream', 'both'):
        direction = 'both'

    # Build adjacency and traverse
    adjacency = build_adjacency_directed()
    result = traverse_graph(
        adjacency,
        node_key,
        direction=direction,
        algorithm='bfs',
        max_depth=degree,
    )

    # Flatten results from all depths
    all_keys = []
    for depth_nodes in result.values():
        all_keys.extend(depth_nodes)

    # Get project IDs for the keys
    projects = Project.objects.filter(key__in=all_keys)
    project_ids = list(projects.values_list('id', flat=True))
    project_keys = list(projects.values_list('key', flat=True))

    return JsonResponse({
        'start_node': node_key,
        'direction': direction,
        'degree': degree,
        'project_keys': project_keys,
        'project_ids': project_ids,
        'count': len(project_keys),
        'by_depth': {str(k): v for k, v in result.items()},
    })
