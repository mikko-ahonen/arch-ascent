# Vision Creation UI – Interaction Patterns

This document elaborates the **explicit interaction patterns** supported by the Vision Creation UI. These patterns describe *how architects actually work* with the system to form, explore, and communicate an architectural vision for large-scale microservice systems.

The interaction patterns are intentionally **human-centered**, exploratory, and reversible. They are designed to support thinking, not to enforce correctness.

This document builds directly on the previously defined **Vision Creation UI Model** and introduces no new conceptual abstractions.

---

## 1. Core Interaction Philosophy

The Vision Creation UI is designed around the following principles:

- **Externalize cognition**: move structure out of the architect’s head and into the workspace
- **Iterate safely**: all actions are reversible and non-destructive
- **Work top-down and bottom-up**: allow switching freely between abstraction levels
- **Prefer manipulation over configuration**: direct interaction beats forms and dialogs

The UI behaves like a *thinking surface*, not a control panel.

---

## 2. Initial Orientation Pattern

### Purpose

Help the architect answer the first question:

> “What am I actually looking at?”

### Interaction

- Open the workspace with a **collapsed default view**
- Show a high-level representation of the system (e.g. clusters or dense regions)
- Allow quick toggling of:
  - Component count
  - Dependency density
  - Presence of cycles

### Outcome

The architect gains an initial sense of:

- Scale
- Structural complexity
- Where attention may be needed

No decisions are made at this stage.

---

## 3. Zoom and Scope Control

### Purpose

Control cognitive load by limiting what is visible at any time.

### Interaction

- Zoom in/out to:
  - Expand a cluster into individual components
  - Collapse a set of components into a single visual unit
- Pan across the workspace without losing context

Zooming is semantic, not just visual:

- Zooming in reveals more detail
- Zooming out emphasizes relationships

---

## 4. Grouping and Ungrouping Components

### Purpose

Allow architects to test ideas about conceptual boundaries.

### Interaction

- Select multiple components
- Use a **visual region** for groupings
- Groupings are
  - Soft
  - Tentative
  - Neutral with regards to the meaning of the group
  - May be typed, and may be assigned a type (such as Bounded context, GitLab project etc.)
  - Exploratory
  - Have a name
  - Ungroup or reassign components at any time
  - Allowed to overlap conceptually over time

The UI must make it clear that grouping does *not* imply commitment.

---

## 5. Drag-Based Boundary Sketching

### Purpose

Support imprecise, visual thinking.

### Interaction

- Draw freeform regions on the workspace
- Drag components into or out of regions
- Resize or reshape regions freely

Boundaries are intentionally fuzzy at first.

This mirrors how architects think before formalizing structure.

---

## 6. Dependency Awareness on Demand

### Purpose

Avoid overwhelming the architect with edges.

### Interaction

- Dependencies are hidden by default
- Reveal dependencies:
  - On hover
  - On selection
  - On explicit request

The architect can:

- See internal vs external dependencies for a region
- Temporarily highlight cycles

Dependency visibility is **situational**, not constant.

---

## 7. Perspective Switching

### Purpose

Allow the same structure to be viewed through different lenses.

### Interaction

Toggle between perspectives such as:

- Component-level view
- Endpoint-level view
- Application overlay
- Team responsibility overlay (if available)

Switching perspective does not change the vision draft — only how it is viewed.

---

## 8. Vision Draft Management

### Purpose

Encourage exploration of alternatives.

### Interaction

- Create multiple vision drafts
- Duplicate an existing draft
- Switch between drafts
- Compare drafts visually

Drafts are first-class artifacts.

The UI should normalize having several incomplete or competing visions.

---

## 9. Descriptive Feedback Patterns

### Purpose

Provide insight without judgment.

### Interaction

The UI may surface:

- High dependency density between regions
- Cycles crossing intended boundaries
- Components that span many regions

Feedback is:

- Descriptive
- Visual
- Non-blocking

The UI never labels a draft as “invalid”.

---

## 10. Progressive Refinement Pattern

### Purpose

Support gradual clarification of vision.

### Interaction

Over time, the architect may:

- Rename regions
- Split regions
- Merge regions
- Clarify intended directionality

The UI supports repeated refinement without forcing completion.

---

## 11. Annotation and Rationale Capture

### Purpose

Preserve architectural intent.

### Interaction

- Attach notes to regions, components, or drafts
- Record open questions or uncertainties
- Capture why a grouping exists

Annotations are lightweight and optional.

---

## 12. Vision as a Shareable Artifact

### Purpose

Enable communication and alignment.

### Interaction

- Freeze a snapshot of a vision draft
- Generate simplified views for discussion
- Hide exploratory clutter

Shared views emphasize clarity over completeness.

---

## 13. Relationship to Grounds

At this stage:

- No grounds are defined
- No sequencing is planned

The interaction patterns exist solely to help:

- Form vision
- Clarify intent
- Reduce ambiguity

Transition to grounds happens only after sufficient clarity emerges.

---

## 14. Formal and Semi‑Formal Intent Modeling

### Purpose

Support the evolution of architectural intent from vague ideas into precise, communicable, and eventually checkable statements — without forcing premature formalization.

This interaction pattern exists to:

- Help architects express intent explicitly
- Reduce ambiguity as vision matures
- Bridge visual vision and future validation

---

### 14.1 Free‑Form Intent Capture

At early stages, architects may capture intent as:

- Natural language notes
- Rough rules
- Questions or hypotheses

Examples:

- "Payment APIs should probably live together"
- "There should be one public payment interface"

These intents:

- Are attached to vision drafts
- Are non‑binding
- Serve as thinking aids

---

### 14.2 Tagging as a First‑Class Interaction

The UI supports tagging of:

- Components
- Endpoints
- Applications
- Groupings

Tags are:

- User‑defined
- Multi‑valued
- Non‑exclusive

Examples:

- `payment`
- `api`
- `public`
- `internal`

Tagging is lightweight and reversible.

---

### 14.3 Tag‑Based References

Tags can be composed into **named references** that identify sets of elements.

Examples:

- `PaymentPublicApiEndpoints = endpoints tagged with payment AND api AND public`
- `PaymentApiDomain = domain tagged with payment AND api AND public`

These references:

- Are symbolic
- Update automatically as tags change
- Allow architects to talk about architecture at a higher level

---

### 14.4 Semi‑Formal Architectural Statements

Architects can express intents using references.

Examples:

- "There must be only one $PaymentApiDomain"
- "All $PaymentPublicApiEndpoints should belong to $PaymentApiDomain"

At this stage:

- Statements are descriptive, not enforced
- Violations are informational
- Ambiguity is allowed

The goal is **clarity**, not correctness.

---

### 14.5 Progressive Formalization

Over time, intents may evolve:

- From free‑form notes
- To semi‑formal statements
- Toward formally evaluable rules

The UI supports this evolution without forcing it.

Formalization is optional and gradual.

---

### 14.6 Feedback Without Policing

When statements are present, the UI may:

- Highlight matching or non‑matching elements
- Show counts (e.g. number of domains matching a reference)
- Indicate where intent is unclear

The UI does not:

- Block changes
- Enforce compliance
- Declare the vision invalid

---

### 14.7 Relationship to Vision and Grounds

Formal and semi‑formal intents:

- Clarify the vision
- Help communicate architectural goals
- Prepare the ground for later validation

They do **not** define grounds by themselves.

---

## 15. Summary

The additional interaction patterns:

- Allow architectural intent to be stated explicitly
- Support gradual formalization
- Enable higher‑level reasoning via tags and references
- Preserve flexibility during vision creation

They strengthen the Vision Creation UI without changing its exploratory nature.

