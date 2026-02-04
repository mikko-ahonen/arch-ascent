"""
Management command to compute topological ordering and detect layer violations.

Usage:
    # Basic topological sort
    python manage.py topo_sort

    # Check for layer violations
    python manage.py topo_sort --check-violations

    # Output as JSON
    python manage.py topo_sort --output json

    # Save violations to database
    python manage.py topo_sort --check-violations --save
"""
import json
from django.core.management.base import BaseCommand
from django.db import transaction
from dependencies.models import (
    Component, Dependency, AnalysisRun, LayerDefinition,
    LayerAssignment, LayerViolation
)
from dependencies.components.graph.graph import (
    topological_sort, assign_topological_layers, detect_layer_violations
)


class Command(BaseCommand):
    help = 'Compute topological ordering and detect layer violations'

    def add_arguments(self, parser):
        parser.add_argument(
            '--check-violations',
            action='store_true',
            help='Check for layer violations using defined layers'
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
            help='Save violations to database'
        )

    def handle(self, *args, **options):
        check_violations = options['check_violations']
        output_format = options['output']
        save = options['save']

        # Build adjacency list from database
        adjacency = self._build_adjacency()

        if not adjacency:
            self.stderr.write(self.style.WARNING("No dependencies found"))
            return

        # Compute topological ordering
        ordering, is_dag, back_edges = topological_sort(adjacency)
        layers = assign_topological_layers(adjacency)

        # Check violations if requested
        violations = []
        if check_violations:
            layer_assignments = self._get_layer_assignments()
            if layer_assignments:
                violations = detect_layer_violations(adjacency, layer_assignments)
            else:
                self.stderr.write(
                    self.style.WARNING("No layer assignments found. Use manage_layers to define layers.")
                )

        # Save violations if requested
        if save and violations:
            self._save_violations(violations)

        # Output results
        if output_format == 'json':
            self._output_json(ordering, is_dag, back_edges, layers, violations)
        elif output_format == 'yaml':
            self._output_yaml(ordering, is_dag, back_edges, layers, violations)
        else:
            self._output_text(ordering, is_dag, back_edges, layers, violations)

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

    def _get_layer_assignments(self) -> dict[str, int]:
        """Get layer assignments from database."""
        assignments = {}
        for la in LayerAssignment.objects.select_related('component', 'layer').all():
            assignments[str(la.component.id)] = la.layer.level
        return assignments

    @transaction.atomic
    def _save_violations(self, violations):
        """Save violations to database."""
        # Create analysis run
        analysis_run = AnalysisRun.objects.create(
            total_projects=Component.objects.count(),
            status='completed'
        )

        # Get component and layer mappings
        components = {str(c.id): c for c in Component.objects.all()}
        layers = {l.level: l for l in LayerDefinition.objects.all()}

        count = 0
        for v in violations:
            source_component = components.get(v['source'])
            target_component = components.get(v['target'])
            source_layer = layers.get(v['source_layer'])
            target_layer = layers.get(v['target_layer'])

            if source_component and target_component and source_layer and target_layer:
                LayerViolation.objects.create(
                    analysis_run=analysis_run,
                    source_component=source_component,
                    target_component=target_component,
                    source_layer=source_layer,
                    target_layer=target_layer,
                    severity=v['severity'],
                )
                count += 1

        self.stdout.write(self.style.SUCCESS(f"Saved {count} violations"))

    def _output_text(self, ordering, is_dag, back_edges, layers, violations):
        """Output results as text."""
        self.stdout.write(self.style.SUCCESS("\nTopological Analysis Results"))
        self.stdout.write(f"Is DAG: {is_dag}")
        self.stdout.write(f"Total nodes: {len(ordering)}")

        if not is_dag:
            self.stdout.write(self.style.WARNING(f"\nCycles detected! Back edges: {len(back_edges)}"))
            for source, target in back_edges[:10]:  # Show first 10
                self.stdout.write(f"  {source} -> {target}")
            if len(back_edges) > 10:
                self.stdout.write(f"  ... and {len(back_edges) - 10} more")

        self.stdout.write("\nTopological Ordering:")
        for i, node in enumerate(ordering[:20]):  # Show first 20
            layer = layers.get(node, '?')
            self.stdout.write(f"  {i + 1}. {node} (layer {layer})")
        if len(ordering) > 20:
            self.stdout.write(f"  ... and {len(ordering) - 20} more")

        if violations:
            critical = [v for v in violations if v['severity'] == 'critical']
            self.stdout.write(self.style.WARNING(f"\nLayer Violations: {len(violations)}"))
            self.stdout.write(f"  Critical: {len(critical)}")

            for v in critical[:10]:
                self.stdout.write(
                    f"  [{v['severity'].upper()}] {v['source']} -> {v['target']} ({v['reason']})"
                )
            if len(critical) > 10:
                self.stdout.write(f"  ... and {len(critical) - 10} more critical violations")

    def _output_json(self, ordering, is_dag, back_edges, layers, violations):
        """Output results as JSON."""
        output = {
            "is_dag": is_dag,
            "ordering": ordering,
            "back_edges": [{"from": s, "to": t} for s, t in back_edges],
            "layers": layers,
            "violations": violations,
        }
        self.stdout.write(json.dumps(output, indent=2))

    def _output_yaml(self, ordering, is_dag, back_edges, layers, violations):
        """Output results as YAML-like format."""
        self.stdout.write(f"is_dag: {str(is_dag).lower()}")

        if not is_dag:
            self.stdout.write("back_edges:")
            for source, target in back_edges:
                self.stdout.write(f"  - from: {source}")
                self.stdout.write(f"    to: {target}")

        self.stdout.write("ordering:")
        for node in ordering:
            self.stdout.write(f"  - {node}")

        self.stdout.write("layer_assignments:")
        for node, layer in sorted(layers.items(), key=lambda x: x[1]):
            self.stdout.write(f"  {node}: {layer}")

        if violations:
            critical = [v for v in violations if v['severity'] == 'critical']
            self.stdout.write("layer_violations:")
            for v in critical:
                self.stdout.write(f"  - from: {v['source']}")
                self.stdout.write(f"    to: {v['target']}")
                self.stdout.write(f"    from_layer: {v['source_layer']}")
                self.stdout.write(f"    to_layer: {v['target_layer']}")
                self.stdout.write(f"    severity: {v['severity']}")
            self.stdout.write(f"total_violations: {len(violations)}")
