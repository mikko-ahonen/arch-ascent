"""Project status classification logic."""
from django.db.models import Count, Q, Exists, OuterRef

from dependencies.models import Project


# Status constants - must match Project.STATUS_CHOICES
STATUS_ACTIVE = 'active'
STATUS_STALE = 'stale'
STATUS_DORMANT = 'dormant'
STATUS_NOT_ANALYZED = 'not_analyzed'
STATUS_ORPHAN = 'orphan'

STATUS_CHOICES = Project.STATUS_CHOICES

STATUS_COLORS = {
    STATUS_ACTIVE: '#28a745',        # Green
    STATUS_STALE: '#ffc107',         # Yellow
    STATUS_DORMANT: '#fd7e14',       # Orange
    STATUS_NOT_ANALYZED: '#dc3545',  # Red
    STATUS_ORPHAN: '#6c757d',        # Gray
}


def classify_project(project):
    """Return status for a project.

    Args:
        project: Project model instance

    Returns:
        str: The project's status field value
    """
    return project.status


def is_orphan(project):
    """Check if project has no dependencies and no dependents.

    Args:
        project: Project model instance

    Returns:
        bool: True if project has no connections
    """
    return (
        not project.dependencies.exists() and
        not project.dependents.exists()
    )


def get_status_counts(queryset=None):
    """Get count of projects in each status category.

    Args:
        queryset: Optional Project queryset to filter. If None, uses all projects.

    Returns:
        dict: Status counts like {'active': 150, 'stale': 200, ...}
    """
    if queryset is None:
        queryset = Project.objects.all()

    # Count by status field
    counts = {
        STATUS_ACTIVE: queryset.filter(status=STATUS_ACTIVE).count(),
        STATUS_STALE: queryset.filter(status=STATUS_STALE).count(),
        STATUS_DORMANT: queryset.filter(status=STATUS_DORMANT).count(),
        STATUS_NOT_ANALYZED: queryset.filter(status=STATUS_NOT_ANALYZED).count(),
        STATUS_ORPHAN: queryset.filter(status=STATUS_ORPHAN).count(),
    }

    return counts


def filter_by_status(queryset, statuses):
    """Filter queryset to only include projects with given statuses.

    Args:
        queryset: Project queryset
        statuses: List of status strings to include

    Returns:
        Filtered QuerySet
    """
    if not statuses:
        return queryset.none()

    return queryset.filter(status__in=statuses)


# =============================================================================
# Cluster Detection (Connected Components)
# =============================================================================

def build_adjacency_undirected():
    """Build undirected adjacency list from dependencies.

    Returns:
        tuple: (adjacency dict, id_to_key dict, key_to_id dict)
    """
    from dependencies.models import Project, Dependency

    # Map project keys to IDs and vice versa
    projects = {p.key: p.id for p in Project.objects.all()}
    id_to_key = {v: k for k, v in projects.items()}

    # Build undirected adjacency (both directions)
    adjacency = {key: set() for key in projects}

    for dep in Dependency.objects.select_related('source', 'target').all():
        source_key = dep.source.key
        target_key = dep.target.key
        if source_key in adjacency and target_key in adjacency:
            adjacency[source_key].add(target_key)
            adjacency[target_key].add(source_key)  # Undirected

    return adjacency, id_to_key, projects


def find_connected_components():
    """Find all connected components (clusters) in the dependency graph.

    Uses BFS to find disconnected subgraphs.

    Returns:
        list[set]: List of sets, each containing project keys in a cluster.
                   Sorted by size (largest first).
    """
    adjacency, _, _ = build_adjacency_undirected()

    visited = set()
    components = []

    for start_key in adjacency:
        if start_key in visited:
            continue

        # BFS to find all connected nodes
        component = set()
        queue = [start_key]

        while queue:
            key = queue.pop(0)
            if key in visited:
                continue

            visited.add(key)
            component.add(key)

            for neighbor in adjacency.get(key, []):
                if neighbor not in visited:
                    queue.append(neighbor)

        if component:
            components.append(component)

    # Sort by size (largest first)
    components.sort(key=len, reverse=True)
    return components


def get_main_cluster_ids():
    """Get project IDs in the main (largest) cluster.

    Returns:
        set: Set of project IDs in the main cluster
    """
    from dependencies.models import Project

    components = find_connected_components()
    if not components:
        return set()

    main_cluster_keys = components[0]

    # Convert keys to IDs
    return set(
        Project.objects.filter(key__in=main_cluster_keys).values_list('id', flat=True)
    )


def get_cluster_info():
    """Get information about all clusters.

    Returns:
        list[dict]: List of cluster info dicts with 'size', 'keys', 'is_main'
    """
    components = find_connected_components()

    return [
        {
            'size': len(cluster),
            'keys': cluster,
            'is_main': i == 0,
            'index': i,
        }
        for i, cluster in enumerate(components)
    ]


def get_disconnected_project_ids():
    """Get project IDs that are NOT in the main cluster.

    Returns:
        set: Set of project IDs in smaller/disconnected clusters
    """
    from dependencies.models import Project

    components = find_connected_components()
    if len(components) <= 1:
        return set()

    # All clusters except the main one
    disconnected_keys = set()
    for cluster in components[1:]:
        disconnected_keys.update(cluster)

    return set(
        Project.objects.filter(key__in=disconnected_keys).values_list('id', flat=True)
    )


# =============================================================================
# Usage Detection (Unused Projects)
# =============================================================================

def get_unused_project_ids():
    """Get project IDs that have no dependents (leaf nodes).

    These are projects that nothing depends on - potentially unused or
    top-level applications.

    Returns:
        set: Set of project IDs with no dependents
    """
    from dependencies.models import Project, Dependency

    has_dependents = Dependency.objects.filter(target=OuterRef('pk'))

    unused = Project.objects.annotate(
        has_dependents=Exists(has_dependents)
    ).filter(
        has_dependents=False
    ).values_list('id', flat=True)

    return set(unused)


def get_connectivity_counts(queryset=None):
    """Get counts for connectivity-based categories.

    Args:
        queryset: Optional Project queryset. If None, uses all projects.

    Returns:
        dict: Counts like {'unused': 50, 'disconnected': 20, 'main_cluster': 630}
    """
    from dependencies.models import Project

    if queryset is None:
        queryset = Project.objects.all()

    total = queryset.count()
    main_cluster_ids = get_main_cluster_ids()
    unused_ids = get_unused_project_ids()

    # Filter to only count within the queryset
    qs_ids = set(queryset.values_list('id', flat=True))

    return {
        'total': total,
        'main_cluster': len(main_cluster_ids & qs_ids),
        'disconnected': len(qs_ids - main_cluster_ids),
        'unused': len(unused_ids & qs_ids),
        'used': len(qs_ids - unused_ids),
    }
