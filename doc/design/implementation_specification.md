# Implementation Specification: Vision Creation System

This document specifies how to implement the vision creation system described in the design documents. It bridges the conceptual model to concrete implementation.

## 1. Current State Assessment

### Already Implemented (Static Analysis)
- ✅ Graph traversal (BFS/DFS)
- ✅ Topological sort with layer violations
- ✅ SCC detection (cycle analysis)
- ✅ Community detection (Louvain)
- ✅ Metrics (instability, centrality, coupling)
- ✅ Basic visualization (Cytoscape.js)

### Gaps to Address
- ❌ Vision drafts
- ❌ Rich grouping model (overlapping, layered, typed)
- ❌ References (named sets with tag-based definitions)
- ❌ Tagging system
- ❌ Intent/statement model
- ❌ Endpoint-level graph
- ❌ Application model
- ❌ Interactive UI patterns (drag sketching, perspective switching)

---

## 2. Data Model Extensions

### 2.1 Core Entity Hierarchy

```
Project (existing) → rename to Component for clarity
  ├── key, name, description
  ├── endpoints[] (new)
  └── tags[] (new)

Application (new)
  ├── key, name, description
  ├── components[] (many-to-many)
  └── tags[]

Endpoint (new)
  ├── component (FK)
  ├── path, method, contract_type
  └── tags[]

Dependency (existing) → extend
  ├── source_component, target_component (existing)
  ├── source_endpoint, target_endpoint (new, optional)
  └── dependency_type (compile, runtime, api_call)
```

### 2.2 Vision Model

```
VisionDraft
  ├── id, name, description
  ├── created_at, updated_at
  ├── status: draft | shared | archived
  ├── parent_draft (FK, nullable) - for branching
  └── snapshot_data (JSON) - frozen state for sharing

VisionDraftMembership
  ├── draft (FK)
  ├── component (FK)
  ├── position_x, position_y (within this draft)
  └── local_tags[] (draft-specific tags)
```

### 2.3 Grouping Model (Enhanced)

```
Grouping
  ├── id, key, name
  ├── vision_draft (FK, nullable) - null = global grouping
  ├── grouping_type: freeform | bounded_context | gitlab_project | team | application
  ├── description
  ├── color, position_x, position_y
  ├── parent_grouping (FK, nullable) - hierarchical
  ├── is_imported: boolean - true if from external source
  └── source_identifier - e.g., GitLab group ID

GroupingMembership
  ├── grouping (FK)
  ├── component (FK) OR endpoint (FK) - polymorphic
  ├── membership_type: explicit | inferred | imported
  └── added_at

# Note: A component CAN belong to multiple groupings (overlap allowed)
```

### 2.4 Tagging System

```
Tag
  ├── id, key (unique)
  ├── name, description
  ├── color
  ├── tag_category: domain | technical | ownership | custom
  └── created_at

TagAssignment
  ├── tag (FK)
  ├── target_type: component | endpoint | grouping | application
  ├── target_id
  ├── vision_draft (FK, nullable) - null = global assignment
  └── assigned_at
```

### 2.5 Reference Model (Architectural Vocabulary)

```
Reference
  ├── id, name (unique within draft)
  ├── vision_draft (FK, nullable)
  ├── description (natural language)
  ├── definition_type: informal | tag_expression | explicit_list
  ├── tag_expression (JSON) - e.g., {"and": ["payment", "api", "public"]}
  ├── explicit_members[] - for explicit_list type
  └── created_at, updated_at

# References resolve dynamically based on current tag state
```

### 2.6 Intent/Statement Model

```
ArchitecturalStatement
  ├── id
  ├── vision_draft (FK)
  ├── statement_type: existence | containment | exclusion | cardinality
  ├── natural_language (text) - human-readable form
  ├── formal_expression (JSON) - machine-evaluable
  ├── status: informal | semi_formal | formal
  ├── is_satisfied: boolean (computed)
  └── created_at

# Example formal_expression:
# {"type": "cardinality", "reference": "PaymentApiDomain", "operator": "==", "value": 1}
# {"type": "containment", "subject": "PaymentPublicApiEndpoints", "container": "PaymentApiDomain"}
```

---

## 3. API Design

### 3.1 Vision Draft API

```
POST   /api/v1/visions/                     Create draft
GET    /api/v1/visions/                     List drafts
GET    /api/v1/visions/{id}/                Get draft with full state
PUT    /api/v1/visions/{id}/                Update draft metadata
DELETE /api/v1/visions/{id}/                Delete draft
POST   /api/v1/visions/{id}/duplicate/      Clone draft
POST   /api/v1/visions/{id}/snapshot/       Create shareable snapshot
GET    /api/v1/visions/{id}/compare/{other}/ Compare two drafts
```

