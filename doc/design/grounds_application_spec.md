# Grounds Application Specification

This document specifies the `grounds` Django application for Arch Ascent. The grounds app captures architectural milestones, tracks evolution between stable states, and measures momentum factors.

---

## 1. Purpose

The grounds application implements the "Ground" and "Momentum" concepts from the [Architecture Vision, Ground, and Momentum Model](architecture_vision_ground_and_momentum_model.md).

**Core responsibilities:**
- Define and track stable architectural states (Grounds)
- Document transitions between grounds
- Capture evidence of what makes a ground stable
- Measure momentum factors that enable or hinder evolution
- Link grounds to visions and statements

---

## 2. Key Concepts

### 2.1 Ground
A **Ground** is a named, stable architectural state where:
- The system operates at least as reliably as before
- Teams understand how to work within the current structure
- Tooling, testing, and processes have caught up

### 2.2 Ground Zero
**Ground Zero** is automatically created as the initial state when a vision is first analyzed. It represents "where we are today."

### 2.3 Momentum
**Momentum** captures the system's ability to evolve. It is measured through:
- Quantitative metrics (coupling, test coverage, deployment frequency)
- Qualitative assessments (team confidence, organizational alignment)

### 2.4 Transition
A **Transition** documents the journey from one ground to another, including what changed, what was learned, and what blocked progress.

---

## 3. Data Models

### 3.1 Ground

```python
class Ground(models.Model):
    """A stable architectural milestone state."""

    class Status(models.TextChoices):
        PLANNED = 'planned', 'Planned'
        CURRENT = 'current', 'Current'
        ACHIEVED = 'achieved', 'Achieved'
        ABANDONED = 'abandoned', 'Abandoned'

    vision = models.ForeignKey(
        'vision.Vision',
        on_delete=models.CASCADE,
        related_name='grounds'
    )

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PLANNED
    )

    # Ordering within the vision's evolution path
    order = models.PositiveIntegerField(default=0)

    # When this ground was achieved (if status is ACHIEVED or CURRENT)
    achieved_at = models.DateTimeField(null=True, blank=True)

    # JSON snapshot of architecture state at this ground
    # Includes: layer assignments, group memberships, metrics
    state_snapshot = models.JSONField(default=dict, blank=True)

    # What makes this ground stable (human description)
    stability_rationale = models.TextField(
        blank=True,
        help_text="Why is this a stable state? What can the org do from here?"
    )

    # Prerequisites - other grounds that must be achieved first
    prerequisites = models.ManyToManyField(
        'self',
        symmetrical=False,
        related_name='dependents',
        blank=True
    )

    is_ground_zero = models.BooleanField(
        default=False,
        help_text="Marks this as the initial state (auto-created)"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['vision', 'order']
        unique_together = [['vision', 'name']]
```

### 3.2 MomentumSnapshot

```python
class MomentumSnapshot(models.Model):
    """Captures momentum factors at a point in time."""

    ground = models.ForeignKey(
        Ground,
        on_delete=models.CASCADE,
        related_name='momentum_snapshots'
    )

    captured_at = models.DateTimeField(auto_now_add=True)

    # Quantitative metrics (from dependencies app)
    metrics = models.JSONField(
        default=dict,
        help_text="Automated metrics: avg_coupling, cycle_count, etc."
    )

    # Qualitative assessments (human input)
    assessments = models.JSONField(
        default=dict,
        help_text="Manual assessments: team_confidence, org_alignment, etc."
    )

    # Overall momentum score (computed or manual)
    momentum_score = models.FloatField(
        null=True,
        blank=True,
        help_text="0.0 to 1.0 scale, higher = more momentum"
    )

    notes = models.TextField(blank=True)
```

### 3.3 GroundEvidence

```python
class GroundEvidence(models.Model):
    """Links statements to their satisfaction status at a ground."""

    class EvidenceType(models.TextChoices):
        STATEMENT_SATISFIED = 'satisfied', 'Statement Satisfied'
        STATEMENT_VIOLATED = 'violated', 'Statement Violated'
        METRIC_THRESHOLD = 'metric', 'Metric Threshold Met'
        MANUAL_VERIFICATION = 'manual', 'Manual Verification'

    ground = models.ForeignKey(
        Ground,
        on_delete=models.CASCADE,
        related_name='evidence'
    )

    evidence_type = models.CharField(
        max_length=20,
        choices=EvidenceType.choices
    )

    # For statement-based evidence
    statement = models.ForeignKey(
        'vision.Statement',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='ground_evidence'
    )

    # Result of evaluation
    is_satisfied = models.BooleanField(null=True)

    # For metric-based evidence
    metric_name = models.CharField(max_length=100, blank=True)
    metric_value = models.FloatField(null=True, blank=True)
    metric_threshold = models.FloatField(null=True, blank=True)

    # Human verification
    verified_by = models.CharField(max_length=200, blank=True)
    verification_notes = models.TextField(blank=True)

    evaluated_at = models.DateTimeField(auto_now_add=True)
```

### 3.4 Transition

