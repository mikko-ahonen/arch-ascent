# Layers

Layers are named groupings of components displayed as colored regions on the canvas.

<img src="screenshots/canvas-groups.png" alt="Layers on canvas" style="max-width:100%">

## Layer Types

| Type | Use case |
|------|----------|
| Freeform | General-purpose grouping |
| Bounded Context | Domain-driven design contexts |
| Team | Ownership boundaries |
| Application | Deployment units |
| Imported | Synced from external source (read-only) |

## Creating Layers

1. Open the Layers panel (left sidebar)
2. Click **New Layer**
3. Provide key, name, and select type
4. Choose a color for visual distinction

## Assigning Components

- **Drag & drop** — Drag component into a layer region on canvas
- **Context menu** — Right-click component → Assign to Layer
- **Bulk assign** — Multi-select components, right-click → Assign to Layer

Components can belong to multiple layers (e.g., a service can be in both "Payments Domain" and "Team Alpha").

## Layer Hierarchy

Layers can have parent layers for nested groupings. Set the parent when creating or editing a layer.