### 3.2 Grouping API

```
POST   /api/v1/visions/{id}/groupings/                   Create grouping
GET    /api/v1/visions/{id}/groupings/                   List groupings
PUT    /api/v1/visions/{id}/groupings/{gid}/             Update grouping
DELETE /api/v1/visions/{id}/groupings/{gid}/             Delete grouping
POST   /api/v1/visions/{id}/groupings/{gid}/members/     Add members
DELETE /api/v1/visions/{id}/groupings/{gid}/members/     Remove members
POST   /api/v1/visions/{id}/groupings/{gid}/merge/{other}/ Merge groupings
POST   /api/v1/visions/{id}/groupings/{gid}/split/       Split grouping
```

### 3.3 Tag API

```
GET    /api/v1/tags/                        List all tags
POST   /api/v1/tags/                        Create tag
DELETE /api/v1/tags/{id}/                   Delete tag
POST   /api/v1/tags/assign/                 Assign tag to element
DELETE /api/v1/tags/assign/                 Remove tag assignment
GET    /api/v1/tags/search/?q=payment       Search by tag
```

### 3.4 Reference API

```
POST   /api/v1/visions/{id}/references/              Create reference
GET    /api/v1/visions/{id}/references/              List references
GET    /api/v1/visions/{id}/references/{rid}/        Get reference with resolved members
PUT    /api/v1/visions/{id}/references/{rid}/        Update reference definition
DELETE /api/v1/visions/{id}/references/{rid}/        Delete reference
GET    /api/v1/visions/{id}/references/{rid}/resolve/ Resolve current members
```

### 3.5 Statement API

```
POST   /api/v1/visions/{id}/statements/              Create statement
GET    /api/v1/visions/{id}/statements/              List statements with satisfaction status
PUT    /api/v1/visions/{id}/statements/{sid}/        Update statement
DELETE /api/v1/visions/{id}/statements/{sid}/        Delete statement
GET    /api/v1/visions/{id}/statements/evaluate/     Evaluate all statements
```

---

## 4. UI Components

### 4.1 Vision Workspace (Main Canvas)

**Component**: `VisionWorkspace`
- Cytoscape.js-based interactive canvas
- Supports: pan, zoom, select, multi-select
- Layers: components, groupings, dependencies (togglable)

**Interactions**:
- Drag component to reposition
- Draw rectangle to create grouping
- Drag component into/out of grouping
- Double-click grouping to edit
- Right-click context menu

### 4.2 Dependency Overlay

**Component**: `DependencyOverlay`
- Hidden by default
- Show on: hover, selection, explicit toggle
- Modes: all, internal-only, external-only, cycles-only

### 4.3 Perspective Switcher

**Component**: `PerspectiveSwitcher`
- Toggle between views:
  - Component view (default)
  - Endpoint view
  - Application overlay
  - Team overlay (if data available)
  - Imported groupings overlay

### 4.4 Tag Panel

**Component**: `TagPanel`
- Sidebar for tag management
- Filter components by tag
- Bulk tag assignment
- Tag search

### 4.5 Reference Panel

**Component**: `ReferencePanel`
- Create/edit references
- Tag expression builder
- Visual preview of resolved members
- Highlight members on canvas

### 4.6 Statement Panel

**Component**: `StatementPanel`
- Natural language statement input
- Statement satisfaction indicator (green/red/yellow)
- Link statements to references

### 4.7 Draft Manager

**Component**: `DraftManager`
- List drafts
- Switch between drafts
- Duplicate draft
- Compare drafts side-by-side

---

## 5. Implementation Phases

### Phase 1: Extended Data Model (Foundation)
1. Rename `Project` → `Component` (or add alias)
2. Add `Endpoint` model
3. Add `Application` model with component membership
4. Extend `Dependency` for endpoint-level edges
5. Create migrations

**Deliverable**: Extended database schema

### Phase 2: Vision Draft System
1. Add `VisionDraft` model
2. Add `VisionDraftMembership` for component positions per draft
3. Add draft CRUD API
4. Add duplicate/snapshot functionality

**Deliverable**: Multiple vision drafts with independent layouts

### Phase 3: Enhanced Grouping Model
1. Replace `NodeGroup` with `Grouping` model
2. Add `GroupingMembership` for many-to-many
3. Support hierarchical groupings (parent FK)
4. Add grouping types
5. Migrate existing NodeGroup data

