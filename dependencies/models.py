from django.db import models
from taggit.managers import TaggableManager


class NodeGroup(models.Model):
    """Group of nodes in the dependency graph, supporting hierarchy."""
    key = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255)  # Display name (e.g., "Bar" for key "foo.bar")
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children'
    )
    position_x = models.FloatField(null=True, blank=True)
    position_y = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ['key']

    def __str__(self):
        return self.name

    @property
    def full_path(self):
        """Return full path from root to this group."""
        if self.parent:
            return f"{self.parent.full_path}.{self.name}"
        return self.name

    @property
    def depth(self):
        """Return depth in hierarchy (0 for root groups)."""
        if self.parent:
            return self.parent.depth + 1
        return 0

    def get_ancestors(self):
        """Return list of ancestors from root to parent."""
        if self.parent:
            return self.parent.get_ancestors() + [self.parent]
        return []

    def get_descendants(self):
        """Return all descendant groups."""
        descendants = list(self.children.all())
        for child in self.children.all():
            descendants.extend(child.get_descendants())
        return descendants


class Project(models.Model):
    """SonarQube project synchronized locally."""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('stale', 'Stale'),
        ('dormant', 'Dormant'),
        ('not_analyzed', 'Not Analyzed'),
        ('orphan', 'Orphan'),
    ]

    key = models.CharField(max_length=255, unique=True, db_index=True)
    name = models.CharField(max_length=255)  # Full name including group (e.g., fi.company.foo.Bar)
    basename = models.CharField(max_length=255, blank=True, default='')  # Short name (e.g., Bar)
    description = models.TextField(blank=True, default='')
    qualifier = models.CharField(max_length=10, default='TRK')
    visibility = models.CharField(max_length=20, default='public')
    last_analysis = models.DateTimeField(null=True, blank=True)
    synced_at = models.DateTimeField(auto_now=True)
    position_x = models.FloatField(null=True, blank=True)
    position_y = models.FloatField(null=True, blank=True)
    group = models.ForeignKey(
        NodeGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='projects'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='not_analyzed',
    )
    internal = models.BooleanField(
        default=True,
        help_text="True for internal projects, False for external packages"
    )
    tags = TaggableManager(blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Dependency(models.Model):
    """Dependency relationship between projects."""
    source = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='dependencies'
    )
    target = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='dependents'
    )
    scope = models.CharField(max_length=50, default='compile')
    weight = models.IntegerField(default=1)

    class Meta:
        unique_together = ['source', 'target', 'scope']
        ordering = ['source__name', 'target__name']

    def __str__(self):
        return f"{self.source.key} -> {self.target.key}"


class AnalysisRun(models.Model):
    """Tracks each refactoring analysis pipeline execution."""
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    total_projects = models.IntegerField(default=0)
    total_sccs = models.IntegerField(default=0)
    total_clusters = models.IntegerField(default=0)
    proposals_generated = models.IntegerField(default=0)
    status = models.CharField(max_length=20, default='running', choices=[
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ])
    error_message = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"Analysis {self.id} ({self.status})"


