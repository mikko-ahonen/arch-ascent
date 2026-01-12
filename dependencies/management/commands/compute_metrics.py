"""
Management command to compute and display extended dependency metrics.

Usage:
    # Show top 20 by instability
    python manage.py compute_metrics

    # Show specific project metrics
    python manage.py compute_metrics --project core:auth

    # Sort by different metric
    python manage.py compute_metrics --sort-by betweenness

    # Show more results
    python manage.py compute_metrics --top 50

    # Save metrics to database
    python manage.py compute_metrics --save

    # Output as JSON
    python manage.py compute_metrics --output json
"""
import json
from django.core.management.base import BaseCommand
from django.db import transaction
from dependencies.models import Project, Dependency, NodeMetrics, AnalysisRun
from dependencies.components.graph.graph import calculate_all_metrics


class Command(BaseCommand):
    help = 'Compute and display extended dependency metrics'

    def add_arguments(self, parser):
        parser.add_argument(
            '--project',
            type=str,
            default=None,
            help='Specific project key to show metrics for'
        )
        parser.add_argument(
            '--sort-by',
            type=str,
            choices=['instability', 'betweenness', 'fan_in', 'fan_out', 'coupling', 'degree'],
            default='instability',
            help='Metric to sort by (default: instability)'
        )
        parser.add_argument(
            '--top',
            type=int,
            default=20,
            help='Number of results to show (default: 20)'
        )
        parser.add_argument(
            '--output',
            type=str,
            choices=['text', 'json', 'yaml'],
            default='text',
            help='Output format (default: text)'
        )
        parser.add_argument(
            '--save',
            action='store_true',
            help='Save metrics to database'
        )

    def handle(self, *args, **options):
        project_key = options['project']
        sort_by = options['sort_by']
        top_n = options['top']
        output_format = options['output']
        save = options['save']

        # Build adjacency list from database
        adjacency = self._build_adjacency()

        if not adjacency:
            self.stderr.write(self.style.WARNING("No dependencies found"))
            return

        # Calculate all metrics
        metrics = calculate_all_metrics(adjacency)

        # Filter to specific project if requested
        if project_key:
            if project_key not in metrics:
                self.stderr.write(self.style.ERROR(f"Project '{project_key}' not found"))
                return
            metrics = {project_key: metrics[project_key]}

        # Sort by requested metric
        sort_key = self._get_sort_key(sort_by)
        sorted_metrics = sorted(
            metrics.items(),
            key=lambda x: x[1].get(sort_key, 0),
            reverse=True
        )

        if not project_key:
            sorted_metrics = sorted_metrics[:top_n]

        # Save if requested
        if save:
            self._save_metrics(metrics)

        # Output results
        if output_format == 'json':
            self._output_json(sorted_metrics, sort_by)
        elif output_format == 'yaml':
            self._output_yaml(sorted_metrics, sort_by)
        else:
            self._output_text(sorted_metrics, sort_by, project_key)

    def _build_adjacency(self) -> dict[str, set[str]]:
        """Build adjacency list from database."""
        adjacency: dict[str, set[str]] = {}

        for dep in Dependency.objects.select_related('source', 'target').all():
            adjacency.setdefault(dep.source.key, set()).add(dep.target.key)

        for project in Project.objects.all():
            adjacency.setdefault(project.key, set())

        return adjacency

    def _get_sort_key(self, sort_by: str) -> str:
        """Map sort option to metric key."""
        return {
            'instability': 'instability',
            'betweenness': 'betweenness_centrality',
            'fan_in': 'fan_in',
            'fan_out': 'fan_out',
            'coupling': 'coupling_score',
            'degree': 'degree_centrality',
        }.get(sort_by, 'instability')

    @transaction.atomic
    def _save_metrics(self, metrics):
        """Save metrics to database."""
        # Create analysis run
        analysis_run = AnalysisRun.objects.create(
            total_projects=len(metrics),
            status='completed'
        )

        projects = {p.key: p for p in Project.objects.all()}
        count = 0

        for node_key, node_metrics in metrics.items():
            project = projects.get(node_key)
            if not project:
                continue

            NodeMetrics.objects.update_or_create(
                project=project,
                defaults={
                    'analysis_run': analysis_run,
                    'fan_in': node_metrics.get('fan_in', 0),
                    'fan_out': node_metrics.get('fan_out', 0),
                    'coupling_score': node_metrics.get('coupling_score', 0.0),
                    'afferent_coupling': node_metrics.get('afferent', 0),
                    'efferent_coupling': node_metrics.get('efferent', 0),
                    'instability': node_metrics.get('instability', 0.0),
                    'degree_centrality': node_metrics.get('degree_centrality', 0.0),
                    'betweenness_centrality': node_metrics.get('betweenness_centrality', 0.0),
                    'topological_order': node_metrics.get('topological_order'),
                    'layer_depth': node_metrics.get('layer_depth'),
                }
            )
            count += 1

        self.stdout.write(self.style.SUCCESS(f"Saved metrics for {count} projects"))

    def _output_text(self, sorted_metrics, sort_by, project_key):
        """Output results as text."""
        if project_key:
            self.stdout.write(self.style.SUCCESS(f"\nMetrics for: {project_key}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"\nTop Projects by {sort_by}"))

        self.stdout.write("-" * 80)

        for node, m in sorted_metrics:
            self.stdout.write(f"\n  {node}")
            self.stdout.write(f"    Fan-in: {m.get('fan_in', 0):<6} Fan-out: {m.get('fan_out', 0):<6}")
            self.stdout.write(
                f"    Instability: {m.get('instability', 0):.3f}    "
                f"Coupling: {m.get('coupling_score', 0):.2f}"
            )
            self.stdout.write(
                f"    Degree centrality: {m.get('degree_centrality', 0):.3f}    "
                f"Betweenness: {m.get('betweenness_centrality', 0):.3f}"
            )
            if 'topological_order' in m:
                self.stdout.write(
                    f"    Topo order: {m.get('topological_order', 'N/A'):<6} "
                    f"Layer depth: {m.get('layer_depth', 'N/A')}"
                )

    def _output_json(self, sorted_metrics, sort_by):
        """Output results as JSON."""
        output = {
            "sorted_by": sort_by,
            "metrics": [
                {"node": node, **metrics}
                for node, metrics in sorted_metrics
            ]
        }
        self.stdout.write(json.dumps(output, indent=2))

    def _output_yaml(self, sorted_metrics, sort_by):
        """Output results as YAML-like format."""
        self.stdout.write(f"sorted_by: {sort_by}")
        self.stdout.write("metrics:")

        for node, m in sorted_metrics:
            self.stdout.write(f"  - node: {node}")
            self.stdout.write(f"    fan_in: {m.get('fan_in', 0)}")
            self.stdout.write(f"    fan_out: {m.get('fan_out', 0)}")
            self.stdout.write(f"    instability: {m.get('instability', 0):.3f}")
            self.stdout.write(f"    coupling_score: {m.get('coupling_score', 0):.2f}")
            self.stdout.write(f"    degree_centrality: {m.get('degree_centrality', 0):.3f}")
            self.stdout.write(f"    betweenness_centrality: {m.get('betweenness_centrality', 0):.3f}")
            if 'topological_order' in m:
                self.stdout.write(f"    topological_order: {m.get('topological_order')}")
            if 'layer_depth' in m:
                self.stdout.write(f"    layer_depth: {m.get('layer_depth')}")
