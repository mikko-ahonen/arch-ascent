"""
Management command to run comprehensive static dependency analysis.

Usage:
    # Run all analyses
    python manage.py analyze_graph --all

    # Run specific analyses
    python manage.py analyze_graph --scc --metrics

    # Check layer violations
    python manage.py analyze_graph --layers

    # Detect communities
    python manage.py analyze_graph --clusters

    # Save results to database
    python manage.py analyze_graph --all --save

    # Output as JSON
    python manage.py analyze_graph --all --output json

    # Include LLM interpretations (if available)
    python manage.py analyze_graph --all --with-llm
"""
import json
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from dependencies.models import (
    Component, Dependency, AnalysisRun, LayerDefinition,
    LayerAssignment, LayerViolation, NodeMetrics
)
from dependencies.components.graph.graph import (
    find_sccs_kosaraju,
    louvain_communities,
    calculate_all_metrics,
    topological_sort,
    assign_topological_layers,
    detect_layer_violations,
)


class Command(BaseCommand):
    help = 'Run comprehensive static dependency analysis'

    def add_arguments(self, parser):
        parser.add_argument('--scc', action='store_true', help='Analyze strongly connected components (cycles)')
        parser.add_argument('--metrics', action='store_true', help='Compute all metrics')
        parser.add_argument('--layers', action='store_true', help='Check layer violations')
        parser.add_argument('--clusters', action='store_true', help='Detect communities')
        parser.add_argument('--all', action='store_true', help='Run all analyses')
        parser.add_argument('--output', choices=['text', 'json', 'yaml'], default='text', help='Output format')
        parser.add_argument('--save', action='store_true', help='Save results to database')
        parser.add_argument('--with-llm', action='store_true', help='Include LLM interpretations')

    def handle(self, *args, **options):
        run_all = options['all']
        run_scc = options['scc'] or run_all
        run_metrics = options['metrics'] or run_all
        run_layers = options['layers'] or run_all
        run_clusters = options['clusters'] or run_all
        output_format = options['output']
        save = options['save']
        with_llm = options['with_llm']

        if not any([run_scc, run_metrics, run_layers, run_clusters]):
            self.stderr.write(self.style.WARNING(
                "No analysis specified. Use --scc, --metrics, --layers, --clusters, or --all"
            ))
            return

        # Build adjacency
        adjacency = self._build_adjacency()
        if not adjacency:
            self.stderr.write(self.style.WARNING("No dependencies found"))
            return

        results = {
            'total_projects': len(adjacency),
            'total_dependencies': sum(len(targets) for targets in adjacency.values()),
        }

        # Run analyses
        if run_scc:
            results['scc'] = self._analyze_scc(adjacency)

        if run_metrics:
            results['metrics'] = self._analyze_metrics(adjacency)

        if run_layers:
            results['layers'] = self._analyze_layers(adjacency)

        if run_clusters:
            results['clusters'] = self._analyze_clusters(adjacency)

        # Add LLM interpretations if requested
        if with_llm:
            results['llm_available'] = self._add_llm_interpretations(results)

        # Save to database
        if save:
            self._save_results(results)

        # Output results
        if output_format == 'json':
            self._output_json(results)
        elif output_format == 'yaml':
            self._output_yaml(results)
        else:
            self._output_text(results)

    def _build_adjacency(self) -> dict[str, set[str]]:
        """Build adjacency list from database."""
        adjacency: dict[str, set[str]] = {}
        for dep in Dependency.objects.select_related('source', 'target').all():
            source_key = str(dep.source.id)
            target_key = str(dep.target.id)
            adjacency.setdefault(source_key, set()).add(target_key)
        for component in Component.objects.all():
            adjacency.setdefault(str(component.id), set())
        return adjacency

    def _analyze_scc(self, adjacency) -> dict:
        """Analyze strongly connected components."""
        sccs = find_sccs_kosaraju(adjacency)
        cyclic_sccs = [scc for scc in sccs if len(scc) >= 2]

        ordering, is_dag, back_edges = topological_sort(adjacency)

        return {
            'is_dag': is_dag,
            'total_sccs': len(sccs),
            'cyclic_sccs': len(cyclic_sccs),
            'largest_cycle_size': max((len(scc) for scc in cyclic_sccs), default=0),
            'back_edges': len(back_edges),
            'cycles': [
                {'members': sorted(scc), 'size': len(scc)}
                for scc in sorted(cyclic_sccs, key=len, reverse=True)[:5]
            ],
        }

    def _analyze_metrics(self, adjacency) -> dict:
        """Calculate all metrics."""
        metrics = calculate_all_metrics(adjacency)

        # Find hotspots
        by_instability = sorted(metrics.items(), key=lambda x: x[1].get('instability', 0), reverse=True)
        by_betweenness = sorted(metrics.items(), key=lambda x: x[1].get('betweenness_centrality', 0), reverse=True)
        by_coupling = sorted(metrics.items(), key=lambda x: x[1].get('coupling_score', 0), reverse=True)

        return {
            'total_nodes': len(metrics),
            'high_instability': [
                {'node': n, 'instability': m['instability']}
                for n, m in by_instability[:5] if m.get('instability', 0) > 0.7
            ],
            'high_betweenness': [
                {'node': n, 'betweenness': m['betweenness_centrality']}
                for n, m in by_betweenness[:5]
            ],
            'high_coupling': [
                {'node': n, 'coupling': m['coupling_score'], 'fan_in': m['fan_in'], 'fan_out': m['fan_out']}
                for n, m in by_coupling[:5]
            ],
            'all_metrics': metrics,
        }

    def _analyze_layers(self, adjacency) -> dict:
        """Analyze layer violations."""
        # Get layer assignments from database
        layer_assignments = {}
        for la in LayerAssignment.objects.select_related('component', 'layer').all():
            layer_assignments[str(la.component.id)] = la.layer.level

        if not layer_assignments:
            return {
                'configured': False,
                'message': 'No layer assignments. Use manage_layers to define layers.',
            }

        violations = detect_layer_violations(adjacency, layer_assignments)
        critical = [v for v in violations if v['severity'] == 'critical']

        # Compute topological layers
        topo_layers = assign_topological_layers(adjacency)

        return {
            'configured': True,
            'assigned_projects': len(layer_assignments),
            'total_violations': len(violations),
            'critical_violations': len(critical),
            'violations': critical[:10],
            'topological_depth': max(topo_layers.values()) if topo_layers else 0,
        }

    def _analyze_clusters(self, adjacency) -> dict:
        """Detect communities using Louvain."""
        communities = louvain_communities(adjacency)

        return {
            'total_clusters': len(communities),
            'cluster_sizes': sorted([len(c) for c in communities], reverse=True),
            'clusters': [
                {'id': i, 'members': sorted(c), 'size': len(c)}
                for i, c in enumerate(sorted(communities, key=len, reverse=True)[:5])
            ],
        }

    def _add_llm_interpretations(self, results) -> bool:
        """Add LLM interpretations if available."""
        try:
            from dependencies.llm_service import RefactoringAnalyzer
            analyzer = RefactoringAnalyzer()
            if not analyzer.is_available:
                return False

            # LLM would add interpretations here
            # For now, just indicate availability
            return True
        except ImportError:
            return False

    @transaction.atomic
    def _save_results(self, results):
        """Save analysis results to database."""
        analysis_run = AnalysisRun.objects.create(
            total_projects=results['total_projects'],
            total_sccs=results.get('scc', {}).get('cyclic_sccs', 0),
            total_clusters=results.get('clusters', {}).get('total_clusters', 0),
            status='completed',
            completed_at=timezone.now(),
        )

        # Save metrics
        if 'metrics' in results and 'all_metrics' in results['metrics']:
            components = {str(c.id): c for c in Component.objects.all()}
            for node_key, metrics in results['metrics']['all_metrics'].items():
                component = components.get(node_key)
                if component:
                    NodeMetrics.objects.update_or_create(
                        component=component,
                        defaults={
                            'analysis_run': analysis_run,
                            'fan_in': metrics.get('fan_in', 0),
                            'fan_out': metrics.get('fan_out', 0),
                            'coupling_score': metrics.get('coupling_score', 0.0),
                            'afferent_coupling': metrics.get('afferent', 0),
                            'efferent_coupling': metrics.get('efferent', 0),
                            'instability': metrics.get('instability', 0.0),
                            'degree_centrality': metrics.get('degree_centrality', 0.0),
                            'betweenness_centrality': metrics.get('betweenness_centrality', 0.0),
                            'topological_order': metrics.get('topological_order'),
                            'layer_depth': metrics.get('layer_depth'),
                        }
                    )

        self.stdout.write(self.style.SUCCESS(f"Saved analysis run #{analysis_run.id}"))

    def _output_text(self, results):
        """Output results as text."""
        self.stdout.write(self.style.SUCCESS("\n" + "=" * 60))
        self.stdout.write(self.style.SUCCESS("Static Dependency Analysis Results"))
        self.stdout.write("=" * 60)

        self.stdout.write(f"\nTotal projects: {results['total_projects']}")
        self.stdout.write(f"Total dependencies: {results['total_dependencies']}")

        if 'scc' in results:
            scc = results['scc']
            self.stdout.write(self.style.SUCCESS("\n--- Cycle Analysis ---"))
            self.stdout.write(f"Is DAG: {scc['is_dag']}")
            self.stdout.write(f"Cyclic components: {scc['cyclic_sccs']}")
            if scc['cyclic_sccs'] > 0:
                self.stdout.write(f"Largest cycle size: {scc['largest_cycle_size']}")
                self.stdout.write("Top cycles:")
                for cycle in scc['cycles']:
                    self.stdout.write(f"  - {cycle['size']} nodes: {', '.join(cycle['members'][:3])}...")

        if 'metrics' in results:
            metrics = results['metrics']
            self.stdout.write(self.style.SUCCESS("\n--- Metrics Hotspots ---"))
            if metrics['high_instability']:
                self.stdout.write("Highly unstable (I > 0.7):")
                for item in metrics['high_instability']:
                    self.stdout.write(f"  - {item['node']}: {item['instability']:.2f}")
            if metrics['high_betweenness']:
                self.stdout.write("High betweenness (bridges):")
                for item in metrics['high_betweenness']:
                    self.stdout.write(f"  - {item['node']}: {item['betweenness']:.3f}")

        if 'layers' in results:
            layers = results['layers']
            self.stdout.write(self.style.SUCCESS("\n--- Layer Analysis ---"))
            if layers.get('configured'):
                self.stdout.write(f"Assigned projects: {layers['assigned_projects']}")
                self.stdout.write(f"Total violations: {layers['total_violations']}")
                self.stdout.write(f"Critical violations: {layers['critical_violations']}")
                if layers['violations']:
                    self.stdout.write("Top violations:")
                    for v in layers['violations'][:5]:
                        self.stdout.write(f"  - {v['source']} -> {v['target']} ({v['reason']})")
            else:
                self.stdout.write(self.style.WARNING(layers['message']))

        if 'clusters' in results:
            clusters = results['clusters']
            self.stdout.write(self.style.SUCCESS("\n--- Community Detection ---"))
            self.stdout.write(f"Total clusters: {clusters['total_clusters']}")
            self.stdout.write(f"Cluster sizes: {clusters['cluster_sizes'][:10]}")

        if results.get('llm_available'):
            self.stdout.write(self.style.SUCCESS("\nLLM interpretations available"))

    def _output_json(self, results):
        """Output results as JSON."""
        # Remove all_metrics for cleaner output
        output = {k: v for k, v in results.items()}
        if 'metrics' in output and 'all_metrics' in output['metrics']:
            output['metrics'] = {k: v for k, v in output['metrics'].items() if k != 'all_metrics'}

        self.stdout.write(json.dumps(output, indent=2, default=str))

    def _output_yaml(self, results):
        """Output results as YAML-like format."""
        self.stdout.write(f"total_projects: {results['total_projects']}")
        self.stdout.write(f"total_dependencies: {results['total_dependencies']}")

        if 'scc' in results:
            scc = results['scc']
            self.stdout.write("scc:")
            self.stdout.write(f"  is_dag: {str(scc['is_dag']).lower()}")
            self.stdout.write(f"  cyclic_sccs: {scc['cyclic_sccs']}")
            self.stdout.write(f"  largest_cycle_size: {scc['largest_cycle_size']}")

        if 'metrics' in results:
            metrics = results['metrics']
            self.stdout.write("metrics:")
            self.stdout.write(f"  total_nodes: {metrics['total_nodes']}")
            if metrics['high_instability']:
                self.stdout.write("  high_instability:")
                for item in metrics['high_instability']:
                    self.stdout.write(f"    - node: {item['node']}")
                    self.stdout.write(f"      instability: {item['instability']:.3f}")

        if 'layers' in results:
            layers = results['layers']
            self.stdout.write("layers:")
            self.stdout.write(f"  configured: {str(layers.get('configured', False)).lower()}")
            if layers.get('configured'):
                self.stdout.write(f"  critical_violations: {layers['critical_violations']}")

        if 'clusters' in results:
            clusters = results['clusters']
            self.stdout.write("clusters:")
            self.stdout.write(f"  total: {clusters['total_clusters']}")
            self.stdout.write(f"  sizes: {clusters['cluster_sizes']}")
