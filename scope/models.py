"""Models for project filtering."""
from django.db import models
from taggit.managers import TaggableManager


class ProjectFilter(models.Model):
    """Saved filter preset for filtering projects."""

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default='')

    # Status filters (which statuses to include)
    include_active = models.BooleanField(default=True)
    include_stale = models.BooleanField(default=True)
    include_dormant = models.BooleanField(default=False)
    include_never_analyzed = models.BooleanField(default=False)
    include_orphan = models.BooleanField(default=False)

    # Connectivity filters
    include_main_cluster = models.BooleanField(
        default=True,
        help_text='Include projects in the main connected cluster'
    )
    include_disconnected = models.BooleanField(
        default=False,
        help_text='Include projects not in the main cluster'
    )
    include_unused = models.BooleanField(
        default=True,
        help_text='Include projects with no dependents (leaf nodes)'
    )

    # Group filter
    groups = models.ManyToManyField(
        'dependencies.NodeGroup',
        blank=True,
        help_text='Only include projects in these groups (empty = all groups)'
    )

    # Tag filter
    tags = TaggableManager(
        blank=True,
        help_text='Only include projects with these tags (empty = ignore tags)'
    )

    # Name pattern filter (supports wildcards)
    name_pattern = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text='Filter by name pattern (supports * wildcard)'
    )

    # Configurable thresholds
    active_days = models.IntegerField(
        default=30,
        help_text='Projects analyzed within this many days are "active"'
    )
    stale_days = models.IntegerField(
        default=90,
        help_text='Projects analyzed within this many days (but not active) are "stale"'
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_default = models.BooleanField(
        default=False,
        help_text='Use this filter by default'
    )

    class Meta:
        ordering = ['-is_default', '-updated_at']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Ensure only one default filter
        if self.is_default:
            ProjectFilter.objects.filter(is_default=True).update(is_default=False)
        super().save(*args, **kwargs)

    def get_included_statuses(self):
        """Return list of status strings that are included in this filter."""
        from .classifier import (
            STATUS_ACTIVE, STATUS_STALE, STATUS_DORMANT,
            STATUS_NEVER_ANALYZED, STATUS_ORPHAN
        )

        statuses = []
        if self.include_active:
            statuses.append(STATUS_ACTIVE)
        if self.include_stale:
            statuses.append(STATUS_STALE)
        if self.include_dormant:
            statuses.append(STATUS_DORMANT)
        if self.include_never_analyzed:
            statuses.append(STATUS_NEVER_ANALYZED)
        if self.include_orphan:
            statuses.append(STATUS_ORPHAN)
        return statuses

    def apply(self, queryset=None):
        """Apply this filter to a queryset.

        Args:
            queryset: Project queryset. If None, uses all projects.

        Returns:
            Filtered queryset
        """
        import fnmatch
        from dependencies.models import Project
        from .classifier import filter_by_status, get_main_cluster_ids, get_unused_project_ids

        if queryset is None:
            queryset = Project.objects.all()

        # Filter by status
        statuses = self.get_included_statuses()
        if statuses:
            queryset = filter_by_status(
                queryset,
                statuses,
                active_days=self.active_days,
                stale_days=self.stale_days
            )

        # Filter by groups
        if self.groups.exists():
            queryset = queryset.filter(group__in=self.groups.all())

        # Filter by tags
        filter_tags = list(self.tags.names())
        if filter_tags:
            queryset = queryset.filter(tags__name__in=filter_tags).distinct()

        # Filter by name pattern
        if self.name_pattern:
            pattern = self.name_pattern.strip()
            if '*' in pattern:
                # Convert wildcard to regex
                regex_pattern = fnmatch.translate(pattern)
                queryset = queryset.filter(name__iregex=regex_pattern)
            else:
                # Simple substring match
                queryset = queryset.filter(name__icontains=pattern)

        # Filter by connectivity (main cluster vs disconnected)
        main_cluster_ids = get_main_cluster_ids()
        if main_cluster_ids:
            if self.include_main_cluster and not self.include_disconnected:
                queryset = queryset.filter(id__in=main_cluster_ids)
            elif self.include_disconnected and not self.include_main_cluster:
                queryset = queryset.exclude(id__in=main_cluster_ids)
            # If both or neither, no filtering needed

        # Filter out unused projects if not included
        if not self.include_unused:
            unused_ids = get_unused_project_ids()
            queryset = queryset.exclude(id__in=unused_ids)

        return queryset

    @classmethod
    def get_default(cls):
        """Get the default filter, or None if not set."""
        return cls.objects.filter(is_default=True).first()
