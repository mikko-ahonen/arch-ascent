"""
Management command to manage architectural layer definitions.

Usage:
    # List all layers
    python manage.py manage_layers list

    # Create a layer
    python manage.py manage_layers create infrastructure 0 --pattern "^infra:.*"

    # Assign project to layer
    python manage.py manage_layers assign core:auth domain

    # Auto-assign projects based on patterns
    python manage.py manage_layers auto-assign

    # Show violations
    python manage.py manage_layers violations
"""
import re
from django.core.management.base import BaseCommand
from django.db import transaction
from dependencies.models import Component, Dependency, LayerDefinition, LayerAssignment


class Command(BaseCommand):
    help = 'Manage architectural layer definitions'

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(dest='action', help='Action to perform')

        # list
        list_parser = subparsers.add_parser('list', help='List all layer definitions')

        # create
        create_parser = subparsers.add_parser('create', help='Create layer definition')
        create_parser.add_argument('name', type=str, help='Layer name')
        create_parser.add_argument('level', type=int, help='Layer level (0=lowest)')
        create_parser.add_argument('--description', type=str, default='', help='Layer description')
        create_parser.add_argument('--pattern', type=str, default='', help='Regex pattern for auto-assignment')

        # delete
        delete_parser = subparsers.add_parser('delete', help='Delete layer definition')
        delete_parser.add_argument('name', type=str, help='Layer name to delete')

        # assign
        assign_parser = subparsers.add_parser('assign', help='Assign project to layer')
        assign_parser.add_argument('project', type=str, help='Project key')
        assign_parser.add_argument('layer', type=str, help='Layer name')

        # unassign
        unassign_parser = subparsers.add_parser('unassign', help='Remove project from layer')
        unassign_parser.add_argument('project', type=str, help='Project key')

        # auto-assign
        auto_parser = subparsers.add_parser('auto-assign', help='Auto-assign projects based on patterns')
        auto_parser.add_argument('--dry-run', action='store_true', help='Show what would be assigned')

        # show
        show_parser = subparsers.add_parser('show', help='Show layer assignments')

    def handle(self, *args, **options):
        action = options.get('action')

        if not action:
            self.stdout.write(self.style.ERROR("Please specify an action: list, create, delete, assign, unassign, auto-assign, show"))
            return

        handler = {
            'list': self._handle_list,
            'create': self._handle_create,
            'delete': self._handle_delete,
            'assign': self._handle_assign,
            'unassign': self._handle_unassign,
            'auto-assign': self._handle_auto_assign,
            'show': self._handle_show,
        }.get(action)

        if handler:
            handler(options)
        else:
            self.stdout.write(self.style.ERROR(f"Unknown action: {action}"))

    def _handle_list(self, options):
        """List all layer definitions."""
        layers = LayerDefinition.objects.all().order_by('level')

        if not layers.exists():
            self.stdout.write(self.style.WARNING("No layers defined. Use 'create' to add layers."))
            return

        self.stdout.write(self.style.SUCCESS("\nArchitectural Layers:"))
        self.stdout.write("-" * 60)

        for layer in layers:
            assignment_count = layer.assignments.count()
            self.stdout.write(f"\n  Level {layer.level}: {layer.name}")
            if layer.description:
                self.stdout.write(f"    Description: {layer.description}")
            if layer.pattern:
                self.stdout.write(f"    Pattern: {layer.pattern}")
            self.stdout.write(f"    Assigned projects: {assignment_count}")

    def _handle_create(self, options):
        """Create a layer definition."""
        name = options['name']
        level = options['level']
        description = options.get('description', '')
        pattern = options.get('pattern', '')

        # Validate pattern if provided
        if pattern:
            try:
                re.compile(pattern)
            except re.error as e:
                self.stdout.write(self.style.ERROR(f"Invalid regex pattern: {e}"))
                return

        # Check if layer already exists
        if LayerDefinition.objects.filter(name=name).exists():
            self.stdout.write(self.style.ERROR(f"Layer '{name}' already exists"))
            return

        layer = LayerDefinition.objects.create(
            name=name,
            level=level,
            description=description,
            pattern=pattern,
        )

        self.stdout.write(self.style.SUCCESS(f"Created layer '{name}' at level {level}"))

    def _handle_delete(self, options):
        """Delete a layer definition."""
        name = options['name']

        try:
            layer = LayerDefinition.objects.get(name=name)
            assignment_count = layer.assignments.count()

            if assignment_count > 0:
                self.stdout.write(
                    self.style.WARNING(f"Layer '{name}' has {assignment_count} assignments. They will be deleted.")
                )

            layer.delete()
            self.stdout.write(self.style.SUCCESS(f"Deleted layer '{name}'"))
        except LayerDefinition.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Layer '{name}' not found"))

    def _handle_assign(self, options):
        """Assign a component to a layer."""
        component_key = options['project']  # Keep arg name for CLI compatibility
        layer_name = options['layer']

        # Try to find component by Maven coordinates or UUID
        component = None
        if ':' in component_key:
            parts = component_key.split(':', 1)
            component = Component.objects.filter(group_id=parts[0], artifact_id=parts[1]).first()
        if not component:
            try:
                component = Component.objects.get(id=component_key)
            except (Component.DoesNotExist, ValueError):
                pass
        if not component:
            component = Component.objects.filter(name=component_key).first()

        if not component:
            self.stdout.write(self.style.ERROR(f"Component '{component_key}' not found"))
            return

        try:
            layer = LayerDefinition.objects.get(name=layer_name)
        except LayerDefinition.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Layer '{layer_name}' not found"))
            return

        assignment, created = LayerAssignment.objects.update_or_create(
            component=component,
            defaults={'layer': layer, 'auto_assigned': False}
        )

        if created:
            self.stdout.write(self.style.SUCCESS(f"Assigned '{component.name}' to layer '{layer_name}'"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Updated '{component.name}' to layer '{layer_name}'"))

    def _handle_unassign(self, options):
        """Remove component from layer."""
        component_key = options['project']

        # Try to find assignment by component Maven coordinates, UUID, or name
        assignment = None
        if ':' in component_key:
            parts = component_key.split(':', 1)
            assignment = LayerAssignment.objects.filter(
                component__group_id=parts[0],
                component__artifact_id=parts[1]
            ).first()
        if not assignment:
            try:
                assignment = LayerAssignment.objects.get(component__id=component_key)
            except (LayerAssignment.DoesNotExist, ValueError):
                pass
        if not assignment:
            assignment = LayerAssignment.objects.filter(component__name=component_key).first()

        if assignment:
            component_name = assignment.component.name
            assignment.delete()
            self.stdout.write(self.style.SUCCESS(f"Removed layer assignment for '{component_name}'"))
        else:
            self.stdout.write(self.style.WARNING(f"Component '{component_key}' has no layer assignment"))

    @transaction.atomic
    def _handle_auto_assign(self, options):
        """Auto-assign components based on layer patterns."""
        dry_run = options.get('dry_run', False)

        layers = LayerDefinition.objects.exclude(pattern='').order_by('level')
        components = Component.objects.all()

        if not layers.exists():
            self.stdout.write(self.style.WARNING("No layers with patterns defined"))
            return

        assignments = []
        for component in components:
            # Skip if already manually assigned
            existing = LayerAssignment.objects.filter(
                component=component, auto_assigned=False
            ).first()
            if existing:
                continue

            # Use Maven coordinate as key for pattern matching
            component_key = component.key
            for layer in layers:
                if layer.pattern and re.match(layer.pattern, component_key):
                    assignments.append((component, layer))
                    break

        if not assignments:
            self.stdout.write(self.style.WARNING("No components matched any layer patterns"))
            return

        if dry_run:
            self.stdout.write(self.style.SUCCESS("\nWould assign (dry run):"))
            for component, layer in assignments:
                self.stdout.write(f"  {component.name} -> {layer.name}")
        else:
            count = 0
            for component, layer in assignments:
                LayerAssignment.objects.update_or_create(
                    component=component,
                    defaults={'layer': layer, 'auto_assigned': True}
                )
                count += 1

            self.stdout.write(self.style.SUCCESS(f"Auto-assigned {count} components"))

    def _handle_show(self, options):
        """Show all layer assignments."""
        assignments = LayerAssignment.objects.select_related(
            'component', 'layer'
        ).order_by('layer__level', 'component__name')

        if not assignments.exists():
            self.stdout.write(self.style.WARNING("No layer assignments. Use 'assign' or 'auto-assign'."))
            return

        self.stdout.write(self.style.SUCCESS("\nLayer Assignments:"))
        self.stdout.write("-" * 60)

        current_layer = None
        for assignment in assignments:
            if assignment.layer != current_layer:
                current_layer = assignment.layer
                self.stdout.write(f"\n  [{assignment.layer.level}] {assignment.layer.name}:")

            auto = " (auto)" if assignment.auto_assigned else ""
            self.stdout.write(f"    - {assignment.component.name}{auto}")
