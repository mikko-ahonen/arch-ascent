import logging
import re
from datetime import datetime
from django.utils import timezone
from .models import Project, Dependency, NodeGroup
from .service import SonarQubeService, CheckmarxService

logger = logging.getLogger(__name__)

# Separators to detect groups in project keys (order matters - check most specific first)
GROUP_SEPARATORS = [':', '/', '.']


def extract_group_from_key(key: str) -> tuple[str | None, str]:
    """
    Extract group prefix from project key based on common naming conventions.

    Examples:
        'com.company:auth-service' -> ('com.company', 'auth-service')
        'backend/auth-service' -> ('backend', 'auth-service')
        'com.company.auth.service' -> ('com.company.auth', 'service')
        'auth-service' -> (None, 'auth-service')

    Returns:
        Tuple of (group_key, project_name) where group_key may be None
    """
    for sep in GROUP_SEPARATORS:
        if sep in key:
            # Split on the separator
            parts = key.rsplit(sep, 1)
            if len(parts) == 2 and parts[0] and parts[1]:
                group_key = parts[0]
                project_name = parts[1]
                return (group_key, project_name)

    return (None, key)


def create_group_name(group_key: str) -> str:
    """
    Create a human-readable group name from a group key.

    Examples:
        'com.company.backend' -> 'Com Company Backend'
        'platform/services' -> 'Platform Services'
    """
    # Replace separators with spaces
    name = re.sub(r'[.:/]', ' ', group_key)
    # Title case
    name = name.title()
    return name


def sync_projects(service: SonarQubeService | None = None) -> int:
    """Synchronize all projects from SonarQube to local database."""
    if service is None:
        service = SonarQubeService()

    synced = 0
    groups_cache: dict[str, NodeGroup] = {}

    # Load existing groups
    for group in NodeGroup.objects.all():
        groups_cache[group.key] = group

    with service:
        for sonar_project in service.get_projects():
            last_analysis = None
            if sonar_project.last_analysis:
                try:
                    last_analysis = datetime.fromisoformat(
                        sonar_project.last_analysis.replace('Z', '+00:00')
                    )
                except ValueError:
                    pass

            # Extract group from project key
            group_key, _ = extract_group_from_key(sonar_project.key)
            group = None

            if group_key:
                # Get or create group
                if group_key not in groups_cache:
                    group, created = NodeGroup.objects.get_or_create(
                        key=group_key,
                        defaults={'name': create_group_name(group_key)}
                    )
                    groups_cache[group_key] = group
                    if created:
                        logger.info(f"Created group: {group_key}")
                else:
                    group = groups_cache[group_key]

            Project.objects.update_or_create(
                key=sonar_project.key,
                defaults={
                    'name': sonar_project.name,
                    'description': sonar_project.description,
                    'qualifier': sonar_project.qualifier,
                    'visibility': sonar_project.visibility,
                    'last_analysis': last_analysis,
                    'synced_at': timezone.now(),
                    'group': group,
                }
            )
            synced += 1
            logger.info(f"Synced project: {sonar_project.key}" + (f" -> group: {group_key}" if group_key else ""))

    return synced


def sync_dependencies(service: SonarQubeService | None = None) -> int:
    """Synchronize dependencies for all local projects."""
    if service is None:
        service = SonarQubeService()

    synced = 0
    projects = {p.key: p for p in Project.objects.all()}

    with service:
        for project in projects.values():
            for dep in service.get_dependencies(project.key):
                target = projects.get(dep.target_key)
                if target:
                    Dependency.objects.update_or_create(
                        source=project,
                        target=target,
                        scope=dep.scope,
                        defaults={'weight': dep.weight}
                    )
                    synced += 1
                    logger.info(f"Synced dependency: {dep.source_key} -> {dep.target_key}")

    return synced


# =============================================================================
# Checkmarx Sync Functions
# =============================================================================


