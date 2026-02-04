"""
Management command to traverse dependency graph from a starting node.

Usage:
    # BFS downstream from a node
    python manage.py traverse_graph ServiceA

    # Upstream traversal (who depends on this?)
    python manage.py traverse_graph ServiceA --direction upstream

    # Limit depth
    python manage.py traverse_graph ServiceA --max-depth 2

    # Use DFS instead of BFS
    python manage.py traverse_graph ServiceA --algorithm dfs

    # Output as JSON
    python manage.py traverse_graph ServiceA --output json
"""
import json
from django.core.management.base import BaseCommand
from dependencies.models import Component, Dependency
from dependencies.components.graph.graph import traverse_graph


class Command(BaseCommand):
    help = 'Traverse dependency graph from a starting node'

    def add_arguments(self, parser):
        parser.add_argument(
            'start_node',
            type=str,
            help='Starting node key (project key)'
        )
        parser.add_argument(
            '--direction',
            type=str,
            choices=['downstream', 'upstream', 'both'],
            default='downstream',
            help='Traversal direction (default: downstream)'
        )
        parser.add_argument(
            '--algorithm',
            type=str,
            choices=['bfs', 'dfs'],
            default='bfs',
            help='Traversal algorithm (default: bfs)'
        )
        parser.add_argument(
            '--max-depth',
            type=int,
            default=None,
            help='Maximum traversal depth'
        )
        parser.add_argument(
            '--output',
            type=str,
            choices=['text', 'json', 'yaml'],
            default='text',
            help='Output format (default: text)'
        )

    def handle(self, *args, **options):
        start_node = options['start_node']
        direction = options['direction']
        algorithm = options['algorithm']
        max_depth = options['max_depth']
        output_format = options['output']

        # Try to find component by Maven coordinates, UUID, or name
        component = None
        if ':' in start_node:
            parts = start_node.split(':', 1)
            component = Component.objects.filter(group_id=parts[0], artifact_id=parts[1]).first()
        if not component:
            try:
                component = Component.objects.get(id=start_node)
            except (Component.DoesNotExist, ValueError):
                pass
        if not component:
            component = Component.objects.filter(name=start_node).first()

        if not component:
            self.stderr.write(self.style.ERROR(f"Component '{start_node}' not found"))
            return

        component_id = str(component.id)

        # Build adjacency list from database
        adjacency = self._build_adjacency()

        # Perform traversal
        result = traverse_graph(
            adjacency,
            component_id,
            direction=direction,
            algorithm=algorithm,
            max_depth=max_depth,
        )

        # Format and output results
        if output_format == 'json':
            self._output_json(result, component.name, direction, algorithm, max_depth)
        elif output_format == 'yaml':
            self._output_yaml(result, component.name, direction, algorithm, max_depth)
        else:
            self._output_text(result, component.name, direction, algorithm, max_depth)

    def _build_adjacency(self) -> dict[str, set[str]]:
        """Build adjacency list from database."""
        adjacency: dict[str, set[str]] = {}

        for dep in Dependency.objects.select_related('source', 'target').all():
            source_key = str(dep.source.id)
            target_key = str(dep.target.id)
            adjacency.setdefault(source_key, set()).add(target_key)

        # Ensure all components are in adjacency (even if no outgoing deps)
        for component in Component.objects.all():
            adjacency.setdefault(str(component.id), set())

        return adjacency

    def _output_text(self, result, start_node, direction, algorithm, max_depth):
        """Output results as text."""
        self.stdout.write(self.style.SUCCESS(f"\nGraph Traversal Results"))
        self.stdout.write(f"Start node: {start_node}")
        self.stdout.write(f"Direction: {direction}")
        self.stdout.write(f"Algorithm: {algorithm.upper()}")
        if max_depth:
            self.stdout.write(f"Max depth: {max_depth}")
        self.stdout.write("")

        total = 0
        for depth in sorted(result.keys()):
            nodes = result[depth]
            total += len(nodes)
            self.stdout.write(f"Depth {depth}:")
            for node in sorted(nodes):
                prefix = "  -> " if depth > 0 else "  "
                self.stdout.write(f"{prefix}{node}")

        self.stdout.write(f"\nTotal nodes reachable: {total}")

    def _output_json(self, result, start_node, direction, algorithm, max_depth):
        """Output results as JSON."""
        # Convert sets to sorted lists for JSON serialization
        result_serializable = {
            f"depth_{k}": sorted(v) for k, v in result.items()
        }

        output = {
            "start_node": start_node,
            "direction": direction,
            "algorithm": algorithm,
            "max_depth": max_depth,
            "reachable": result_serializable,
            "total_reachable": sum(len(v) for v in result.values()),
        }
        self.stdout.write(json.dumps(output, indent=2))

    def _output_yaml(self, result, start_node, direction, algorithm, max_depth):
        """Output results as YAML-like format."""
        self.stdout.write(f"start_node: {start_node}")
        self.stdout.write(f"direction: {direction}")
        self.stdout.write(f"algorithm: {algorithm}")
        if max_depth:
            self.stdout.write(f"max_depth: {max_depth}")
        self.stdout.write("reachable:")

        for depth in sorted(result.keys()):
            nodes = result[depth]
            self.stdout.write(f"  depth_{depth}:")
            for node in sorted(nodes):
                self.stdout.write(f"    - {node}")

        total = sum(len(v) for v in result.values())
        self.stdout.write(f"total_reachable: {total}")
