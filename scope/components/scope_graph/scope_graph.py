"""
Django component for scope graph visualization.

Shows filtered projects in a Cytoscape.js graph with selection sync.
"""
import json
from django_components import Component, register
from django.http import JsonResponse
from django.urls import path

from dependencies.models import Project, Dependency
from dependencies.components.graph.graph import (
    DependencyGraph,
    get_cycle_edges,
)


def get_graph_data_for_keys(project_keys: list[str]) -> dict:
    """Build Cytoscape-compatible graph data for given project keys."""
    nodes = []
    edges = []
    has_positions = False

    # Load projects
    projects = {p.key: p for p in Project.objects.filter(key__in=project_keys)}

    if not projects:
        return {"nodes": [], "edges": [], "has_positions": False}

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

    # Build adjacency for transitive/cycle detection
    adjacency: dict[str, set[str]] = {}
    for dep in deps:
        adjacency.setdefault(dep.source.key, set()).add(dep.target.key)

    # Compute transitive and cycle edges
    transitive_edges = DependencyGraph._find_transitive_edges(adjacency)
    cycle_edges = get_cycle_edges(adjacency)

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

    return {"nodes": nodes, "edges": edges, "has_positions": has_positions}


def scope_graph_data(request):
    """Return graph data for specified project keys (POST with JSON body)."""
    if request.method != 'POST':
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        body = json.loads(request.body)
        project_keys = body.get('keys', [])
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"nodes": [], "edges": [], "has_positions": False})

    if not project_keys:
        return JsonResponse({"nodes": [], "edges": [], "has_positions": False})

    # Build graph data for these projects
    data = get_graph_data_for_keys(project_keys)
    return JsonResponse(data)


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
        ]
