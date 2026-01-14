"""
Django component for project filtering panel.
"""
from django_components import Component, register
from django.http import HttpRequest, JsonResponse
from django.urls import path
from django.views.decorators.csrf import csrf_exempt

from dependencies.models import Project, NodeGroup
from scope.classifier import (
    STATUS_CHOICES, STATUS_COLORS,
    get_status_counts, get_connectivity_counts,
)


@register("filter_panel")
class FilterPanel(Component):
    template_name = "filter_panel/filter_panel.html"

    def get_context_data(
        self,
        # Status filters
        include_active: bool = True,
        include_stale: bool = True,
        include_dormant: bool = False,
        include_not_analyzed: bool = False,
        include_orphan: bool = False,
        # Connectivity filters
        include_main_cluster: bool = True,
        include_unused: bool = True,
        include_disconnected: bool = False,
        # Internal/External filter
        include_external: bool = False,
        # Other filters
        selected_groups: list = None,
        name_pattern: str = '',
        # UI options
        target_id: str = 'graph-container',
    ):
        # Get status counts
        status_counts = get_status_counts()

        # Get connectivity counts
        connectivity_counts = get_connectivity_counts()

        # Get internal/external counts
        internal_count = Project.objects.filter(internal=True).count()
        external_count = Project.objects.filter(internal=False).count()

        # Get all tags with counts
        from taggit.models import Tag
        from django.db.models import Count
        tags = Tag.objects.annotate(count=Count('taggit_taggeditem_items')).order_by('name')

        # Get all groups with project counts, organized hierarchically
        import re
        from django.db.models import Count

        def natural_sort_key(group):
            """Sort key for natural ordering (Cluster 1, 2, 10 not 1, 10, 2)."""
            return [
                int(text) if text.isdigit() else text.lower()
                for text in re.split(r'(\d+)', group.name)
            ]

        groups_qs = NodeGroup.objects.annotate(project_count=Count('projects'))

        # Build hierarchical structure
        def build_group_tree(groups_qs):
            """Build a tree of groups with parent-child relationships."""
            # First pass: get all groups with their data
            groups_by_id = {}
            root_groups = []

            for group in groups_qs:
                group_data = {
                    'id': group.id,
                    'key': group.key,
                    'name': group.name,
                    'project_count': group.project_count,
                    'depth': group.depth,
                    'parent_id': group.parent_id,
                    'children': [],
                }
                groups_by_id[group.id] = group_data

            # Second pass: build tree structure
            for group_id, group_data in groups_by_id.items():
                parent_id = group_data['parent_id']
                if parent_id and parent_id in groups_by_id:
                    groups_by_id[parent_id]['children'].append(group_data)
                else:
                    root_groups.append(group_data)

            # Sort children at each level
            def sort_children(node):
                node['children'] = sorted(node['children'], key=lambda g: natural_sort_key(type('obj', (), {'name': g['name']})()))
                for child in node['children']:
                    sort_children(child)

            root_groups = sorted(root_groups, key=lambda g: natural_sort_key(type('obj', (), {'name': g['name']})()))
            for root in root_groups:
                sort_children(root)

            return root_groups

        # Flatten tree for template iteration with depth info
        def flatten_group_tree(roots, result=None):
            """Flatten tree into list with depth info for indented display."""
            if result is None:
                result = []
            for group in roots:
                result.append(group)
                if group['children']:
                    flatten_group_tree(group['children'], result)
            return result

        group_tree = build_group_tree(groups_qs)
        groups = flatten_group_tree(group_tree)

        # Calculate filtered count based on current selections
        current_filter = {
            'include_active': include_active,
            'include_stale': include_stale,
            'include_dormant': include_dormant,
            'include_not_analyzed': include_not_analyzed,
            'include_orphan': include_orphan,
            'include_main_cluster': include_main_cluster,
            'include_unused': include_unused,
            'include_disconnected': include_disconnected,
            'include_external': include_external,
            'selected_groups': selected_groups or [],
            'name_pattern': name_pattern,
        }

        filtered_count = self._get_filtered_count(current_filter)
        total_count = Project.objects.count()

        return {
            # Counts
            'status_counts': status_counts,
            'connectivity_counts': connectivity_counts,
            'internal_count': internal_count,
            'external_count': external_count,
            'filtered_count': filtered_count,
            'total_count': total_count,
            # Status metadata
            'status_choices': STATUS_CHOICES,
            'status_colors': STATUS_COLORS,
            # Filter options
            'groups': groups,
            'tags': tags,
            # Current filter state
            'current_filter': current_filter,
            # UI options
            'target_id': target_id,
        }

    def _get_filtered_count(self, filter_config):
        """Calculate how many projects match the current filter config."""
        from scope.classifier import filter_by_status, get_main_cluster_ids, get_unused_project_ids

        queryset = Project.objects.all()

        # Filter by internal/external
        if not filter_config.get('include_external', False):
            queryset = queryset.filter(internal=True)

        # Build status list
        statuses = []
        if filter_config['include_active']:
            statuses.append('active')
        if filter_config['include_stale']:
            statuses.append('stale')
        if filter_config['include_dormant']:
            statuses.append('dormant')
        if filter_config['include_not_analyzed']:
            statuses.append('not_analyzed')
        if filter_config['include_orphan']:
            statuses.append('orphan')

        if statuses:
            queryset = filter_by_status(queryset, statuses)
        else:
            queryset = queryset.none()

        # Filter by groups - if none selected, show nothing
        # Include projects with no group when all groups are selected
        if filter_config['selected_groups']:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(group_id__in=filter_config['selected_groups']) | Q(group__isnull=True)
            )
        else:
            queryset = queryset.none()

        # Filter by tags - if tags selected, show projects with those tags or no tags
        selected_tags = filter_config.get('selected_tags', [])
        if selected_tags:
            from django.db.models import Q
            # Include projects with selected tags OR projects with no tags
            queryset = queryset.filter(
                Q(tags__name__in=selected_tags) | Q(tags__isnull=True)
            )

        # Filter by name pattern
        if filter_config['name_pattern']:
            import fnmatch
            pattern = filter_config['name_pattern'].strip()
            if '*' in pattern:
                regex_pattern = fnmatch.translate(pattern)
                queryset = queryset.filter(name__iregex=regex_pattern)
            else:
                queryset = queryset.filter(name__icontains=pattern)

        # Filter by connectivity (main cluster vs disconnected)
        main_cluster_ids = get_main_cluster_ids()
        include_main = filter_config.get('include_main_cluster', True)
        include_disconnected = filter_config.get('include_disconnected', False)

        if main_cluster_ids:
            if include_main and not include_disconnected:
                queryset = queryset.filter(id__in=main_cluster_ids)
            elif include_disconnected and not include_main:
                queryset = queryset.exclude(id__in=main_cluster_ids)
            # If both or neither, no filtering needed

        # Filter out unused if not included
        if not filter_config.get('include_unused', True):
            unused_ids = get_unused_project_ids()
            queryset = queryset.exclude(id__in=unused_ids)

        return queryset.distinct().count()

    @staticmethod
    def get_urls():
        return [
            path('filter/apply/', filter_apply, name='filter_apply'),
            path('filter/counts/', filter_counts, name='filter_counts'),
        ]


