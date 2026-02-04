"""
Sync project dependencies from GitLab by extracting and parsing pom.xml files.

Phase 1: Extract all pom.xml files from visible GitLab projects (cached locally)
Phase 2: Parse cached pom.xml files to create projects, groups, and dependencies
"""
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from dependencies.models import Project, Dependency, NodeGroup
from dependencies.service import GitLabService, GitLabProject, DEFAULT_POM_CACHE_DIR


class Command(BaseCommand):
    help = 'Synchronize projects and dependencies from GitLab pom.xml files'

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
            help=f'Directory for caching pom.xml files (default: {DEFAULT_POM_CACHE_DIR})',
        )
        parser.add_argument(
            '--phase',
            type=int,
            choices=[1, 2],
            help='Run only specific phase: 1=extract pom.xml, 2=process and create dependencies',
        )
        parser.add_argument(
            '--extract-only',
            action='store_true',
            help='Only extract pom.xml files (Phase 1), skip processing',
        )
        parser.add_argument(
            '--process-only',
            action='store_true',
            help='Only process cached pom.xml files (Phase 2), skip extraction',
        )
        parser.add_argument(
            '--no-cache',
            action='store_true',
            help='Re-fetch pom.xml files even if cached',
        )
        parser.add_argument(
            '--request-delay',
            type=float,
            help='Seconds to wait between API requests (default: 0.1)',
        )
        parser.add_argument(
            '--internal-group-prefix',
            type=str,
            default='',
            help='Group ID prefix to identify internal packages (e.g., "com.mycompany")',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )
        parser.add_argument(
            '--projects-file',
            type=str,
            help='JSON file for project list (default: <cache-dir>/projects.json)',
        )
        parser.add_argument(
            '--skip-fetch-projects',
            action='store_true',
            help='Skip fetching project list from GitLab, use existing projects.json',
        )
        parser.add_argument(
            '--by-group',
            action='store_true',
            help='Fetch projects by iterating through groups (more reliable for large instances)',
        )
        parser.add_argument(
            '--all-visible',
            action='store_true',
            help='Fetch all visible projects, not just projects where you are a member',
        )

    def handle(self, *args, **options):
        # Determine which phases to run
        run_phase_1 = True
        run_phase_2 = True

        if options['phase'] == 1 or options['extract_only']:
            run_phase_2 = False
        elif options['phase'] == 2 or options['process_only']:
            run_phase_1 = False

        cache_dir = Path(options['cache_dir'])

        if run_phase_1:
            self.stdout.write(self.style.MIGRATE_HEADING('Phase 1: Extracting pom.xml files from GitLab'))
            self.phase_1_extract(options, cache_dir)

        if run_phase_2:
            self.stdout.write(self.style.MIGRATE_HEADING('\nPhase 2: Processing pom.xml files'))
            self.phase_2_process(options, cache_dir)

        self.stdout.write(self.style.SUCCESS('\nSync completed!'))

    def phase_1_extract(self, options, cache_dir: Path):
        """Phase 1: Extract pom.xml files from all visible GitLab projects."""
        service = GitLabService(
            url=options.get('url'),
            token=options.get('token'),
            cache_dir=str(cache_dir),
            request_delay=options.get('request_delay'),
        )

        # Determine projects file path
        projects_file = options.get('projects_file')
        if projects_file:
            projects_file = Path(projects_file)
        else:
            projects_file = cache_dir / 'projects.json'

        skip_fetch = options.get('skip_fetch_projects', False)
        use_cache = not options['no_cache']

        with service:
            # Step 1: Get project list (from API or file)
            if skip_fetch:
                if not projects_file.exists():
                    self.stderr.write(self.style.ERROR(
                        f'Projects file not found: {projects_file}\n'
                        f'Run without --skip-fetch-projects first to fetch the project list.'
                    ))
                    return
                self.stdout.write(f'Loading project list from {projects_file}...')
                projects = self._load_projects_from_file(projects_file)
                self.stdout.write(f'Loaded {len(projects)} projects from file')
            else:
                by_group = options.get('by_group', False)
                all_visible = options.get('all_visible', False)
                if by_group:
                    self.stdout.write('Fetching project list from GitLab (by group)...')
                elif all_visible:
                    self.stdout.write('Fetching all visible projects from GitLab...')
                else:
                    self.stdout.write('Fetching project list from GitLab (member projects only)...')
                projects = self._fetch_and_save_projects(service, projects_file, by_group=by_group, all_visible=all_visible)
                self.stdout.write(f'Fetched {len(projects)} projects, saved to {projects_file}')

            # Step 2: Process each project
            extracted = 0
            skipped_cached = 0
            skipped_no_pom = 0
            errors = 0

            for i, project in enumerate(projects, 1):
                project_path = project.path_with_namespace

                # Check cache first
                if use_cache and service.is_file_cached(project_path, 'pom.xml'):
                    skipped_cached += 1
                    self.stdout.write(f'  [{i}/{len(projects)}] {project_path}: cached')
                    continue

                try:
                    content = service.fetch_and_cache_file(project, 'pom.xml', use_cache=use_cache)
                    if content:
                        extracted += 1
                        self.stdout.write(f'  [{i}/{len(projects)}] {project_path}: extracted')
                    else:
                        skipped_no_pom += 1
                        self.stdout.write(f'  [{i}/{len(projects)}] {project_path}: no pom.xml')
                except Exception as e:
                    errors += 1
                    self.stderr.write(f'  [{i}/{len(projects)}] {project_path}: error - {e}')

        self.stdout.write(f'\nPhase 1 Summary:')
        self.stdout.write(f'  Extracted: {extracted}')
        self.stdout.write(f'  Already cached: {skipped_cached}')
        self.stdout.write(f'  No pom.xml: {skipped_no_pom}')
        self.stdout.write(f'  Errors: {errors}')

    def _fetch_and_save_projects(self, service: GitLabService, projects_file: Path, by_group: bool = False, all_visible: bool = False) -> list[GitLabProject]:
        """Fetch all projects from GitLab and save to JSON file.

        Args:
            service: GitLab service instance
            projects_file: Path to save projects JSON
            by_group: If True, fetch projects by iterating through groups (more reliable)
            all_visible: If True, fetch all visible projects (not just member projects)
        """
        projects = []
        projects_data = []

        if by_group:
            project_iter = service.get_all_projects_by_group()
        else:
            # membership=None means all visible, membership=True means only member projects
            membership = None if all_visible else True
            project_iter = service.get_projects(membership=membership)

        for project in project_iter:
            projects.append(project)
            projects_data.append({
                'id': project.id,
                'name': project.name,
                'path': project.path,
                'path_with_namespace': project.path_with_namespace,
                'description': project.description,
                'default_branch': project.default_branch,
                'namespace': project.namespace,
                'web_url': project.web_url,
            })
            # Progress indicator every 100 projects
            if len(projects) % 100 == 0:
                self.stdout.write(f'  Fetched {len(projects)} projects...')

        # Save to file
        projects_file.parent.mkdir(parents=True, exist_ok=True)
        with open(projects_file, 'w') as f:
            json.dump(projects_data, f, indent=2)

        return projects

    def _load_projects_from_file(self, projects_file: Path) -> list[GitLabProject]:
        """Load projects from JSON file."""
        with open(projects_file) as f:
            projects_data = json.load(f)

        return [
            GitLabProject(
                id=p['id'],
                name=p['name'],
                path=p['path'],
                path_with_namespace=p['path_with_namespace'],
                description=p.get('description', ''),
                default_branch=p.get('default_branch', 'main'),
                namespace=p.get('namespace', {}),
                web_url=p.get('web_url', ''),
            )
            for p in projects_data
        ]

    def phase_2_process(self, options, cache_dir: Path):
        """Phase 2: Process cached pom.xml files to create projects and dependencies."""
        internal_prefix = options.get('internal_group_prefix', '')
        dry_run = options['dry_run']

        # Find all cached pom.xml files
        pom_files = list(cache_dir.rglob('pom.xml'))
        self.stdout.write(f'Found {len(pom_files)} cached pom.xml files')

        if not pom_files:
            self.stdout.write(self.style.WARNING('No pom.xml files to process'))
            return

        # Parse all pom.xml files to extract project info and dependencies
        parsed_projects = []
        parse_errors = 0

        for pom_path in pom_files:
            try:
                parsed = self.parse_pom_xml(pom_path, cache_dir)
                if parsed:
                    parsed_projects.append(parsed)
            except Exception as e:
                parse_errors += 1
                self.stderr.write(f'  Error parsing {pom_path}: {e}')

        self.stdout.write(f'Parsed {len(parsed_projects)} projects ({parse_errors} errors)')

        if dry_run:
            self.stdout.write(self.style.WARNING('\nDry run - not making changes'))
            for proj in parsed_projects[:10]:  # Show first 10
                self.stdout.write(f"  Project: {proj['key']} ({len(proj['dependencies'])} deps)")
            if len(parsed_projects) > 10:
                self.stdout.write(f"  ... and {len(parsed_projects) - 10} more")
            return

        # Create/update projects, groups, and dependencies
        with transaction.atomic():
            created_projects = 0
            updated_projects = 0
            created_groups = 0
            created_deps = 0

            # Build lookup of internal project keys
            internal_keys = {p['key'] for p in parsed_projects}

            for proj_data in parsed_projects:
                # Create or update group
                group = None
                if proj_data['group_id']:
                    group, created = self.get_or_create_group(proj_data['group_id'])
                    if created:
                        created_groups += 1

                # Create or update project
                project, created = Project.objects.update_or_create(
                    key=proj_data['key'],
                    defaults={
                        'name': proj_data['name'],
                        'description': proj_data.get('description', ''),
                        'group': group,
                        'internal': True,
                    }
                )
                if created:
                    created_projects += 1
                else:
                    updated_projects += 1

            # Second pass: create dependencies
            for proj_data in parsed_projects:
                source = Project.objects.get(key=proj_data['key'])

                for dep in proj_data['dependencies']:
                    dep_key = dep['key']
                    dep_scope = dep.get('scope', 'compile')

                    # Determine if dependency is internal or external
                    is_internal = dep_key in internal_keys
                    if not is_internal and internal_prefix:
                        is_internal = dep['group_id'].startswith(internal_prefix)

                    # Get or create target project
                    target, _ = Project.objects.get_or_create(
                        key=dep_key,
                        defaults={
                            'name': dep.get('artifact_id', dep_key),
                            'internal': is_internal,
                        }
                    )

                    # Create dependency if not exists
                    _, created = Dependency.objects.get_or_create(
                        source=source,
                        target=target,
                        scope=dep_scope,
                        defaults={'weight': 1}
                    )
                    if created:
                        created_deps += 1

            self.stdout.write(f'\nPhase 2 Summary:')
            self.stdout.write(f'  Projects created: {created_projects}')
            self.stdout.write(f'  Projects updated: {updated_projects}')
            self.stdout.write(f'  Groups created: {created_groups}')
            self.stdout.write(f'  Dependencies created: {created_deps}')

    def parse_pom_xml(self, pom_path: Path, cache_dir: Path) -> dict | None:
        """Parse a pom.xml file and extract project info and dependencies.

        Returns:
            Dict with keys: key, name, group_id, artifact_id, version, description, dependencies
            Or None if parsing fails
        """
        try:
            tree = ET.parse(pom_path)
            root = tree.getroot()
        except ET.ParseError as e:
            raise ValueError(f"Invalid XML: {e}")

        # Handle Maven namespace
        ns = {'m': 'http://maven.apache.org/POM/4.0.0'}
        def find(elem, path):
            """Find element with or without namespace."""
            result = elem.find(f'm:{path}', ns)
            if result is None:
                result = elem.find(path)
            return result

        def findtext(elem, path, default=''):
            """Get text content with or without namespace."""
            el = find(elem, path)
            return el.text.strip() if el is not None and el.text else default

        # Extract project coordinates
        group_id = findtext(root, 'groupId')
        artifact_id = findtext(root, 'artifactId')
        version = findtext(root, 'version')
        name = findtext(root, 'name') or artifact_id
        description = findtext(root, 'description')

        # If groupId not in project, check parent
        if not group_id:
            parent = find(root, 'parent')
            if parent is not None:
                group_id = findtext(parent, 'groupId')

        if not group_id or not artifact_id:
            # Get project path from file location for better error message
            rel_path = pom_path.relative_to(cache_dir)
            raise ValueError(f"Missing groupId or artifactId in {rel_path}")

        # Build project key
        project_key = f"{group_id}:{artifact_id}"

        # Extract dependencies
        dependencies = []
        deps_elem = find(root, 'dependencies')
        if deps_elem is not None:
            for dep in deps_elem.findall('m:dependency', ns) or deps_elem.findall('dependency'):
                dep_group = findtext(dep, 'groupId')
                dep_artifact = findtext(dep, 'artifactId')
                dep_version = findtext(dep, 'version')
                dep_scope = findtext(dep, 'scope') or 'compile'
                dep_optional = findtext(dep, 'optional') == 'true'

                if dep_group and dep_artifact:
                    # Skip test dependencies by default
                    if dep_scope == 'test':
                        continue

                    dependencies.append({
                        'key': f"{dep_group}:{dep_artifact}",
                        'group_id': dep_group,
                        'artifact_id': dep_artifact,
                        'version': dep_version,
                        'scope': dep_scope if dep_scope != 'compile' else 'compile',
                        'optional': dep_optional,
                    })

        return {
            'key': project_key,
            'name': name,
            'group_id': group_id,
            'artifact_id': artifact_id,
            'version': version,
            'description': description,
            'dependencies': dependencies,
            'pom_path': str(pom_path),
        }

    def get_or_create_group(self, group_id: str) -> tuple[NodeGroup, bool]:
        """Get or create a NodeGroup from a Maven groupId.

        Converts dot-separated groupId (e.g., com.example.service) to
        hierarchical NodeGroup structure.

        Returns:
            Tuple of (NodeGroup, created)
        """
        parts = group_id.split('.')
        parent = None
        created = False

        for i, part in enumerate(parts):
            key = '.'.join(parts[:i+1])
            name = part

            group, was_created = NodeGroup.objects.get_or_create(
                key=key,
                defaults={
                    'name': name,
                    'parent': parent,
                }
            )

            if was_created:
                created = True

            # Update parent if it changed
            if group.parent != parent:
                group.parent = parent
                group.save()

            parent = group

        return parent, created