class RefactoringProposal(models.Model):
    """LLM-generated refactoring suggestion."""
    PROPOSAL_TYPES = [
        ('cycle_break', 'Cycle Breaking'),
        ('service_extraction', 'Service Extraction'),
        ('api_stabilization', 'API Stabilization'),
        ('boundary_redefinition', 'Boundary Redefinition'),
    ]
    IMPACT_CHOICES = [
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
    ]
    RISK_CHOICES = [
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
    ]
    STATUS_CHOICES = [
        ('proposed', 'Proposed'),
        ('approved', 'Approved'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
    ]

    proposal_id = models.CharField(max_length=20, unique=True)  # e.g., ARC-042
    analysis_run = models.ForeignKey(
        AnalysisRun,
        on_delete=models.CASCADE,
        related_name='proposals',
        null=True,
        blank=True
    )
    proposal_type = models.CharField(max_length=50, choices=PROPOSAL_TYPES)
    scope = models.JSONField(default=list)  # List of affected service keys
    impact = models.CharField(max_length=20, choices=IMPACT_CHOICES, default='medium')
    risk = models.CharField(max_length=20, choices=RISK_CHOICES, default='medium')
    summary = models.TextField()
    root_cause = models.TextField(blank=True, default='')
    steps = models.JSONField(default=list)  # List of refactoring steps
    expected_improvement = models.TextField(blank=True, default='')

    # Validation metrics (before)
    scc_size_before = models.IntegerField(null=True, blank=True)
    fan_in_before = models.FloatField(null=True, blank=True)
    fan_out_before = models.FloatField(null=True, blank=True)

    # Status tracking
    status = models.CharField(max_length=20, default='proposed', choices=STATUS_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.proposal_id}: {self.summary[:50]}"

    @property
    def impact_badge_class(self):
        return {'high': 'danger', 'medium': 'warning', 'low': 'info'}.get(self.impact, 'secondary')

    @property
    def risk_badge_class(self):
        return {'high': 'danger', 'medium': 'warning', 'low': 'success'}.get(self.risk, 'secondary')

    @property
    def status_badge_class(self):
        return {
            'proposed': 'primary',
            'approved': 'info',
            'in_progress': 'warning',
            'completed': 'success',
            'rejected': 'secondary',
        }.get(self.status, 'secondary')


class LayerDefinition(models.Model):
    """Architectural layer definition for enforcing dependency rules."""
    name = models.CharField(max_length=100, unique=True)
    level = models.IntegerField(
        help_text="Lower numbers = lower layers (e.g., 0=infrastructure, 1=domain, 2=application)"
    )
    description = models.TextField(blank=True, default='')
    pattern = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text="Regex pattern to auto-assign projects (e.g., '^infra:.*')"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['level', 'name']

    def __str__(self):
        return f"{self.name} (level {self.level})"


class LayerAssignment(models.Model):
    """Assigns a project to an architectural layer."""
    project = models.OneToOneField(
        Project,
        on_delete=models.CASCADE,
        related_name='layer_assignment'
    )
    layer = models.ForeignKey(
        LayerDefinition,
        on_delete=models.CASCADE,
        related_name='assignments'
    )
    auto_assigned = models.BooleanField(
        default=False,
        help_text="True if assigned automatically via pattern matching"
    )
    assigned_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['layer__level', 'project__name']

    def __str__(self):
        return f"{self.project.key} -> {self.layer.name}"


class LayerViolation(models.Model):
    """Records detected layer violations."""
    SEVERITY_CHOICES = [
        ('critical', 'Critical'),   # Lower layer depends on higher layer
        ('warning', 'Warning'),     # Same layer circular dependency
        ('info', 'Info'),           # Skip-layer dependency
    ]

    analysis_run = models.ForeignKey(
        AnalysisRun,
        on_delete=models.CASCADE,
        related_name='layer_violations'
    )
    source_project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='outgoing_violations'
    )
    target_project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='incoming_violations'
    )
    source_layer = models.ForeignKey(
        LayerDefinition,
        on_delete=models.CASCADE,
        related_name='+'
    )
    target_layer = models.ForeignKey(
        LayerDefinition,
        on_delete=models.CASCADE,
        related_name='+'
    )
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    detected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-detected_at']

    def __str__(self):
        return f"{self.source_project.key} -> {self.target_project.key} ({self.severity})"

    @property
    def severity_badge_class(self):
        return {
            'critical': 'danger',
            'warning': 'warning',
            'info': 'info',
        }.get(self.severity, 'secondary')