@csrf_exempt
def filter_apply(request: HttpRequest) -> JsonResponse:
    """Apply filter and return matching project IDs."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    import json
    data = json.loads(request.body) if request.body else {}

    # Build filter config from request
    filter_config = {
        'include_active': data.get('include_active', True),
        'include_stale': data.get('include_stale', True),
        'include_dormant': data.get('include_dormant', False),
        'include_not_analyzed': data.get('include_not_analyzed', False),
        'include_orphan': data.get('include_orphan', False),
        'include_main_cluster': data.get('include_main_cluster', True),
        'include_unused': data.get('include_unused', True),
        'include_disconnected': data.get('include_disconnected', False),
        'include_external': data.get('include_external', False),
        'selected_groups': data.get('selected_groups', []),
        'selected_tags': data.get('selected_tags', []),
        'name_pattern': data.get('name_pattern', ''),
    }

    # Get filtered project IDs
    from scope.classifier import filter_by_status, get_main_cluster_ids, get_unused_project_ids

    queryset = Project.objects.all()

    # Filter by internal/external
    if not filter_config.get('include_external', False):
        queryset = queryset.filter(internal=True)

    # Build status list
    statuses = []
    if filter_config['include_active']:
        statuses.append('active')
    if filter_config['include_stale']:
        statuses.append('stale')
    if filter_config['include_dormant']:
        statuses.append('dormant')
    if filter_config['include_not_analyzed']:
        statuses.append('not_analyzed')
    if filter_config['include_orphan']:
        statuses.append('orphan')

    if statuses:
        queryset = filter_by_status(queryset, statuses)
    else:
        queryset = queryset.none()

    # Filter by groups - if none selected, show nothing
    # Include projects with no group when all groups are selected
    if filter_config['selected_groups']:
        from django.db.models import Q
        queryset = queryset.filter(
            Q(group_id__in=filter_config['selected_groups']) | Q(group__isnull=True)
        )
    else:
        queryset = queryset.none()

    # Filter by tags - if tags selected, show projects with those tags or no tags
    selected_tags = filter_config.get('selected_tags', [])
    if selected_tags:
        from django.db.models import Q
        queryset = queryset.filter(
            Q(tags__name__in=selected_tags) | Q(tags__isnull=True)
        )

    # Filter by name pattern
    if filter_config['name_pattern']:
        import fnmatch
        pattern = filter_config['name_pattern'].strip()
        if '*' in pattern:
            regex_pattern = fnmatch.translate(pattern)
            queryset = queryset.filter(name__iregex=regex_pattern)
        else:
            queryset = queryset.filter(name__icontains=pattern)

    # Filter by connectivity (main cluster vs disconnected)
    main_cluster_ids = get_main_cluster_ids()
    include_main = filter_config.get('include_main_cluster', True)
    include_disconnected = filter_config.get('include_disconnected', False)

    if main_cluster_ids:
        if include_main and not include_disconnected:
            queryset = queryset.filter(id__in=main_cluster_ids)
        elif include_disconnected and not include_main:
            queryset = queryset.exclude(id__in=main_cluster_ids)
        # If both or neither, no filtering needed

    # Filter out unused if not included
    if not filter_config.get('include_unused', True):
        unused_ids = get_unused_project_ids()
        queryset = queryset.exclude(id__in=unused_ids)

    project_ids = list(queryset.distinct().values_list('id', flat=True))
    project_keys = list(queryset.distinct().values_list('key', flat=True))

    return JsonResponse({
        'count': len(project_ids),
        'project_ids': project_ids,
        'project_keys': project_keys,
    })


def filter_counts(request: HttpRequest) -> JsonResponse:
    """Get current filter counts."""
    status_counts = get_status_counts()
    connectivity_counts = get_connectivity_counts()

    return JsonResponse({
        'status': status_counts,
        'connectivity': connectivity_counts,
        'total': Project.objects.count(),
    })
