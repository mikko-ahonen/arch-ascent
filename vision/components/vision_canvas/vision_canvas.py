"""
Vision Canvas Component for Arch Ascent.

Displays a vision's layers and groups with Cytoscape.js visualization.
"""
import json
from django_components import component
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from vision.models import Vision, Layer, Group, GroupMembership, LayerNodePosition, VisionVersion
from dependencies.models import Project, Dependency
from dependencies.components.graph.graph import (
    DependencyGraph,
    get_cycle_edges,
    calculate_optimal_eps,
    dbscan_cluster,
)


@component.register("vision_canvas")
class VisionCanvas(component.Component):
    template_name = "vision_canvas/vision_canvas.html"

    def get_context_data(self, vision=None, vision_id=None, version=None,
                         height="500px", visible_layers=None, **kwargs):
        if vision_id and not vision:
            vision = Vision.objects.get(pk=vision_id)

        # Default to first layer only (single layer selection mode)
        if vision and visible_layers is None:
            first_layer = vision.layers.first()
            if first_layer:
                visible_layers = [first_layer.id]

        # Load from version snapshot if provided, otherwise live data
        if version:
            graph_data = self.get_version_graph_data(version, visible_layers)
        elif vision:
            graph_data = self.get_vision_graph_data(vision, visible_layers)
        else:
            graph_data = {"nodes": [], "edges": []}

        return {
            'vision': vision,
            'version': version,
            'height': height,
            'graph_data': json.dumps(graph_data),
            'has_positions': graph_data.get("has_positions", False),
            'visible_layers': visible_layers,
        }

    @staticmethod
    def get_vision_graph_data(vision, visible_layers=None) -> dict:
        """Build Cytoscape-compatible graph data for a vision.

        Args:
            vision: The Vision object
            visible_layers: List of layer IDs to show. If None, show all layers.

        All projects are shown regardless of group membership. Projects in
        groups appear inside their group; others appear as standalone nodes.
        """
        nodes = []
        edges = []
        has_positions = False
        added_project_keys = set()  # Track which projects we've added

        # Get all projects
        all_projects = {p.key: p for p in Project.objects.all()}

        # Get layers to display
        layers = vision.layers.all()
        if visible_layers is not None:
            layers = layers.filter(id__in=visible_layers)

        # Add layer nodes and their groups/projects
        for layer in layers:
            layer_node = {
                "data": {
                    "id": f"layer-{layer.id}",
                    "label": layer.name,
                    "isLayer": True,
                    "color": layer.color or "#6c757d",
                }
            }
            nodes.append(layer_node)

            # Add groups within the layer
            for group in layer.groups.all():
                group_node = {
                    "data": {
                        "id": f"group-{group.id}",
                        "label": group.name,
                        "parent": f"layer-{layer.id}",
                        "isGroup": True,
                        "color": group.color or "#495057",
                    }
                }
                if group.position_x is not None and group.position_y is not None:
                    group_node["position"] = {"x": group.position_x, "y": group.position_y}
                    has_positions = True
                nodes.append(group_node)

                # Add project nodes within the group
                for membership in group.memberships.select_related('project').all():
                    project = membership.project

                    # Skip if already added (from another layer's group)
                    if project.key in added_project_keys:
                        continue

                    added_project_keys.add(project.key)

                    # Check for position override in this layer
                    position = LayerNodePosition.objects.filter(
                        layer=layer, project=project
                    ).first()

                    project_node = {
                        "data": {
                            "id": project.key,
                            "label": project.name,
                            "parent": f"group-{group.id}",
                            "description": project.description,
                            "inGroup": True,
                        }
                    }
                    if position and position.position_x is not None:
                        project_node["position"] = {
                            "x": position.position_x,
                            "y": position.position_y,
                        }
                        has_positions = True
                    nodes.append(project_node)

        # Add remaining projects that aren't in any visible group
        for key, project in all_projects.items():
            if key not in added_project_keys:
                added_project_keys.add(key)
                project_node = {
                    "data": {
                        "id": project.key,
                        "label": project.name,
                        "description": project.description,
                        "inGroup": False,
                    }
                }
                nodes.append(project_node)

        # Add dependencies between all projects
        all_project_ids = set(p.id for p in all_projects.values())
        if all_project_ids:
            deps = Dependency.objects.filter(
                source_id__in=all_project_ids,
                target_id__in=all_project_ids
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

    @staticmethod
    def get_version_graph_data(version: VisionVersion, visible_layers=None) -> dict:
        """Build Cytoscape-compatible graph data from a version's snapshot.

        Args:
            version: The VisionVersion object with layout_data
            visible_layers: List of layer IDs to show. If None, show all.

        Returns a graph with the snapshotted layout (groups, positions).
        """
        nodes = []
        edges = []
        has_positions = False
        added_project_keys = set()

        layout_data = version.layout_data or {}
        layers_data = layout_data.get('layers', [])

        # Get all projects for dependency edges
        all_projects = {p.key: p for p in Project.objects.all()}

        # Build node positions lookup from snapshot
        snapshot_positions = {}  # {project_key: {layer_id: {x, y}}}
        snapshot_groups = {}  # {project_key: group_id}

        for layer_data in layers_data:
            layer_id = layer_data.get('id')

            # Skip if filtering by visible_layers
            if visible_layers is not None and layer_id not in visible_layers:
                continue

            # Add layer node
            layer_node = {
                "data": {
                    "id": f"layer-{layer_id}",
                    "label": layer_data.get('name', f'Layer {layer_id}'),
                    "isLayer": True,
                    "color": layer_data.get('color', '#6c757d'),
                }
            }
            nodes.append(layer_node)

            # Add groups from snapshot
            for group_data in layer_data.get('groups', []):
                group_id = group_data.get('id')
                group_node = {
                    "data": {
                        "id": f"group-{group_id}",
                        "label": group_data.get('name', f'Group {group_id}'),
                        "parent": f"layer-{layer_id}",
                        "isGroup": True,
                        "color": group_data.get('color', '#495057'),
                    }
                }
                if group_data.get('position_x') is not None:
                    group_node["position"] = {
                        "x": group_data['position_x'],
                        "y": group_data['position_y'],
                    }
                    has_positions = True
                nodes.append(group_node)

                # Add project nodes within the group
                for member_key in group_data.get('members', []):
                    if member_key in added_project_keys:
                        continue
                    if member_key not in all_projects:
                        continue

                    added_project_keys.add(member_key)
                    project = all_projects[member_key]

                    project_node = {
                        "data": {
                            "id": project.key,
                            "label": project.name,
                            "parent": f"group-{group_id}",
                            "description": project.description,
                            "inGroup": True,
                        }
                    }
                    nodes.append(project_node)

            # Apply node positions from snapshot
            for pos_data in layer_data.get('node_positions', []):
                project_key = pos_data.get('project__key')
                if project_key in added_project_keys:
                    # Find and update the node position
                    for node in nodes:
                        if node['data'].get('id') == project_key:
                            node['position'] = {
                                'x': pos_data['position_x'],
                                'y': pos_data['position_y'],
                            }
                            has_positions = True
                            break

        # Add remaining projects not in any group
        for key, project in all_projects.items():
            if key not in added_project_keys:
                added_project_keys.add(key)
                project_node = {
                    "data": {
                        "id": project.key,
                        "label": project.name,
                        "description": project.description,
                        "inGroup": False,
                    }
                }
                nodes.append(project_node)

        # Add dependency edges (same as get_vision_graph_data)
        all_project_ids = set(p.id for p in all_projects.values())
        if all_project_ids:
            deps = Dependency.objects.filter(
                source_id__in=all_project_ids,
                target_id__in=all_project_ids
            ).select_related('source', 'target')

            adjacency: dict[str, set[str]] = {}
            for dep in deps:
                adjacency.setdefault(dep.source.key, set()).add(dep.target.key)

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

    @staticmethod
    def htmx_get_data(request, vision_id):
        """Return vision graph data as JSON.

        Query params:
            layers: Comma-separated list of layer IDs to show
            version_id: If provided, load from version snapshot instead of live data
        """
        try:
            vision = Vision.objects.get(pk=vision_id)

            # Parse visible layers from query params
            visible_layers = None
            layers_param = request.GET.get('layers')
            if layers_param:
                visible_layers = [int(lid) for lid in layers_param.split(',') if lid.strip().isdigit()]

            # Check if loading from a version
            version_id = request.GET.get('version_id')
            if version_id:
                try:
                    version = VisionVersion.objects.get(pk=version_id, vision=vision)
                    data = VisionCanvas.get_version_graph_data(version, visible_layers)
                except VisionVersion.DoesNotExist:
                    return JsonResponse({"error": "Version not found"}, status=404)
            else:
                data = VisionCanvas.get_vision_graph_data(vision, visible_layers)

            return JsonResponse(data)
        except Vision.DoesNotExist:
            return JsonResponse({"error": "Vision not found"}, status=404)

    @staticmethod
    @csrf_exempt
    def htmx_save_layout(request, vision_id):
        """Save node positions for a vision.

        Saves positions for the currently selected layer. Each layer maintains
        its own node positions.
        """
        if request.method != 'POST':
            return HttpResponse(status=405)

        try:
            vision = Vision.objects.get(pk=vision_id)
            data = json.loads(request.body)
            nodes = data.get('nodes', [])
            groups = data.get('groups', [])
            layer_id = data.get('layerId')

            # Get the layer we're saving to
            layer = None
            if layer_id:
                layer = Layer.objects.filter(pk=layer_id, vision=vision).first()

            # Update group positions
            for group_data in groups:
                group_id = group_data.get('id', '').replace('group-', '')
                if group_id.isdigit():
                    Group.objects.filter(pk=int(group_id)).update(
                        position_x=group_data.get('x'),
                        position_y=group_data.get('y'),
                    )

            # Update project positions in the current layer
            for node_data in nodes:
                project_key = node_data.get('id')
                if project_key and not project_key.startswith(('layer-', 'group-')):
                    project = Project.objects.filter(key=project_key).first()
                    if project and layer:
                        # Save position for this layer
                        LayerNodePosition.objects.update_or_create(
                            layer=layer,
                            project=project,
                            defaults={
                                'position_x': node_data.get('x'),
                                'position_y': node_data.get('y'),
                            }
                        )

            return HttpResponse(
                '<div class="alert alert-success alert-dismissible fade show">'
                '<i class="bi bi-check-circle me-2"></i>'
                'Layout saved.'
                '<button type="button" class="btn-close" data-bs-dismiss="alert"></button>'
                '</div>'
            )
        except Exception as e:
            return HttpResponse(
                f'<div class="alert alert-danger alert-dismissible fade show">'
                f'<i class="bi bi-x-circle me-2"></i>'
                f'Save failed: {e}'
                f'<button type="button" class="btn-close" data-bs-dismiss="alert"></button>'
                f'</div>'
            )

    @staticmethod
    @csrf_exempt
    def htmx_cluster(request, vision_id):
        """Automatically cluster nodes based on positions."""
        if request.method != 'POST':
            return JsonResponse({'error': 'Method not allowed'}, status=405)

        try:
            data = json.loads(request.body)
            nodes = data.get('nodes', [])
            eps_param = data.get('eps', 'auto')
            min_samples = int(data.get('min_samples', 2))

            # Filter out nodes that are already in groups
            ungrouped = [n for n in nodes if not n.get('parent')]

            if len(ungrouped) < min_samples:
                return JsonResponse({
                    'error': 'Not enough ungrouped nodes to cluster.',
                    'clusters': []
                })

            # Calculate eps: auto mode targets n/10 clusters
            if eps_param == 'auto':
                target_clusters = max(2, len(ungrouped) // 10)
                eps = calculate_optimal_eps(ungrouped, target_clusters, min_samples)
            else:
                eps = float(eps_param)

            # Run clustering
            clusters = dbscan_cluster(ungrouped, eps, min_samples)

            if not clusters:
                return JsonResponse({
                    'error': 'No clusters found. Try adjusting the distance threshold.',
                    'clusters': []
                })

            # Filter valid clusters
            valid_clusters = [c for c in clusters if len(c) >= min_samples]

            if not valid_clusters:
                return JsonResponse({
                    'error': 'No valid clusters found.',
                    'clusters': []
                })

            # Return clusters for frontend to create groups
            result_clusters = []
            for i, cluster_node_ids in enumerate(valid_clusters):
                result_clusters.append({
                    'name': f'Cluster {i + 1}',
                    'nodes': cluster_node_ids,
                })

            return JsonResponse({
                'clusters': result_clusters,
                'eps_used': eps,
            })

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
