"""
Sync Maven dependencies from GitLab repositories using maven-dependencies library.

This command uses the maven-dependencies library to build a complete static
Maven dependency graph from Git-hosted repositories without running Maven.
"""
import os
from django.core.management.base import BaseCommand
from django.db import transaction

from dependencies.models import Component, Dependency, NodeGroup, GitProject
from dependencies.service import GitLabService, DEFAULT_POM_CACHE_DIR


class Command(BaseCommand):
    help = 'Sync Maven dependencies from GitLab using maven-dependencies library'

    def add_arguments(self, parser):
        parser.add_argument(
            '--url',
            type=str,
            help='GitLab instance URL (default: GITLAB_URL env var)',
        )
        parser.add_argument(
            '--token',
            type=str,
            help='GitLab personal access token (default: GITLAB_TOKEN env var)',
        )
        parser.add_argument(
            '--cache-dir',
            type=str,
            default=DEFAULT_POM_CACHE_DIR,
            help=f'Directory for caching (default: {DEFAULT_POM_CACHE_DIR})',
        )
        parser.add_argument(
            '--project',
            type=str,
            action='append',
            dest='projects',
            help='GitLab project path (can be specified multiple times). If not specified, syncs all projects.',
        )
        parser.add_argument(
            '--ref',
            type=str,
            default='HEAD',
            help='Git ref to analyze (default: HEAD)',
        )
        parser.add_argument(
            '--internal-group-prefix',
            type=str,
            default='',
            help='Maven groupId prefix to identify internal packages (e.g., "com.mycompany")',
        )
        parser.add_argument(
            '--include-test-scope',
            action='store_true',
            default=False,
            help='Include test-scope dependencies',
        )
        parser.add_argument(
            '--include-optional',
            action='store_true',
            default=False,
            help='Include optional dependencies',
        )
        parser.add_argument(
            '--include-plugins',
            action='store_true',
            default=False,
            help='Include Maven plugins as dependencies',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )
        parser.add_argument(
            '--by-group',
            action='store_true',
            help='Fetch projects by iterating through GitLab groups',
        )
        parser.add_argument(
            '--all-visible',
            action='store_true',
            help='Fetch all visible GitLab projects',
        )

    def handle(self, *args, **options):
        try:
            from maven_dependencies import resolve_repository_graph, GraphResult
        except ImportError:
            self.stderr.write(self.style.ERROR(
                'maven-dependencies library not installed.\n'
                'Install it with: pip install git+https://github.com/mikko-ahonen/maven-dependencies.git'
            ))
            return

        gitlab_url = options.get('url') or os.environ.get('GITLAB_URL')
        gitlab_token = options.get('token') or os.environ.get('GITLAB_TOKEN')
        cache_dir = options['cache_dir']
        ref = options['ref']
        internal_prefix = options.get('internal_group_prefix', '')
        dry_run = options['dry_run']
        include_test = options['include_test_scope']
        include_optional = options['include_optional']
        include_plugins = options['include_plugins']

        if not gitlab_url:
            self.stderr.write(self.style.ERROR('GitLab URL required (--url or GITLAB_URL env var)'))
            return

        # Get list of projects to sync
        project_paths = options.get('projects')
        if not project_paths:
            if not gitlab_token:
                self.stderr.write(self.style.ERROR('GitLab token required to list projects'))
                return

            self.stdout.write('Fetching project list from GitLab...')
            service = GitLabService(gitlab_url, gitlab_token)

            if options.get('by_group'):
                projects = list(service.get_all_projects_by_group())
            else:
                membership = None if options.get('all_visible') else True
                projects = list(service.get_projects(membership=membership))

            project_paths = [p.path_with_namespace for p in projects]
            self.stdout.write(f'Found {len(project_paths)} projects')

        # Process each project
        total_components = 0
        total_deps = 0
        errors = []

        for project_path in project_paths:
            repo_url = f'{gitlab_url.rstrip("/")}/{project_path}.git'
            self.stdout.write(f'\nProcessing: {project_path}')

            try:
                result = resolve_repository_graph(
                    repo_url=repo_url,
                    ref=ref,
                    cache_dir=cache_dir,
                    include_plugins=include_plugins,
                    include_extensions=False,
                    include_plugin_transitive=False,
                    include_optional=include_optional,
                    include_test_scope=include_test,
                )

                if result.issues:
                    for issue in result.issues[:3]:  # Show first 3 issues
                        self.stdout.write(self.style.WARNING(f'  Issue: {issue}'))
                    if len(result.issues) > 3:
                        self.stdout.write(self.style.WARNING(f'  ... and {len(result.issues) - 3} more issues'))

                components, deps = self._process_graph_result(
                    result, project_path, internal_prefix, dry_run
                )
                total_components += components
                total_deps += deps
                self.stdout.write(f'  Components: {components}, Dependencies: {deps}')

            except Exception as e:
                errors.append((project_path, str(e)))
                self.stderr.write(self.style.ERROR(f'  Error: {e}'))

        # Summary
        self.stdout.write(self.style.SUCCESS(f'\nSync complete:'))
        self.stdout.write(f'  Total components: {total_components}')
        self.stdout.write(f'  Total dependencies: {total_deps}')
        if errors:
            self.stdout.write(self.style.WARNING(f'  Errors: {len(errors)}'))

    def _parse_node_id(self, node_id: str) -> tuple[str, str, str, str] | None:
        """Parse a node ID like 'artifact:group:artifact:version' into parts.

        Returns (kind, group_id, artifact_id, version) or None if invalid.
        """
        parts = node_id.split(':')
        if len(parts) < 3:
            return None

        kind = parts[0]
        # Node IDs are kind:groupId:artifactId:version
        # But groupId might contain colons, so we need to handle that
        # Format: kind:group:artifact:version (4+ parts)
        if len(parts) >= 4:
            group_id = parts[1]
            artifact_id = parts[2]
            version = ':'.join(parts[3:]) if len(parts) > 3 else ''
            return kind, group_id, artifact_id, version

        return None

    def _process_graph_result(self, result, project_path, internal_prefix, dry_run):
        """Process GraphResult and create/update Components and Dependencies."""
        if dry_run:
            return len(result.nodes), len(result.edges)

        components_by_node_id = {}
        components_by_key = {}
        created_components = 0
        created_deps = 0

        with transaction.atomic():
            # First pass: create all components from nodes
            for node in result.nodes:
                # Skip non-artifact nodes (modules, etc.)
                if node.node_type not in ('artifact', 'project', 'parent', 'bom'):
                    continue

                parsed = self._parse_node_id(node.id)
                if not parsed:
                    continue

                kind, group_id, artifact_id, version = parsed
                key = f"{group_id}:{artifact_id}"

                # Skip if already processed
                if key in components_by_key:
                    components_by_node_id[node.id] = components_by_key[key]
                    continue

                # Determine if internal
                is_internal = False
                if internal_prefix and group_id.startswith(internal_prefix):
                    is_internal = True

                # Get or create group hierarchy
                group = None
                if group_id:
                    group = self._get_or_create_group(group_id)

                component, created = Component.objects.get_or_create(
                    key=key,
                    defaults={
                        'name': artifact_id,
                        'maven_group_id': group_id,
                        'artifact_id': artifact_id,
                        'version': version or '',
                        'component_type': 'java',
                        'internal': is_internal,
                        'group': group,
                    }
                )

                if not created and version:
                    # Update version if provided
                    if version != component.version:
                        component.version = version
                        component.save(update_fields=['version'])

                components_by_key[key] = component
                components_by_node_id[node.id] = component
                if created:
                    created_components += 1

            # Second pass: create dependencies from edges
            for edge in result.edges:
                source = components_by_node_id.get(edge.from_node)
                target = components_by_node_id.get(edge.to_node)

                if not source or not target:
                    continue

                # Skip self-dependencies
                if source == target:
                    continue

                scope = edge.scope or 'compile'

                _, created = Dependency.objects.get_or_create(
                    source=source,
                    target=target,
                    scope=scope,
                    defaults={'weight': 1}
                )
                if created:
                    created_deps += 1

            # Link to GitProject if exists
            try:
                git_project = GitProject.objects.get(path_with_namespace=project_path)
                # Find the root component (project nodes, matching project name)
                project_name = project_path.split('/')[-1]
                for node in result.nodes:
                    if node.node_type == 'project':
                        parsed = self._parse_node_id(node.id)
                        if parsed:
                            _, group_id, artifact_id, _ = parsed
                            if artifact_id == project_name or project_name in artifact_id:
                                key = f"{group_id}:{artifact_id}"
                                if key in components_by_key:
                                    git_project.component = components_by_key[key]
                                    git_project.save(update_fields=['component'])
                                    break
            except GitProject.DoesNotExist:
                pass

        return created_components, created_deps

    def _get_or_create_group(self, group_id: str) -> NodeGroup:
        """Get or create a NodeGroup hierarchy from a Maven groupId."""
        parts = group_id.split('.')
        parent = None

        for i in range(len(parts)):
            key = '.'.join(parts[:i + 1])
            name = parts[i]

            group, _ = NodeGroup.objects.get_or_create(
                key=key,
                defaults={
                    'name': name,
                    'parent': parent,
                }
            )
            parent = group

        return parent