```python
class Transition(models.Model):
    """Documents the journey between two grounds."""

    class Status(models.TextChoices):
        PLANNED = 'planned', 'Planned'
        IN_PROGRESS = 'in_progress', 'In Progress'
        COMPLETED = 'completed', 'Completed'
        BLOCKED = 'blocked', 'Blocked'
        ABANDONED = 'abandoned', 'Abandoned'

    from_ground = models.ForeignKey(
        Ground,
        on_delete=models.CASCADE,
        related_name='outgoing_transitions'
    )

    to_ground = models.ForeignKey(
        Ground,
        on_delete=models.CASCADE,
        related_name='incoming_transitions'
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PLANNED
    )

    # What needs to change
    change_description = models.TextField(
        blank=True,
        help_text="What architectural changes are needed?"
    )

    # Related refactoring proposals from dependencies app
    refactoring_proposals = models.ManyToManyField(
        'dependencies.RefactoringProposal',
        blank=True,
        related_name='transitions'
    )

    # What's blocking progress
    blockers = models.TextField(
        blank=True,
        help_text="What is preventing this transition?"
    )

    # Retrospective
    lessons_learned = models.TextField(
        blank=True,
        help_text="What did we learn from this transition?"
    )

    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [['from_ground', 'to_ground']]
```

---

## 4. Services

### 4.1 Ground Zero Generator

```python
# grounds/services/ground_zero.py

def create_ground_zero(vision: Vision) -> Ground:
    """
    Create the initial Ground Zero for a vision.
    Captures current state as the baseline.
    """
    # Create ground
    # Snapshot current state (layer assignments, groups, metrics)
    # Create initial momentum snapshot
    # Evaluate all formal statements as evidence
```

### 4.2 Momentum Calculator

```python
# grounds/services/momentum.py

def calculate_momentum_metrics(vision: Vision) -> dict:
    """
    Calculate quantitative momentum metrics from current state.

    Returns dict with:
    - avg_coupling: Average coupling across all projects
    - cycle_count: Number of dependency cycles
    - max_cycle_size: Size of largest cycle
    - layer_violation_count: Number of layer violations
    - formal_statement_ratio: % of statements that are formal
    - statement_satisfaction_ratio: % of formal statements satisfied
    """

def capture_momentum_snapshot(ground: Ground, assessments: dict = None) -> MomentumSnapshot:
    """
    Capture current momentum for a ground.
    Combines automated metrics with manual assessments.
    """
```

### 4.3 Evidence Collector

```python
# grounds/services/evidence.py

def collect_statement_evidence(ground: Ground) -> list[GroundEvidence]:
    """
    Evaluate all formal statements in the vision and record evidence.
    """

def verify_ground_stability(ground: Ground) -> dict:
    """
    Check if a ground meets stability criteria.

    Returns:
    - is_stable: bool
    - satisfied_count: int
    - violated_count: int
    - unverified_count: int
    - blocking_violations: list of critical violations
    """
```

### 4.4 Transition Planner

```python
# grounds/services/transitions.py

def suggest_next_ground(current_ground: Ground, vision: Vision) -> list[dict]:
    """
    Suggest possible next grounds based on:
    - Unsatisfied statements
    - Layer violations
    - Refactoring proposals

    Returns list of suggestions with effort/impact estimates.
    """

def calculate_transition_delta(from_ground: Ground, to_ground: Ground) -> dict:
    """
    Calculate what changed between two grounds.

    Returns:
    - statements_changed: list of statements that changed satisfaction
    - metrics_delta: dict of metric changes
    - structural_changes: summary of layer/group changes
    """
```

---

## 5. Views & Endpoints

### 5.1 Ground Management

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/grounds/` | Grounds home - list all visions with their grounds |
| GET | `/grounds/vision/<id>/` | Ground timeline for a specific vision |
| GET | `/grounds/htmx/ground-form/` | Ground create/edit form (modal) |
| POST | `/grounds/htmx/ground-form/` | Save ground |
| DELETE | `/grounds/htmx/ground-delete/` | Delete ground |
| POST | `/grounds/htmx/ground-zero/` | Create Ground Zero for vision |
| POST | `/grounds/htmx/mark-current/` | Mark a ground as current |

### 5.2 Momentum & Evidence

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/grounds/htmx/momentum/<ground_id>/` | Momentum panel for a ground |
| POST | `/grounds/htmx/momentum-snapshot/` | Capture new momentum snapshot |
| GET | `/grounds/htmx/evidence/<ground_id>/` | Evidence list for a ground |
| POST | `/grounds/htmx/collect-evidence/` | Run evidence collection |
| POST | `/grounds/htmx/verify-evidence/` | Manual evidence verification |

