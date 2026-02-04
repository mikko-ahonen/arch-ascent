"""
REST API views for static dependency analysis.

Endpoints:
    POST /api/v1/graph/traverse/     - Traverse graph from a node
    GET  /api/v1/graph/topo-sort/    - Get topological ordering
    GET  /api/v1/graph/scc/          - Get strongly connected components
    GET  /api/v1/graph/metrics/      - Get all node metrics
    GET  /api/v1/graph/metrics/<node>/ - Get metrics for a specific node
    GET  /api/v1/layers/             - List layer definitions
    POST /api/v1/layers/             - Create layer definition
    GET  /api/v1/layers/violations/  - Get layer violations
    POST /api/v1/layers/auto-assign/ - Auto-assign projects to layers
    POST /api/v1/analysis/run/       - Run full analysis
    GET  /api/v1/analysis/runs/      - List analysis runs
"""
import json
import re
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.db import transaction

from dependencies.models import (
    Component, Dependency, AnalysisRun, LayerDefinition,
    LayerAssignment, LayerViolation, NodeMetrics
)
from dependencies.components.graph.graph import (
    traverse_graph,
    topological_sort,
    assign_topological_layers,
    detect_layer_violations,
    find_sccs_kosaraju,
    louvain_communities,
    calculate_all_metrics,
)


def build_adjacency() -> dict[str, set[str]]:
    """Build adjacency list from database."""
    adjacency: dict[str, set[str]] = {}
    for dep in Dependency.objects.select_related('source', 'target').all():
        source_key = str(dep.source.id)
        target_key = str(dep.target.id)
        adjacency.setdefault(source_key, set()).add(target_key)
    for component in Component.objects.all():
        adjacency.setdefault(str(component.id), set())
    return adjacency


def get_layer_assignments() -> dict[str, int]:
    """Get layer assignments from database."""
    return {
        str(la.component.id): la.layer.level
        for la in LayerAssignment.objects.select_related('component', 'layer').all()
    }


@method_decorator(csrf_exempt, name='dispatch')
class TraverseGraphView(View):
    """POST /api/v1/graph/traverse/"""

    def post(self, request):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        start_node = data.get('start_node')
        if not start_node:
            return JsonResponse({'error': 'start_node is required'}, status=400)

        direction = data.get('direction', 'downstream')
        algorithm = data.get('algorithm', 'bfs')
        max_depth = data.get('max_depth')

        if direction not in ('downstream', 'upstream', 'both'):
            return JsonResponse({'error': 'Invalid direction'}, status=400)
        if algorithm not in ('bfs', 'dfs'):
            return JsonResponse({'error': 'Invalid algorithm'}, status=400)

        adjacency = build_adjacency()
        result = traverse_graph(adjacency, start_node, direction, algorithm, max_depth)

        # Convert to serializable format
        reachable = {f"depth_{k}": sorted(v) for k, v in result.items()}

        return JsonResponse({
            'start_node': start_node,
            'direction': direction,
            'algorithm': algorithm,
            'max_depth': max_depth,
            'reachable': reachable,
            'total_reachable': sum(len(v) for v in result.values()),
        })


class TopologicalSortView(View):
    """GET /api/v1/graph/topo-sort/"""

    def get(self, request):
        adjacency = build_adjacency()
        ordering, is_dag, back_edges = topological_sort(adjacency)
        layers = assign_topological_layers(adjacency)

        return JsonResponse({
            'is_dag': is_dag,
            'ordering': ordering,
            'back_edges': [{'from': s, 'to': t} for s, t in back_edges],
            'layers': layers,
            'total_nodes': len(ordering),
        })


class SCCView(View):
    """GET /api/v1/graph/scc/"""

    def get(self, request):
        adjacency = build_adjacency()
        sccs = find_sccs_kosaraju(adjacency)

        cyclic_sccs = [scc for scc in sccs if len(scc) >= 2]

        return JsonResponse({
            'total_sccs': len(sccs),
            'cyclic_sccs': len(cyclic_sccs),
            'cycles': [
                {'members': sorted(scc), 'size': len(scc)}
                for scc in sorted(cyclic_sccs, key=len, reverse=True)
            ],
        })


class MetricsView(View):
    """GET /api/v1/graph/metrics/"""

    def get(self, request):
        sort_by = request.GET.get('sort_by', 'instability')
        limit = int(request.GET.get('limit', 50))

        sort_key_map = {
            'instability': 'instability',
            'betweenness': 'betweenness_centrality',
            'fan_in': 'fan_in',
            'fan_out': 'fan_out',
            'coupling': 'coupling_score',
            'degree': 'degree_centrality',
        }
        sort_key = sort_key_map.get(sort_by, 'instability')

        adjacency = build_adjacency()
        metrics = calculate_all_metrics(adjacency)

        sorted_metrics = sorted(
            metrics.items(),
            key=lambda x: x[1].get(sort_key, 0),
            reverse=True
        )[:limit]

        return JsonResponse({
            'sorted_by': sort_by,
            'metrics': [{'node': k, **v} for k, v in sorted_metrics],
        })


