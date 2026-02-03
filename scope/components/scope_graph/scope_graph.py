"""
Django component for scope graph visualization.

Shows filtered projects in a Cytoscape.js graph with selection sync.
"""
import json
from django_components import Component, register
from django.http import JsonResponse
from django.urls import path
from django.views.decorators.csrf import csrf_exempt

from dependencies.models import Project, Dependency
from dependencies.components.graph.graph import (
    DependencyGraph,
    get_cycle_edges,
    enumerate_cycles,
)


def get_graph_data_for_keys(project_keys: list[str]) -> dict:
    """Build Cytoscape-compatible graph data for given project keys."""
    nodes = []
    edges = []
    has_positions = False

    # Load projects
    projects = {p.key: p for p in Project.objects.filter(key__in=project_keys)}

    if not projects:
        return {"nodes": [], "edges": [], "has_positions": False, "cycle_edge_count": 0}

    # Add project nodes
    for key, project in projects.items():
        node_data = {
            "data": {
                "id": project.key,
                "label": project.basename or project.name,
                "description": project.description,
            }
        }
        if project.position_x is not None and project.position_y is not None:
            node_data["position"] = {"x": project.position_x, "y": project.position_y}
            has_positions = True
        nodes.append(node_data)

    # Add dependencies between these projects
    project_ids = [p.id for p in projects.values()]
    deps = Dependency.objects.filter(
        source_id__in=project_ids,
        target_id__in=project_ids
    ).select_related('source', 'target')

    # Build adjacency for selected nodes only (for performance)
    adjacency: dict[str, set[str]] = {}
    for dep in deps:
        adjacency.setdefault(dep.source.key, set()).add(dep.target.key)

    # Compute transitive and cycle edges for selected nodes
    transitive_edges = DependencyGraph._find_transitive_edges(adjacency)
    cycle_edges = get_cycle_edges(adjacency)

    # Don't enumerate cycles here - do it lazily via separate endpoint
    # This avoids expensive computation on every graph load

    for dep in deps:
        edge_key = (dep.source.key, dep.target.key)
        edges.append({
            "data": {
                "id": f"{dep.source.key}->{dep.target.key}",
                "source": dep.source.key,
                "target": dep.target.key,
                "scope": dep.scope,
                "transitive": edge_key in transitive_edges,
                "inCycle": edge_key in cycle_edges,
            }
        })

    return {
        "nodes": nodes,
        "edges": edges,
        "has_positions": has_positions,
        "cycle_edge_count": len(cycle_edges),
    }


@csrf_exempt
def scope_graph_data(request):
    """Return graph data for specified project keys (POST with JSON body)."""
    if request.method != 'POST':
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        body = json.loads(request.body)
        project_keys = body.get('keys', [])
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"nodes": [], "edges": [], "has_positions": False, "cycle_edge_count": 0})

    if not project_keys:
        return JsonResponse({"nodes": [], "edges": [], "has_positions": False, "cycle_edge_count": 0})

    # Build graph data for these projects
    data = get_graph_data_for_keys(project_keys)
    return JsonResponse(data)


@csrf_exempt
def scope_graph_cycles(request):
    """Lazily enumerate individual cycles for the given project keys."""
    if request.method != 'POST':
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        body = json.loads(request.body)
        project_keys = body.get('keys', [])
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"cycles": []})

    if not project_keys:
        return JsonResponse({"cycles": []})

    # Load projects and build adjacency
    projects = {p.key: p for p in Project.objects.filter(key__in=project_keys)}
    if not projects:
        return JsonResponse({"cycles": []})

    project_ids = [p.id for p in projects.values()]
    deps = Dependency.objects.filter(
        source_id__in=project_ids,
        target_id__in=project_ids
    ).select_related('source', 'target')

    adjacency: dict[str, set[str]] = {}
    for dep in deps:
        adjacency.setdefault(dep.source.key, set()).add(dep.target.key)

    # Enumerate cycles with conservative limits for performance
    cycles = enumerate_cycles(adjacency, max_cycles=25, max_length=8, timeout=1.0)

    # Debug: validate all cycle edges exist
    invalid_cycles = []
    for i, cycle in enumerate(cycles):
        for j in range(len(cycle)):
            source = cycle[j]
            target = cycle[(j + 1) % len(cycle)]
            if target not in adjacency.get(source, set()):
                invalid_cycles.append({
                    'index': i,
                    'cycle': cycle,
                    'missing_edge': f'{source}->{target}'
                })
                break

    return JsonResponse({
        "cycles": cycles,
        "debug": {
            "total_cycles": len(cycles),
            "invalid_cycles": invalid_cycles,
            "adjacency_node_count": len(adjacency),
            "adjacency_edge_count": sum(len(v) for v in adjacency.values()),
        }
    })


@register("scope_graph")
class ScopeGraph(Component):
    template_name = "scope_graph/scope_graph.html"

    def get_context_data(self, height="500px"):
        return {
            "height": height,
        }

    @classmethod
    def get_urls(cls):
        return [
            path('scope-graph/data/', scope_graph_data, name='scope_graph_data'),
            path('scope-graph/cycles/', scope_graph_cycles, name='scope_graph_cycles'),
        ]