### 5.3 Transitions

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/grounds/htmx/transition-form/` | Transition create/edit form |
| POST | `/grounds/htmx/transition-form/` | Save transition |
| DELETE | `/grounds/htmx/transition-delete/` | Delete transition |
| POST | `/grounds/htmx/start-transition/` | Mark transition as in progress |
| POST | `/grounds/htmx/complete-transition/` | Mark transition as completed |

---

## 6. UI Components

### 6.1 Ground Timeline

A vertical timeline showing the evolution path:
- Ground Zero at the bottom
- Current ground highlighted
- Planned grounds shown with dashed borders
- Transitions shown as arrows between grounds
- Click ground to see details

### 6.2 Ground Detail Panel

Shows for a selected ground:
- Name, description, status
- Stability rationale
- Prerequisites (with satisfaction status)
- Evidence summary (satisfied/violated/unverified counts)
- Momentum snapshot comparison (vs previous ground)
- Actions: Mark as Current, Capture Momentum, Collect Evidence

### 6.3 Momentum Dashboard

Visual display of momentum factors:
- Spider/radar chart of quantitative metrics
- Progress bars for qualitative assessments
- Trend arrows showing change from previous snapshot
- Overall momentum score gauge

### 6.4 Transition Card

For each transition:
- From/To ground names
- Status badge
- Change description summary
- Blocker warnings (if any)
- Related refactoring proposals
- Action buttons: Start, Complete, Block, Abandon

---

## 7. Integration Points

### 7.1 With Vision App

- Each Vision has a `grounds` related set
- Ground Zero is auto-created when first accessing grounds for a vision
- Statements are evaluated as evidence for grounds
- References are used in evidence collection

### 7.2 With Dependencies App

- Metrics from `NodeMetrics` feed into momentum calculation
- `LayerViolation` records contribute to evidence
- `RefactoringProposal` objects link to transitions
- `AnalysisRun` timestamps help track when snapshots were valid

### 7.3 With Scope App

- Grounds inherit the project scope from their vision
- Metrics are calculated only for in-scope projects

---

## 8. Workflows

### 8.1 Initial Setup

1. User navigates to Grounds from a Vision
2. System prompts to create Ground Zero
3. Ground Zero is created with:
   - Current state snapshot
   - Initial momentum capture
   - Evidence collection for all formal statements
4. User can add stability rationale

### 8.2 Planning Next Ground

1. User creates a new Ground (status: Planned)
2. User describes what this ground represents
3. User sets prerequisites (other grounds)
4. System suggests which statements should be satisfied
5. User creates Transition from current to planned ground
6. User links relevant refactoring proposals

### 8.3 Achieving a Ground

1. User marks Transition as "In Progress"
2. Team executes changes (outside tool)
3. User periodically captures momentum snapshots
4. When ready, user runs "Collect Evidence"
5. System evaluates all statements
6. If stability criteria met, user marks ground as "Current"
7. Previous current ground becomes "Achieved"

### 8.4 Retrospective

1. User documents blockers encountered during transition
2. User adds lessons learned
3. User compares momentum before/after
4. Insights inform planning of next ground

---

## 9. JSON Schema for State Snapshot

```json
{
  "captured_at": "2024-01-15T10:30:00Z",
  "projects": {
    "project-key": {
      "layer_id": 123,
      "groups": [456, 789],
      "tags": ["api", "payment"]
    }
  },
  "metrics": {
    "total_projects": 150,
    "total_dependencies": 420,
    "cycle_count": 3,
    "avg_coupling": 0.35
  },
  "statements": {
    "stmt-id-1": {
      "status": "formal",
      "is_satisfied": true
    }
  },
  "violations": [
    {
      "id": 101,
      "source": "project-a",
      "target": "project-b",
      "severity": "critical"
    }
  ]
}
```

---

## 10. Momentum Metrics Schema

### Quantitative (Automated)

| Metric | Description | Good Direction |
|--------|-------------|----------------|
| `avg_coupling` | Average Ce/(Ca+Ce) across projects | Lower |
| `cycle_count` | Number of SCCs with size > 1 | Lower |
| `max_cycle_size` | Largest SCC size | Lower |
| `violation_count` | Layer violations | Lower |
| `formal_ratio` | Formal statements / total | Higher |
| `satisfied_ratio` | Satisfied / formal statements | Higher |

### Qualitative (Manual)

| Assessment | Description | Scale |
|------------|-------------|-------|
| `team_confidence` | Team's comfort with current state | 1-5 |
| `deployment_safety` | Confidence in deployment process | 1-5 |
| `test_coverage` | Perceived test coverage adequacy | 1-5 |
| `observability` | Ability to understand system behavior | 1-5 |
| `org_alignment` | Organizational support for changes | 1-5 |

---

## 11. Open Questions

1. **Ground branching**: Should grounds support branching (multiple possible next grounds from one current ground)?
   - Current design: Yes, via prerequisites M2M

2. **Automatic ground detection**: Should the system suggest when a new ground has been achieved?
   - Current design: No, grounds are human-declared milestones

3. **Momentum weighting**: How should quantitative and qualitative factors be weighted in overall score?
   - Current design: Leave as separate, let users interpret

4. **Historical comparison**: How far back should momentum comparisons go?
   - Current design: Compare to previous ground only, full history available

---

## 12. Future Considerations

- **Export/Import**: Ability to export grounds timeline for reporting
- **Notifications**: Alert when momentum metrics degrade significantly
- **Integration**: Connect to CI/CD for automated metric capture
- **Collaboration**: Multiple users working on transition planning
- **Templates**: Pre-defined ground templates for common patterns

---

*This specification is ready for review. Implementation should not begin until approved.*