class NodeMetrics(models.Model):
    """Cached node-level metrics for a project."""
    project = models.OneToOneField(
        Project,
        on_delete=models.CASCADE,
        related_name='metrics'
    )
    analysis_run = models.ForeignKey(
        AnalysisRun,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='node_metrics'
    )

    # Basic coupling metrics
    fan_in = models.IntegerField(default=0, help_text="Number of incoming dependencies")
    fan_out = models.IntegerField(default=0, help_text="Number of outgoing dependencies")
    coupling_score = models.FloatField(default=0.0)

    # Extended metrics (Robert Martin)
    afferent_coupling = models.IntegerField(default=0, help_text="Ca - incoming dependencies")
    efferent_coupling = models.IntegerField(default=0, help_text="Ce - outgoing dependencies")
    instability = models.FloatField(
        default=0.0,
        help_text="I = Ce / (Ca + Ce), 0=stable, 1=unstable"
    )

    # Centrality metrics
    degree_centrality = models.FloatField(default=0.0)
    betweenness_centrality = models.FloatField(default=0.0)

    # Topological position
    topological_order = models.IntegerField(
        null=True,
        blank=True,
        help_text="Position in topological ordering (if DAG)"
    )
    layer_depth = models.IntegerField(
        null=True,
        blank=True,
        help_text="Longest path from any root node"
    )

    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Node metrics'
        ordering = ['-instability', '-coupling_score']

    def __str__(self):
        return f"Metrics for {self.project.key}"


class Vision(models.Model):
    """Workspace for architectural exploration."""
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
    snapshot_data = models.JSONField(null=True, blank=True, help_text="Frozen state for sharing")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.name


class Reference(models.Model):
    """Named set with tag-based or explicit definitions."""
    DEFINITION_TYPES = [
        ('informal', 'Informal'),
        ('tag_expression', 'Tag Expression'),
        ('explicit_list', 'Explicit List'),
        ('layer', 'Layer'),  # Reference to a layer (for coverage/ownership statements)
    ]
    name = models.CharField(max_length=255)
    vision = models.ForeignKey(
        Vision,
        on_delete=models.CASCADE,
        related_name='references'
    )
    description = models.TextField(blank=True, default='')
    color = models.CharField(max_length=20, blank=True, default='')
    definition_type = models.CharField(max_length=20, choices=DEFINITION_TYPES, default='informal')
    tag_expression = models.JSONField(null=True, blank=True, help_text='e.g., {"and": ["payment", "api"]}')
    explicit_members = models.JSONField(default=list, help_text="List of project keys")
    layer_id = models.IntegerField(null=True, blank=True, help_text="ID of referenced layer (for layer definition type)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['name', 'vision']
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.vision.name})"


class Statement(models.Model):
    """Architectural intent statement."""
    STATEMENT_TYPES = [
        ('existence', 'Existence'),       # "There must be X"
        ('containment', 'Containment'),   # "X must contain Y"
        ('exclusion', 'Exclusion'),       # "X must not depend on Y"
        ('cardinality', 'Cardinality'),   # "There must be exactly N of X"
        ('coverage', 'Coverage'),         # "All X must have an owner on Y" (belong to a group on layer Y)
        ('correspondence', 'Correspondence'),  # "Layer X corresponds with layer Y" (1:1 group alignment)
        ('refinement', 'Refinement'),     # "Layer X refines layer Y" (many:1 - finer partitioning)
    ]
    STATUS_CHOICES = [
        ('informal', 'Informal'),
        ('semi_formal', 'Semi-Formal'),
        ('formal', 'Formal'),
    ]
    vision = models.ForeignKey(
        Vision,
        on_delete=models.CASCADE,
        related_name='statements'
    )
    description = models.TextField(blank=True, default='', help_text="Optional description or rationale")
    statement_type = models.CharField(max_length=20, choices=STATEMENT_TYPES, null=True, blank=True)
    natural_language = models.TextField(help_text="Human-readable statement with $$$ref$$$ tokens")
    formal_expression = models.JSONField(null=True, blank=True, help_text="Machine-evaluable expression")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='informal')
    is_satisfied = models.BooleanField(null=True, help_text="null = not evaluated")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.natural_language[:50]

    def save(self, *args, **kwargs):
        """Auto-infer statement_type, status, and formal_expression on save."""
        from dependencies.services.statement_parser import analyze_statement
        analysis = analyze_statement(self.natural_language)
        self.statement_type = analysis['statement_type']
        self.status = analysis['status']
        self.formal_expression = analysis['formal_expression']
        super().save(*args, **kwargs)