class NodeMetricsView(View):
    """GET /api/v1/graph/metrics/<node>/"""

    def get(self, request, node):
        adjacency = build_adjacency()

        if node not in adjacency:
            return JsonResponse({'error': f'Node {node} not found'}, status=404)

        metrics = calculate_all_metrics(adjacency)
        node_metrics = metrics.get(node, {})

        return JsonResponse({
            'node': node,
            **node_metrics,
        })


class LayerListView(View):
    """GET/POST /api/v1/layers/"""

    def get(self, request):
        layers = LayerDefinition.objects.all().order_by('level')
        return JsonResponse({
            'layers': [
                {
                    'id': layer.id,
                    'name': layer.name,
                    'level': layer.level,
                    'description': layer.description,
                    'pattern': layer.pattern,
                    'assignment_count': layer.assignments.count(),
                }
                for layer in layers
            ]
        })

    @method_decorator(csrf_exempt)
    def post(self, request):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        name = data.get('name')
        level = data.get('level')

        if not name or level is None:
            return JsonResponse({'error': 'name and level are required'}, status=400)

        if LayerDefinition.objects.filter(name=name).exists():
            return JsonResponse({'error': f'Layer {name} already exists'}, status=400)

        pattern = data.get('pattern', '')
        if pattern:
            try:
                re.compile(pattern)
            except re.error as e:
                return JsonResponse({'error': f'Invalid regex pattern: {e}'}, status=400)

        layer = LayerDefinition.objects.create(
            name=name,
            level=level,
            description=data.get('description', ''),
            pattern=pattern,
        )

        return JsonResponse({
            'id': layer.id,
            'name': layer.name,
            'level': layer.level,
        }, status=201)

    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class LayerDetailView(View):
    """GET/PUT/DELETE /api/v1/layers/<pk>/"""

    def get(self, request, pk):
        try:
            layer = LayerDefinition.objects.get(pk=pk)
        except LayerDefinition.DoesNotExist:
            return JsonResponse({'error': 'Layer not found'}, status=404)

        assignments = LayerAssignment.objects.filter(layer=layer).select_related('component')

        return JsonResponse({
            'id': layer.id,
            'name': layer.name,
            'level': layer.level,
            'description': layer.description,
            'pattern': layer.pattern,
            'assignments': [
                {'component': a.component.name, 'component_id': str(a.component.id), 'auto_assigned': a.auto_assigned}
                for a in assignments
            ],
        })

    @method_decorator(csrf_exempt)
    def delete(self, request, pk):
        try:
            layer = LayerDefinition.objects.get(pk=pk)
            layer.delete()
            return JsonResponse({'status': 'deleted'})
        except LayerDefinition.DoesNotExist:
            return JsonResponse({'error': 'Layer not found'}, status=404)

    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class LayerViolationsView(View):
    """GET /api/v1/layers/violations/"""

    def get(self, request):
        adjacency = build_adjacency()
        layer_assignments = get_layer_assignments()

        if not layer_assignments:
            return JsonResponse({
                'configured': False,
                'message': 'No layer assignments configured',
                'violations': [],
            })

        violations = detect_layer_violations(adjacency, layer_assignments)

        return JsonResponse({
            'configured': True,
            'total_violations': len(violations),
            'critical_count': len([v for v in violations if v['severity'] == 'critical']),
            'violations': violations,
        })


@method_decorator(csrf_exempt, name='dispatch')
class AutoAssignLayersView(View):
    """POST /api/v1/layers/auto-assign/"""

    def post(self, request):
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            data = {}

        dry_run = data.get('dry_run', False)

        layers = LayerDefinition.objects.exclude(pattern='').order_by('level')
        components = Component.objects.all()

        if not layers.exists():
            return JsonResponse({
                'error': 'No layers with patterns defined'
            }, status=400)

        assignments = []
        for component in components:
            # Skip manually assigned
            if LayerAssignment.objects.filter(component=component, auto_assigned=False).exists():
                continue

            for layer in layers:
                if layer.pattern and re.match(layer.pattern, component.key):
                    assignments.append({
                        'component': str(component.id),
                        'component_name': component.name,
                        'layer': layer.name,
                        'layer_id': layer.id,
                    })
                    break

        if dry_run:
            return JsonResponse({
                'dry_run': True,
                'would_assign': assignments,
            })

        with transaction.atomic():
            for a in assignments:
                layer = LayerDefinition.objects.get(id=a['layer_id'])
                component = Component.objects.get(id=a['component'])
                LayerAssignment.objects.update_or_create(
                    component=component,
                    defaults={'layer': layer, 'auto_assigned': True}
                )

        return JsonResponse({
            'assigned': len(assignments),
            'assignments': assignments,
        })