def sync_checkmarx_projects(service: CheckmarxService | None = None) -> int:
    """Synchronize all projects from Checkmarx SCA to local database."""
    if service is None:
        service = CheckmarxService()

    synced = 0
    groups_cache: dict[str, NodeGroup] = {}

    # Load existing groups
    for group in NodeGroup.objects.all():
        groups_cache[group.key] = group

    with service:
        for cx_project in service.get_projects():
            # Use project name as key (prefix with cx: to distinguish from SonarQube)
            project_key = f"cx:{cx_project.name}"

            # Extract group from project name
            group_key, _ = extract_group_from_key(cx_project.name)
            group = None

            if group_key:
                # Prefix group key to distinguish from SonarQube groups
                cx_group_key = f"cx:{group_key}"
                if cx_group_key not in groups_cache:
                    group, created = NodeGroup.objects.get_or_create(
                        key=cx_group_key,
                        defaults={'name': create_group_name(group_key)}
                    )
                    groups_cache[cx_group_key] = group
                    if created:
                        logger.info(f"Created Checkmarx group: {cx_group_key}")
                else:
                    group = groups_cache[cx_group_key]

            Project.objects.update_or_create(
                key=project_key,
                defaults={
                    'name': cx_project.name,
                    'description': f'Checkmarx SCA project (ID: {cx_project.id})',
                    'qualifier': 'CX',
                    'visibility': 'public',
                    'synced_at': timezone.now(),
                    'group': group,
                }
            )
            synced += 1
            logger.info(f"Synced Checkmarx project: {project_key}" + (f" -> group: {group_key}" if group_key else ""))

    return synced


def export_checkmarx_sboms(
    service: CheckmarxService,
    on_progress: callable = None,
) -> dict:
    """Export SBOMs for all Checkmarx projects sequentially.

    Processes one project at a time:
    1. Fetch project
    2. Get scans for project
    3. Export SBOM if not cached
    4. Move to next project

    All request throttling is handled by the service's request_delay setting.
    HTTP errors will propagate and stop processing immediately.

    Args:
        service: CheckmarxService instance
        on_progress: Optional callback(exported, skipped, processed) for progress updates

    Returns:
        dict with 'exported', 'skipped' counts
    """
    result = {'exported': 0, 'skipped': 0}
    processed = 0

    # Process projects one at a time using the generator
    for cx_project in service.get_projects():
        processed += 1
        logger.info(f"Processing project {processed}: {cx_project.name}")

        # Get latest scan for this project
        scans = service.get_scans(cx_project.id)
        if not scans:
            logger.info(f"  No scans found for {cx_project.name}")
            if on_progress:
                on_progress(result['exported'], result['skipped'], processed)
            continue

        scan_id = scans[0].get('id') or scans[0].get('scanId')
        if not scan_id:
            logger.info(f"  No scan ID found for {cx_project.name}")
            if on_progress:
                on_progress(result['exported'], result['skipped'], processed)
            continue

        # Check if already cached
        if service.is_sbom_cached(scan_id):
            result['skipped'] += 1
            logger.info(f"  SBOM already cached (scan: {scan_id})")
        else:
            service.export_sbom(scan_id, use_cache=False)
            result['exported'] += 1
            logger.info(f"  Exported SBOM (scan: {scan_id})")

        if on_progress:
            on_progress(result['exported'], result['skipped'], processed)

    logger.info(f"Completed: {result['exported']} exported, {result['skipped']} cached")
    return result


def sync_checkmarx_dependencies(
    service: CheckmarxService | None = None,
    use_cached_only: bool = False,
) -> int:
    """Synchronize dependencies from Checkmarx SCA for all local projects.

    Args:
        service: CheckmarxService instance
        use_cached_only: If True, only process projects with cached SBOMs

    Returns:
        Number of dependencies synced
    """
    if service is None:
        service = CheckmarxService()

    synced = 0
    # Get all Checkmarx projects (those with cx: prefix)
    projects = {p.key: p for p in Project.objects.filter(key__startswith='cx:')}

    with service:
        for cx_project in service.get_projects():
            project_key = f"cx:{cx_project.name}"
            project = projects.get(project_key)

            if not project:
                continue

            # Get the latest scan
            scans = service.get_scans(cx_project.id)
            if not scans:
                continue

            scan_id = scans[0].get('id') or scans[0].get('scanId')
            if not scan_id:
                continue

            # Skip if not cached and use_cached_only is True
            if use_cached_only and not service.is_sbom_cached(scan_id):
                logger.debug(f"Skipping {project_key}: SBOM not cached")
                continue

            for dep in service.get_dependencies_from_sbom(scan_id, cx_project.id):
                # Create package as a project if it doesn't exist
                package_key = f"pkg:{dep.package_name}"
                target, _ = Project.objects.get_or_create(
                    key=package_key,
                    defaults={
                        'name': dep.package_name,
                        'description': f'External package (version: {dep.version})',
                        'qualifier': 'PKG',
                    }
                )

                Dependency.objects.update_or_create(
                    source=project,
                    target=target,
                    defaults={
                        'scope': 'direct' if dep.is_direct else 'transitive',
                        'weight': 1,
                    }
                )
                synced += 1
                logger.info(f"Synced Checkmarx dependency: {project_key} -> {package_key}")

    return synced


