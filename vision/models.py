"""
Vision Creation System models for Arch Ascent.

Provides architectural exploration and vision creation capabilities.
"""
from django.db import models


class Vision(models.Model):
    """Workspace for architectural exploration and vision creation."""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('shared', 'Shared'),
        ('archived', 'Archived'),
    ]

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='children',
        help_text="Parent vision for branching"
    )
    snapshot_data = models.JSONField(
        null=True,
        blank=True,
        help_text="Frozen state for sharing"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.name} ({self.status})"


class VisionVersion(models.Model):
    """Alternative variation/version of a vision's layout.

    Statements and References are shared across all versions of a vision.
    Each version stores its own layout data (groups, positions).
    """
    vision = models.ForeignKey(
        Vision,
        on_delete=models.CASCADE,
        related_name='versions'
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default='')
    layout_data = models.JSONField(
        default=dict,
        help_text="Snapshot of layers, groups, and positions for this version"
    )
    is_active = models.BooleanField(
        default=False,
        help_text="Currently active version (for display purposes)"
    )
    order = models.IntegerField(default=0, help_text="Tab order")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'created_at']
        unique_together = ['vision', 'name']

    def __str__(self):
        return f"{self.vision.name} - {self.name}"

    def snapshot_current_layout(self):
        """Capture the current vision layout into this version."""
        layers_data = []
        for layer in self.vision.layers.all():
            layer_data = {
                'id': layer.id,
                'key': layer.key,
                'name': layer.name,
                'color': layer.color,
                'groups': [],
            }
            for group in layer.groups.all():
                group_data = {
                    'id': group.id,
                    'key': group.key,
                    'name': group.name,
                    'color': group.color,
                    'position_x': group.position_x,
                    'position_y': group.position_y,
                    'members': list(group.memberships.values_list('project__key', flat=True)),
                }
                layer_data['groups'].append(group_data)

            # Include node positions for this layer
            layer_data['node_positions'] = list(
                layer.node_positions.values('project__key', 'position_x', 'position_y')
            )
            layers_data.append(layer_data)

        self.layout_data = {'layers': layers_data}
        self.save()


class Layer(models.Model):
    """Visual layer within a Vision, containing Groups."""
    LAYER_TYPES = [
        ('freeform', 'Freeform'),
        ('bounded_context', 'Bounded Context'),
        ('team', 'Team'),
        ('application', 'Application'),
        ('imported', 'Imported'),
    ]

    key = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    layer_type = models.CharField(max_length=50, choices=LAYER_TYPES, default='freeform')
    vision = models.ForeignKey(
        Vision,
        on_delete=models.CASCADE,
        related_name='layers'
    )
    color = models.CharField(max_length=20, blank=True, default='')
    is_visible = models.BooleanField(default=True)
    order = models.IntegerField(default=0, help_text="Display order within vision")
    is_imported = models.BooleanField(default=False)
    source_identifier = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text="External source ID (e.g., GitLab group ID)"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'name']
        unique_together = ['vision', 'key']

    def __str__(self):
        return f"{self.name} ({self.vision.name})"


class Group(models.Model):
    """Group of projects within a Layer."""
    key = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    layer = models.ForeignKey(
        Layer,
        on_delete=models.CASCADE,
        related_name='groups'
    )
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='children',
        help_text="Parent group for hierarchical grouping"
    )
    color = models.CharField(max_length=20, blank=True, default='')
    position_x = models.FloatField(null=True, blank=True)
    position_y = models.FloatField(null=True, blank=True)
    width = models.FloatField(null=True, blank=True)
    height = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        unique_together = ['layer', 'key']

    def __str__(self):
        return f"{self.name} ({self.layer.name})"


class GroupMembership(models.Model):
    """Membership of a project in a Group (many-to-many, overlapping allowed)."""
    MEMBERSHIP_TYPES = [
        ('explicit', 'Explicit'),
        ('inferred', 'Inferred'),
        ('imported', 'Imported'),
    ]

    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name='memberships'
    )
    project = models.ForeignKey(
        'dependencies.Project',
        on_delete=models.CASCADE,
        related_name='vision_group_memberships'
    )
    membership_type = models.CharField(
        max_length=20,
        choices=MEMBERSHIP_TYPES,
        default='explicit'
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['group', 'project']
        ordering = ['project__name']

    def __str__(self):
        return f"{self.project.key} in {self.group.name}"


class LayerNodePosition(models.Model):
    """Position of a project node within a Layer (layer-specific positions)."""
    layer = models.ForeignKey(
        Layer,
        on_delete=models.CASCADE,
        related_name='node_positions'
    )
    project = models.ForeignKey(
        'dependencies.Project',
        on_delete=models.CASCADE,
        related_name='vision_layer_positions'
    )
    position_x = models.FloatField(default=0.0)
    position_y = models.FloatField(default=0.0)

    class Meta:
        unique_together = ['layer', 'project']

    def __str__(self):
        return f"{self.project.key} @ ({self.position_x}, {self.position_y}) in {self.layer.name}"


class Reference(models.Model):
    """Named set of elements defined by tags or explicit list."""
    DEFINITION_TYPES = [
        ('informal', 'Informal'),
        ('tag_expression', 'Tag Expression'),
        ('explicit_list', 'Explicit List'),
    ]

    name = models.CharField(max_length=255)
    vision = models.ForeignKey(
        Vision,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='references',
        help_text="Vision scope (null = global reference)"
    )
    description = models.TextField(blank=True, default='')
    definition_type = models.CharField(
        max_length=20,
        choices=DEFINITION_TYPES,
        default='informal'
    )
    tag_expression = models.JSONField(
        null=True,
        blank=True,
        help_text='Tag expression, e.g., {"and": ["payment", "api"]}'
    )
    explicit_members = models.JSONField(
        default=list,
        help_text="List of project keys for explicit_list type"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['name', 'vision']
        ordering = ['name']

    def __str__(self):
        scope = self.vision.name if self.vision else "global"
        return f"{self.name} ({scope})"


class Statement(models.Model):
    """Architectural intent statement that can be evaluated."""
    STATEMENT_TYPES = [
        ('existence', 'Existence'),
        ('containment', 'Containment'),
        ('exclusion', 'Exclusion'),
        ('cardinality', 'Cardinality'),
    ]
    FORMALIZATION_STATUS = [
        ('informal', 'Informal'),
        ('semi_formal', 'Semi-Formal'),
        ('formal', 'Formal'),
    ]

    vision = models.ForeignKey(
        Vision,
        on_delete=models.CASCADE,
        related_name='statements'
    )
    statement_type = models.CharField(max_length=20, choices=STATEMENT_TYPES)
    natural_language = models.TextField(
        help_text="Human-readable statement, e.g., 'All payment APIs must be in the Payment domain'"
    )
    formal_expression = models.JSONField(
        null=True,
        blank=True,
        help_text='Machine-evaluable expression, e.g., {"type": "containment", "subject": "PaymentAPIs", "container": "PaymentDomain"}'
    )
    status = models.CharField(
        max_length=20,
        choices=FORMALIZATION_STATUS,
        default='informal'
    )
    is_satisfied = models.BooleanField(
        null=True,
        help_text="Evaluation result (null = not evaluated)"
    )
    last_evaluated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        status = "✓" if self.is_satisfied else ("✗" if self.is_satisfied is False else "?")
        return f"[{status}] {self.natural_language[:50]}"
