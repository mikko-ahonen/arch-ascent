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
    batch_size: int = 10,
    batch_delay: float = 10.0,
    on_progress: callable = None,
) -> dict:
    """Export SBOMs for all Checkmarx projects in batches.

    Args:
        service: CheckmarxService instance
        batch_size: Number of SBOMs to export per batch
        batch_delay: Seconds to wait between batches (default: 1.0)
        on_progress: Optional callback(exported, skipped, failed, total) for progress updates

    Returns:
        dict with 'exported', 'skipped', 'failed', 'errors' counts
    """
    import time

    result = {'exported': 0, 'skipped': 0, 'failed': 0, 'errors': []}

    # Build list of (project_id, scan_id) pairs to process
    to_export = []
    for cx_project in service.get_projects():
        scans = service.get_scans(cx_project.id)
        if scans:
            scan_id = scans[0].get('id') or scans[0].get('scanId')
            if scan_id:
                to_export.append((cx_project.id, cx_project.name, scan_id))

    total = len(to_export)
    processed = 0

    for i in range(0, len(to_export), batch_size):
        batch = to_export[i:i + batch_size]

        for j, (project_id, project_name, scan_id) in enumerate(batch):
            # Check if already cached
            if service.is_sbom_cached(scan_id):
                result['skipped'] += 1
                logger.info(f"SBOM already cached for {project_name} (scan: {scan_id})")
            else:
                try:
                    service.export_sbom(scan_id, use_cache=False)
                    result['exported'] += 1
                    logger.info(f"Exported SBOM for {project_name} (scan: {scan_id})")

                    # Delay after each export (not after the very last one)
                    is_last_item = (i + j + 1) >= len(to_export)
                    if batch_delay > 0 and not is_last_item:
                        time.sleep(batch_delay)

                except Exception as e:
                    result['failed'] += 1
                    result['errors'].append({'project': project_name, 'scan_id': scan_id, 'error': str(e)})
                    logger.error(f"Failed to export SBOM for {project_name}: {e}")

            processed += 1
            if on_progress:
                on_progress(result['exported'], result['skipped'], result['failed'], total)

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