@method_decorator(csrf_exempt, name='dispatch')
class RunAnalysisView(View):
    """POST /api/v1/analysis/run/"""

    def post(self, request):
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            data = {}

        run_scc = data.get('scc', True)
        run_metrics = data.get('metrics', True)
        run_layers = data.get('layers', True)
        run_clusters = data.get('clusters', True)
        save = data.get('save', False)

        adjacency = build_adjacency()
        if not adjacency:
            return JsonResponse({'error': 'No dependencies found'}, status=400)

        results = {
            'total_projects': len(adjacency),
            'total_dependencies': sum(len(targets) for targets in adjacency.values()),
        }

        if run_scc:
            sccs = find_sccs_kosaraju(adjacency)
            cyclic_sccs = [scc for scc in sccs if len(scc) >= 2]
            ordering, is_dag, back_edges = topological_sort(adjacency)

            results['scc'] = {
                'is_dag': is_dag,
                'cyclic_sccs': len(cyclic_sccs),
                'largest_cycle_size': max((len(scc) for scc in cyclic_sccs), default=0),
                'cycles': [
                    {'members': sorted(scc), 'size': len(scc)}
                    for scc in sorted(cyclic_sccs, key=len, reverse=True)[:5]
                ],
            }

        if run_metrics:
            metrics = calculate_all_metrics(adjacency)
            by_instability = sorted(metrics.items(), key=lambda x: x[1].get('instability', 0), reverse=True)

            results['metrics'] = {
                'total_nodes': len(metrics),
                'high_instability': [
                    {'node': n, 'instability': m['instability']}
                    for n, m in by_instability[:5] if m.get('instability', 0) > 0.7
                ],
            }

        if run_layers:
            layer_assignments = get_layer_assignments()
            if layer_assignments:
                violations = detect_layer_violations(adjacency, layer_assignments)
                critical = [v for v in violations if v['severity'] == 'critical']
                results['layers'] = {
                    'configured': True,
                    'total_violations': len(violations),
                    'critical_violations': len(critical),
                    'violations': critical[:10],
                }
            else:
                results['layers'] = {'configured': False}

        if run_clusters:
            communities = louvain_communities(adjacency)
            results['clusters'] = {
                'total_clusters': len(communities),
                'cluster_sizes': sorted([len(c) for c in communities], reverse=True)[:10],
            }

        if save:
            analysis_run = AnalysisRun.objects.create(
                total_projects=results['total_projects'],
                total_sccs=results.get('scc', {}).get('cyclic_sccs', 0),
                total_clusters=results.get('clusters', {}).get('total_clusters', 0),
                status='completed',
                completed_at=timezone.now(),
            )
            results['analysis_run_id'] = analysis_run.id

        return JsonResponse(results)


class AnalysisRunListView(View):
    """GET /api/v1/analysis/runs/"""

    def get(self, request):
        limit = int(request.GET.get('limit', 20))
        runs = AnalysisRun.objects.all().order_by('-started_at')[:limit]

        return JsonResponse({
            'runs': [
                {
                    'id': run.id,
                    'status': run.status,
                    'started_at': run.started_at.isoformat(),
                    'completed_at': run.completed_at.isoformat() if run.completed_at else None,
                    'total_projects': run.total_projects,
                    'total_sccs': run.total_sccs,
                    'total_clusters': run.total_clusters,
                    'proposals_generated': run.proposals_generated,
                }
                for run in runs
            ]
        })


class AnalysisRunDetailView(View):
    """GET /api/v1/analysis/runs/<pk>/"""

    def get(self, request, pk):
        try:
            run = AnalysisRun.objects.get(pk=pk)
        except AnalysisRun.DoesNotExist:
            return JsonResponse({'error': 'Analysis run not found'}, status=404)

        # Get associated data
        violations = LayerViolation.objects.filter(analysis_run=run).select_related(
            'source_component', 'target_component', 'source_layer', 'target_layer'
        )[:20]

        metrics = NodeMetrics.objects.filter(analysis_run=run).select_related('component')[:20]

        return JsonResponse({
            'id': run.id,
            'status': run.status,
            'started_at': run.started_at.isoformat(),
            'completed_at': run.completed_at.isoformat() if run.completed_at else None,
            'total_projects': run.total_projects,
            'total_sccs': run.total_sccs,
            'total_clusters': run.total_clusters,
            'proposals_generated': run.proposals_generated,
            'error_message': run.error_message,
            'layer_violations': [
                {
                    'source': v.source_component.name,
                    'target': v.target_component.name,
                    'source_layer': v.source_layer.name,
                    'target_layer': v.target_layer.name,
                    'severity': v.severity,
                }
                for v in violations
            ],
            'sample_metrics': [
                {
                    'component': m.component.name,
                    'instability': m.instability,
                    'coupling_score': m.coupling_score,
                }
                for m in metrics
            ],
        })