def parse_purl(purl: str) -> dict:
    """Parse a purl into its components.

    Example: pkg:maven/fi.company.foo/Bar@1.0 -> {
        'type': 'maven',
        'namespace': 'fi.company.foo',
        'artifact': 'Bar',
        'version': '1.0'
    }
    """
    result = {'type': None, 'namespace': None, 'artifact': None, 'version': None}

    if not purl or not purl.startswith('pkg:'):
        return result

    # Remove pkg: prefix
    path = purl[4:]

    # Extract version
    if '@' in path:
        path, result['version'] = path.rsplit('@', 1)

    # Split by / to get [type, namespace, name] or [type, name]
    parts = path.split('/')
    if len(parts) >= 2:
        result['type'] = parts[0]
    if len(parts) >= 3:
        result['namespace'] = parts[1]
        result['artifact'] = parts[2]
    elif len(parts) == 2:
        result['artifact'] = parts[1]

    return result


def strip_purl_version(purl: str) -> tuple[str, str | None]:
    """Strip the version from a purl.

    Args:
        purl: Full purl like 'pkg:maven/org.example/lib@1.0.0'

    Returns:
        Tuple of (purl_without_version, version)
        e.g., ('pkg:maven/org.example/lib', '1.0.0')
    """
    if not purl:
        return purl, None

    if '@' in purl:
        base, version = purl.rsplit('@', 1)
        return base, version

    return purl, None


def extract_group_from_purl(purl: str, internal_prefix: str | None) -> tuple[str | None, str, str]:
    """Extract group, basename, and full name from a purl.

    Args:
        purl: The package URL (e.g., pkg:maven/fi.company.foo/Bar@1.0)
        internal_prefix: Prefix for internal packages (e.g., pkg:maven/fi.company)

    Returns:
        Tuple of (group_key, basename, full_name)
        - group_key: The sub-namespace after internal prefix (e.g., "foo.bar" for hierarchy)
        - basename: The artifact name (e.g., "Bar")
        - full_name: namespace.artifact (e.g., "fi.company.foo.Bar")
    """
    parsed = parse_purl(purl)
    namespace = parsed['namespace'] or ''
    artifact = parsed['artifact'] or ''

    # Build full name: namespace.artifact
    if namespace and artifact:
        full_name = f"{namespace}.{artifact}"
    elif artifact:
        full_name = artifact
    else:
        full_name = purl

    basename = artifact or purl

    # Extract group from namespace (relative to internal prefix)
    group_key = None
    if internal_prefix and namespace:
        # Parse the internal prefix to get its namespace
        prefix_parsed = parse_purl(internal_prefix)
        prefix_ns = prefix_parsed['namespace'] or ''

        if namespace.startswith(prefix_ns):
            # Get the part after the prefix namespace
            remainder = namespace[len(prefix_ns):].lstrip('.')
            if remainder:
                group_key = remainder

    return (group_key, basename, full_name)


def get_or_create_group_hierarchy(group_key: str, groups_cache: dict) -> 'NodeGroup':
    """Get or create a group and all its parent groups.

    For group_key "foo.bar.baz", creates:
    - "foo" (parent=None, name="Foo")
    - "foo.bar" (parent=foo, name="Bar")
    - "foo.bar.baz" (parent=foo.bar, name="Baz")

    Returns the deepest (leaf) group.
    """
    if group_key in groups_cache:
        return groups_cache[group_key]

    parts = group_key.split('.')
    parent = None
    current_key = ''

    for i, part in enumerate(parts):
        if current_key:
            current_key = f"{current_key}.{part}"
        else:
            current_key = part

        if current_key in groups_cache:
            parent = groups_cache[current_key]
        else:
            # Capitalize the display name
            display_name = part.replace('_', ' ').replace('-', ' ')
            display_name = ' '.join(word.capitalize() for word in display_name.split())

            group, created = NodeGroup.objects.get_or_create(
                key=current_key,
                defaults={
                    'name': display_name,
                    'parent': parent,
                }
            )
            # Update parent if it was created without one
            if not created and group.parent != parent and parent is not None:
                group.parent = parent
                group.save(update_fields=['parent'])

            groups_cache[current_key] = group
            parent = group

            if created:
                logger.info(f"Created group: {current_key} (parent: {parent.parent.key if parent.parent else None})")

    return groups_cache[group_key]


