# Tagged Editor Component Specification

## Overview

The Tagged Editor is a reusable Django component that provides a rich text editor with inline annotation capabilities. Users can select portions of text and tag them with named references, which are visually displayed as bracket-style underlines with labels.

## Purpose

The component enables users to:
- Annotate text passages with semantic tags (references)
- Visualize tagged regions with colored bracket notation
- Support nested and multi-line tag annotations
- Create, edit, and remove tags through an intuitive popup interface

## Component Location

```
src/vision/components/tagged_editor/
├── tagged_editor.py      # Django component class
├── tagged_editor.html    # Template
├── tagged_editor.js      # Client-side logic
└── tagged_editor.css     # Styles
```

## Usage

```django
{% component "tagged_editor"
    editor_id="my-editor"
    content="Initial text content"
    tags=existing_tags
    available_tags=reference_list
    vision_id=vision.id
    placeholder="Enter text..."
    readonly=False
%}{% endcomponent %}
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `editor_id` | string | `"tagged-editor"` | Unique identifier for the editor instance |
| `content` | string | `""` | Initial text content |
| `tags` | list | `[]` | Existing tag annotations |
| `available_tags` | list | `[]` | Reference types available for tagging |
| `vision_id` | int | `None` | Vision ID for backend reference creation |
| `placeholder` | string | `"Enter text..."` | Placeholder when empty |
| `readonly` | bool | `False` | Disable editing |

## Data Structures

### Tag Annotation

```json
{
  "id": "tag-1234567890",
  "start": 0,
  "end": 15,
  "tag": "Reference Name",
  "color": "#3498db"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier (auto-generated if not provided) |
| `start` | int | Start character position (0-indexed) |
| `end` | int | End character position (exclusive) |
| `tag` | string | Reference/tag name |
| `color` | string | Hex color for visual display |

### Available Tag

```json
{
  "name": "Requirement",
  "color": "#2ecc71",
  "description": "Links to a requirement document"
}
```

## Visual Design

### Bracket Notation

Tags are rendered as bracket-style underlines below the annotated text:

```
The quick brown fox jumps over the lazy dog.
    └────────────────────┘
           subject
```

- **Left bracket**: Vertical line at start position
- **Horizontal line**: Spans the tagged text
- **Right bracket**: Vertical line at end position
- **Label**: Centered below the bracket

### Multi-line Support

When tagged text spans multiple lines, each line segment gets its own bracket portion:

```
The quick brown fox
└───────────────────    (first segment - left bracket only)
jumps over the lazy
────────────────────    (middle segment - line only)
dog in the park.
────────────┘           (last segment - right bracket only)
   subject              (label on longest segment)
```

### Nested Tags

Nested tags are rendered at increasing depths:
- Inner tags (containing fewer other tags) are drawn closest to the text
- Outer tags (containing more tags) are drawn progressively lower
- Each nesting level adds 12px of vertical offset

```
The quick brown fox jumps
    └────────────────┘       (inner tag - level 0)
└─────────────────────────┘  (outer tag - level 1)
      noun                    (inner label)
           clause             (outer label)
```

### Colors

Default tag colors cycle through:
- `#3498db` (blue)
- `#2ecc71` (green)
- `#e74c3c` (red)
- `#9b59b6` (purple)
- `#f39c12` (orange)
- `#1abc9c` (teal)

## User Interactions

### Creating a Tag

1. **Select text** by clicking and dragging
2. **Popup appears** below selection with available references
3. **Click a reference** to apply the tag
4. Or click **"Create New Reference"** to define a new one

### Editing a Tag

1. **Click on tagged text** (highlighted region)
2. **Popup shows** current tag name and options:
   - **Remove Tag**: Delete the annotation
   - **Change to**: Switch to a different reference

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Escape` | Close popup without action |
| `Shift+Arrow` | Extend selection (shows popup) |

### Constraints

- Tags cannot partially overlap (crossing boundaries)
- Valid configurations:
  - Completely separate tags
  - Fully nested tags (one inside another)
  - Adjacent tags (touching but not overlapping)
- Invalid selection triggers a red flash on the editor border

## JavaScript API

### Initialization

```javascript
initTaggedEditor(editorId, initialTags, options);
```

### Global Functions

| Function | Description |
|----------|-------------|
| `getTaggedEditorState(editorId)` | Returns `{text, tags}` |
| `setTaggedEditorContent(editorId, text, tags)` | Sets editor content |
| `setTaggedEditorReferences(editorId, references)` | Updates available tags |
| `taggedEditorApplyTag(editorId, tagName, tagColor)` | Apply tag to selection |
| `taggedEditorRemoveTag(editorId)` | Remove tag at cursor |
| `taggedEditorRemoveTagById(editorId, tagId)` | Remove specific tag |
| `taggedEditorChangeTag(editorId, tagId, newName, newColor)` | Change tag type |

### Events

The component dispatches a custom event on state changes:

```javascript
editor.container.addEventListener('taggedEditorChange', (e) => {
  const { text, tags } = e.detail;
  // Handle change
});
```

### State Storage

Editor state is serialized to a hidden input for form submission:

```html
<input type="hidden" id="{editor_id}-data" name="{editor_id}" value="...">
```

Value format:
```json
{
  "text": "The full text content",
  "tags": [/* array of tag objects */]
}
```

## Backend Integration

### Reference Creation

When `vision_id` is provided, creating a new reference triggers an API call:

```
POST /vision/htmx/reference-create/
Content-Type: application/x-www-form-urlencoded

vision_id={id}&name={name}&color={color}
```

### Toolbar Mode vs Popup Mode

- **Popup Mode** (default when `vision_id` is set): Tags are applied via selection popup
- **Toolbar Mode** (when `available_tags` but no `vision_id`): Tags are applied via toolbar buttons

## CSS Customization

Key CSS custom properties:

| Property | Description |
|----------|-------------|
| `--tag-color` | Per-tag color (set via inline style) |

Key CSS classes:

| Class | Element |
|-------|---------|
| `.tagged-editor-container` | Outer wrapper |
| `.tagged-editor-toolbar` | Toolbar (toolbar mode) |
| `.tagged-editor-content` | Editable text area |
| `.tagged-text` | Span wrapping tagged text |
| `.tag-overlay` | Container for bracket graphics |
| `.tag-line-segment` | Individual bracket segment |
| `.tag-label` | Text label below bracket |
| `.tag-popup` | Selection/edit popup |

## Performance Considerations

- **Line height adjustment**: Editor line-height increases based on maximum nesting depth to accommodate bracket graphics
- **Reflow trigger**: `offsetHeight` is accessed after line-height changes to force browser reflow before calculating positions
- **Debounced updates**: Text input triggers state save after 100ms debounce

## Limitations

1. **No HTML content**: Editor works with plain text only; HTML is stripped
2. **Character-based positions**: Tags use character offsets, not DOM positions
3. **Single editor focus**: Only one popup can be open at a time per editor
4. **Browser support**: Requires modern browser with `contenteditable` support

## Implementation Decisions

### 1. Text Storage: Separate from DOM

**Decision**: Store plain text in `editor.text` separately from the DOM content.

**Rationale**: The `contenteditable` div contains rendered HTML with tag spans, overlays, and visual elements. Extracting accurate text positions from this mixed content is error-prone. By maintaining a separate plain text copy, we ensure:
- Accurate character offset calculations for tags
- Clean serialization without HTML artifacts
- Simpler text synchronization logic

**Trade-off**: Requires careful synchronization between `editor.text` and DOM on every input event, with a 100ms debounce to balance responsiveness and performance.

### 2. Character-Based Positioning (Not DOM Nodes)

**Decision**: Tags use character offsets (`start`, `end`) rather than DOM node references.

**Rationale**:
- DOM structure changes when tags are rendered (text split into spans)
- Character positions are stable across re-renders
- Simplifies serialization for backend storage
- Enables straightforward overlap detection arithmetic

**Trade-off**: Requires converting between DOM selection ranges and character offsets using `Range.toString().length`, which involves temporarily removing the overlay to get accurate counts.

### 3. Overlay-Based Bracket Rendering

**Decision**: Render bracket graphics in a separate overlay div positioned absolutely, rather than inline with text.

**Rationale**:
- Brackets need to extend below text without affecting text flow
- Multi-line tags require independent line segments
- Nested tags need stacked brackets at different vertical positions
- Labels must be centered regardless of text alignment

**Implementation**: The overlay is inserted as the first child of the content div and uses `pointer-events: none` so clicks pass through to the underlying text.

### 4. Dynamic Line Height Adjustment

**Decision**: Dynamically adjust the editor's `line-height` based on maximum tag nesting depth.

**Rationale**: Bracket graphics extend below text. Without additional space, brackets would overlap with the next line of text. The formula:
```
newLineHeight = (baseLineHeight * fontSize) + bracketHeight + labelHeight + padding
```

**Trade-off**: All lines get the same increased spacing, even those without tags. This ensures consistent visual rhythm but uses more vertical space than strictly necessary.

### 5. Nesting Level Calculation

**Decision**: Calculate nesting level as "how many other tags this tag completely contains."

**Rationale**: Outer tags (containing inner tags) should be drawn further from the text to avoid visual overlap. By counting containment rather than depth-from-root, we ensure:
- Inner tags are always closest to their text
- Outer tags stack below in consistent order
- Independent tag groups don't affect each other's levels

**Implementation**:
```javascript
let nestingLevel = 0;
editor.tags.forEach(otherTag => {
    if (tag.start <= otherTag.start && tag.end >= otherTag.end) {
        nestingLevel++;
    }
});
```

### 6. Popup-Based Tag Selection (vs. Toolbar)

**Decision**: Default to popup-based tag selection that appears on text selection, with toolbar as fallback.

**Rationale**:
- Popup appears contextually near the selection, reducing mouse travel
- Supports dynamic reference creation inline
- Works better with long reference lists (scrollable popup vs. crowded toolbar)
- Toolbar mode retained for simpler use cases without `vision_id`

### 7. No Partial Overlaps Constraint

**Decision**: Forbid tags that partially overlap (cross boundaries).

**Rationale**:
- Simplifies rendering logic (no need for complex intersection handling)
- Avoids ambiguous visual representations
- Matches semantic expectation (annotations are hierarchical, not intersecting)

**Valid configurations**:
```
[----A----]  [----B----]     # Separate
[--------A--------]           # A contains B
    [----B----]
[--A--][--B--]                # Adjacent
```

**Invalid**:
```
[----A----]
      [----B----]             # Partial overlap - REJECTED
```

**Feedback**: Invalid selections trigger a 300ms red border flash on the editor.

### 8. Two-Pass Rendering for Labels

**Decision**: Render all bracket lines first, then all labels in a second pass.

**Rationale**: Labels should always appear on top of bracket lines, even when tags overlap visually. A single-pass render might draw a label, then draw another tag's bracket line over it.

```javascript
// First pass: Draw all brackets
taggedSpans.forEach(span => { /* draw brackets */ });

// Second pass: Draw all labels on top
labelsToRender.forEach(labelData => { /* draw labels */ });
```

### 9. Label Placement on Longest Segment

**Decision**: For multi-line tags, place the label on the longest (widest) line segment.

**Rationale**:
- Longest segment has most space for label text
- Avoids label truncation on short segments
- Provides visual balance for wrapped text

### 10. Range.getClientRects() for Multi-line Detection

**Decision**: Use `Range.getClientRects()` on text nodes to detect line wrapping.

**Rationale**: A single `getBoundingClientRect()` returns one rectangle spanning all lines. `getClientRects()` returns separate rectangles for each visual line, enabling per-line bracket rendering.

**Implementation**:
```javascript
const range = document.createRange();
range.setStart(textNodes[0], 0);
range.setEnd(textNodes[last], textNodes[last].length);
const rects = Array.from(range.getClientRects());
```

### 11. ESC Key Handling with Event Propagation Stop

**Decision**: Intercept ESC key at document level and stop propagation when popup is visible.

**Rationale**: The editor may be used inside modals. Without stopping propagation, ESC would close both the popup AND the parent modal, which is unexpected behavior.

```javascript
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && popup.style.display !== 'none') {
        e.preventDefault();
        e.stopPropagation();
        popup.style.display = 'none';
    }
});
```

### 12. Global Function Exposure

**Decision**: Expose all API functions on the `window` object.

**Rationale**:
- Enables inline `onclick` handlers in dynamically generated popup HTML
- Allows external code to interact with editors
- Supports multiple editor instances via `editorId` parameter

**Trade-off**: Pollutes global namespace. Mitigated by prefixing all functions with `taggedEditor*`.

### 13. Hidden Input for Form Integration

**Decision**: Serialize editor state to a hidden input field for standard form submission.

**Rationale**:
- Works with traditional Django form handling
- No special JavaScript needed on submit
- State persists through page interactions

**Format**: JSON object with `text` and `tags` properties.

### 14. Deferred Overlay Removal for Position Calculation

**Decision**: Temporarily remove the overlay div before calculating selection positions.

**Rationale**: The overlay contains tag labels which are text nodes. When calculating character offsets via `Range.toString()`, these label texts would be included, corrupting the offset calculation.

```javascript
const overlay = editor.content.querySelector('.tag-overlay');
if (overlay) overlay.remove();
// ... calculate positions ...
if (overlay) editor.content.insertBefore(overlay, editor.content.firstChild);
```

### 15. CSS Custom Properties for Tag Colors

**Decision**: Use CSS custom property `--tag-color` on each tagged span.

**Rationale**:
- Enables color inheritance to child elements (bracket lines, labels)
- Single point of color definition per tag
- Allows CSS-based hover effects using the same color

## Example Integration

```python
# views.py
def vision_detail(request, pk):
    vision = get_object_or_404(Vision, pk=pk)
    return render(request, 'vision/detail.html', {
        'vision': vision,
        'content': vision.problem_statement,
        'tags': vision.get_tags_json(),
        'references': vision.references.all(),
    })
```

```django
{# detail.html #}
{% component "tagged_editor"
    editor_id="problem-statement"
    content=content
    tags=tags
    available_tags=references
    vision_id=vision.id
%}{% endcomponent %}
```