**Deliverable**: Overlapping, typed, hierarchical groupings

### Phase 4: Tagging System
1. Add `Tag` and `TagAssignment` models
2. Add tag CRUD API
3. Add bulk tag assignment
4. Add tag-based filtering in UI
5. Integrate tags with components, endpoints, groupings

**Deliverable**: Full tagging infrastructure

### Phase 5: References
1. Add `Reference` model
2. Implement tag expression parser
3. Add reference resolution logic
4. Add reference API
5. Add UI for reference creation/editing

**Deliverable**: Named sets with tag-based definitions

### Phase 6: Intent/Statements
1. Add `ArchitecturalStatement` model
2. Implement statement evaluation engine
3. Add statement API
4. Add UI for statement creation
5. Show satisfaction status

**Deliverable**: Evaluable architectural statements

### Phase 7: UI Enhancements
1. Dependency overlay (on-demand visibility)
2. Perspective switcher
3. Draft comparison view
4. Drag-based grouping creation
5. Reference/statement panels

**Deliverable**: Full vision creation UI

---

## 6. Migration Strategy

### From Current State

```python
# Current models to migrate/extend:
Project       → Component (rename or alias)
Dependency    → Dependency (extend with endpoint support)
NodeGroup     → Grouping (replace with richer model)
LayerDefinition → (keep, integrates with grouping types)
```

### Data Migration Steps
1. Add new tables without removing old ones
2. Migrate NodeGroup → Grouping with type='legacy'
3. Migrate LayerAssignment → GroupingMembership
4. Deprecate NodeGroup after verification
5. Remove deprecated tables in later release

---

## 7. LLM Enhancement Points

Following the "deterministic core, optional intelligence" principle:

| Feature | Baseline (No LLM) | Enhanced (With LLM) |
|---------|-------------------|---------------------|
| Grouping suggestions | Louvain clustering | Semantic domain inference |
| Tag suggestions | Pattern matching on names | Concept extraction |
| Reference definitions | Manual tag expressions | Natural language → expression |
| Statement formalization | Manual structured input | NL → formal statement |
| Intent explanation | Show violations | Explain why & suggest fixes |

---

## 8. Testing Strategy

### Unit Tests
- Tag expression parser
- Reference resolution
- Statement evaluation
- Grouping membership logic

### Integration Tests
- Vision draft lifecycle
- Tag propagation across drafts
- Reference resolution with changing tags
- Statement evaluation with graph changes

### UI Tests
- Canvas interactions (Cypress)
- Grouping drag-and-drop
- Perspective switching
- Panel state management

---

## 9. Success Criteria

### Phase 1-3 Complete When:
- Architect can create multiple vision drafts
- Components can belong to multiple overlapping groupings
- Groupings can be hierarchical
- Draft layouts are independent

### Phase 4-5 Complete When:
- Architect can tag any element
- References resolve dynamically as tags change
- UI shows resolved members visually

### Phase 6-7 Complete When:
- Architect can write architectural statements
- Statements evaluate against current state
- Full UI supports vision creation workflow

---

## 10. File Structure

```
/src
├── dependencies/
│   ├── models.py              # Extend with new models
│   ├── api/
│   │   ├── views.py           # Extend with vision/grouping/tag APIs
│   │   └── serializers.py     # Add serializers for new models
│   ├── services/
│   │   ├── tag_resolver.py    # Tag expression evaluation
│   │   ├── reference_resolver.py  # Reference member resolution
│   │   └── statement_evaluator.py # Statement satisfaction checking
│   ├── components/
│   │   └── vision/            # New vision workspace component
│   └── management/commands/
│       ├── import_endpoints.py    # Import endpoint data
│       └── import_applications.py # Import application data
└── tests/
    ├── test_tags.py
    ├── test_references.py
    └── test_statements.py
```

---

## 11. Key Design Decisions

1. **Groupings are NOT containers in the strict sense** - components can belong to multiple groupings simultaneously

2. **References are dynamic** - they resolve based on current tag state, not stored membership

3. **Vision drafts are independent** - changes in one draft don't affect others

4. **Tags are global, assignments can be draft-scoped** - allows draft-specific explorations

5. **Statements describe intent, not enforce it** - violations are informational

6. **Endpoints are first-class** - dependency graph exists at both component and endpoint level

7. **Imported groupings are read-only** - GitLab groups, etc. are signals, not editable structures