def import_from_cached_sboms(
    cache_dir,
    internal_prefix: str = None,
    on_progress: callable = None,
) -> dict:
    """Import projects and dependencies from cached SBOM JSON files.

    This is a fully offline operation - no HTTP requests are made.
    Projects and dependencies are extracted directly from CycloneDX JSON files.

    Args:
        cache_dir: Path to directory containing cached SBOM JSON files
        internal_prefix: Purl prefix for internal packages (e.g., "pkg:maven/fi.company")
        on_progress: Optional callback(projects_count, dependencies_count)

    Returns:
        dict with 'projects' and 'dependencies' counts
    """
    import json
    from pathlib import Path

    cache_path = Path(cache_dir)
    result = {'projects': 0, 'dependencies': 0}

    # Build a lookup of bom-ref -> Project for dependency resolution
    projects_cache: dict[str, Project] = {}
    groups_cache: dict[str, NodeGroup] = {}

    # Load existing groups
    for group in NodeGroup.objects.all():
        groups_cache[group.key] = group

    # Track bom-ref -> version-less key mapping for dependency resolution
    bomref_to_key: dict[str, str] = {}

    # First pass: create all projects from all SBOM files
    for sbom_file in cache_path.glob('*.json'):
        try:
            with open(sbom_file) as f:
                sbom = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to read {sbom_file}: {e}")
            continue

        # Create projects for all components
        for component in sbom.get('components', []):
            bom_ref = component.get('bom-ref', '')
            if not bom_ref:
                continue

            # Strip version from purl to get stable key
            # e.g., pkg:maven/org.example/lib@1.0.0 -> pkg:maven/org.example/lib
            project_key, version = strip_purl_version(bom_ref)

            # Map bom-ref (with version) to project key (without version)
            bomref_to_key[bom_ref] = project_key

            # Skip if we've already processed this package (different version)
            if project_key in projects_cache:
                continue

            # Use version from component if not in bom-ref
            if not version:
                version = component.get('version', '')

            # Determine if internal based on prefix (use version-less key)
            is_internal = False
            if internal_prefix:
                internal_prefix_base, _ = strip_purl_version(internal_prefix)
                if project_key.startswith(internal_prefix_base):
                    is_internal = True

            # Extract group, basename, and full name from purl (use version-less key)
            group_key, basename, full_name = extract_group_from_purl(project_key, internal_prefix)

            # Create/get group hierarchy for internal packages
            group = None
            if is_internal and group_key:
                group = get_or_create_group_hierarchy(group_key, groups_cache)

            project, created = Project.objects.update_or_create(
                key=project_key,
                defaults={
                    'name': full_name,
                    'basename': basename,
                    'description': f'v{version}' if version else '',
                    'qualifier': 'TRK' if is_internal else 'PKG',
                    'internal': is_internal,
                    'group': group,
                    'synced_at': timezone.now(),
                }
            )
            projects_cache[project_key] = project
            if created:
                result['projects'] += 1

    # Second pass: create dependencies from the dependencies array
    for sbom_file in cache_path.glob('*.json'):
        try:
            with open(sbom_file) as f:
                sbom = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            continue

        # Process dependencies array (each entry has ref and dependsOn)
        for dep_entry in sbom.get('dependencies', []):
            source_ref = dep_entry.get('ref', '')
            depends_on = dep_entry.get('dependsOn', [])

            # Map bom-ref (with version) to version-less key
            source_key = bomref_to_key.get(source_ref) or strip_purl_version(source_ref)[0]

            source = projects_cache.get(source_key)
            if not source:
                # Source might not be in cache if it's not in components
                source = Project.objects.filter(key=source_key).first()
                if source:
                    projects_cache[source_key] = source

            if not source:
                continue

            for target_ref in depends_on:
                # Map bom-ref (with version) to version-less key
                target_key = bomref_to_key.get(target_ref) or strip_purl_version(target_ref)[0]

                target = projects_cache.get(target_key)
                if not target:
                    target = Project.objects.filter(key=target_key).first()
                    if target:
                        projects_cache[target_key] = target

                if not target:
                    continue

                Dependency.objects.update_or_create(
                    source=source,
                    target=target,
                    defaults={
                        'scope': 'compile',
                        'weight': 1,
                    }
                )
                result['dependencies'] += 1

        if on_progress:
            on_progress(result['projects'], result['dependencies'])

    logger.info(f"Offline import complete: {result['projects']} projects, {result['dependencies']} dependencies")
    return result
