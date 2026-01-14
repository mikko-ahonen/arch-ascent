/**
 * Tagged Editor Component
 *
 * A text editor that allows tagging/annotating portions of text with
 * visual underlines and tag labels. Supports popup tag selection.
 */

// Store for all editor instances
window.taggedEditors = window.taggedEditors || {};

/**
 * Initialize a tagged editor instance
 */
function initTaggedEditor(editorId, initialTags = [], options = {}) {
    const container = document.getElementById(`${editorId}-container`);
    const content = document.getElementById(`${editorId}-content`);
    const dataInput = document.getElementById(`${editorId}-data`);

    if (!container || !content) {
        console.error(`Tagged editor elements not found for: ${editorId}`);
        return;
    }

    // Store the initial plain text before any rendering
    const initialText = content.innerText || content.textContent || '';

    // Ensure all initial tags have IDs
    const tagsWithIds = (initialTags || []).map((tag, index) => ({
        ...tag,
        id: tag.id || `tag-init-${index}-${Date.now()}`
    }));

    // Create editor state
    const editor = {
        id: editorId,
        container: container,
        content: content,
        dataInput: dataInput,
        text: initialText,  // Store text separately
        tags: tagsWithIds,
        availableTags: options.availableTags || [],
        onTagSelect: options.onTagSelect || null,
        visionId: options.visionId || null,
    };

    window.taggedEditors[editorId] = editor;

    // Create tag popup element
    createTagPopup(editor);

    // Render initial tags
    renderTaggedContent(editor);

    // Listen for text changes
    content.addEventListener('input', () => {
        clearTimeout(editor.updateTimeout);
        editor.updateTimeout = setTimeout(() => {
            // Update stored text from DOM (strip any HTML first)
            const tempDiv = document.createElement('div');
            tempDiv.innerHTML = content.innerHTML;
            // Remove overlay and tag markers before getting text
            tempDiv.querySelectorAll('.tag-overlay, .tag-end-marker, .tag-bottom-line, .tag-label').forEach(el => el.remove());
            editor.text = tempDiv.innerText || tempDiv.textContent || '';

            // Save state but don't re-render (to preserve cursor)
            saveEditorState(editor);
        }, 100);
    });

    // Listen for mouseup to show tag popup on selection
    content.addEventListener('mouseup', (e) => {
        // Don't show selection popup if clicking on a tagged element
        if (e.target.closest('.tagged-text')) {
            return;
        }
        setTimeout(() => showTagPopupOnSelection(editor, e), 10);
    });

    // Listen for keyup (shift+arrow selection)
    content.addEventListener('keyup', (e) => {
        if (e.shiftKey) {
            setTimeout(() => showTagPopupOnSelection(editor, e), 10);
        }
    });

    // Hide popup when clicking outside
    document.addEventListener('mousedown', (e) => {
        const popup = document.getElementById(`${editorId}-tag-popup`);
        if (popup && !popup.contains(e.target) && !content.contains(e.target)) {
            popup.style.display = 'none';
        }
    });

    // ESC key closes popup (and prevents modal from closing)
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            const popup = document.getElementById(`${editorId}-tag-popup`);
            if (popup && popup.style.display !== 'none') {
                e.preventDefault();
                e.stopPropagation();
                popup.style.display = 'none';
            }
        }
    });

    // Click handler for tagged text (to edit/remove tags)
    content.addEventListener('click', (e) => {
        const taggedSpan = e.target.closest('.tagged-text');
        if (taggedSpan) {
            e.preventDefault();
            e.stopPropagation();
            showTagEditPopup(editor, taggedSpan);
        }
    });

    // Save initial state
    saveEditorState(editor);
}

/**
 * Create the tag selection popup
 */
function createTagPopup(editor) {
    const popup = document.createElement('div');
    popup.id = `${editor.id}-tag-popup`;
    popup.className = 'tag-popup';
    popup.style.cssText = `
        display: none;
        position: absolute;
        z-index: 1000;
        background: #1a1a2e;
        border: 1px solid #495057;
        border-radius: 4px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        padding: 8px;
        min-width: 200px;
        max-width: 300px;
    `;
    editor.container.appendChild(popup);
}

/**
 * Show tag popup when text is selected
 */
function showTagPopupOnSelection(editor, event) {
    const selection = window.getSelection();
    const popup = document.getElementById(`${editor.id}-tag-popup`);

    if (!selection || selection.isCollapsed || !popup) {
        if (popup) popup.style.display = 'none';
        return;
    }

    // Check if selection is within our editor
    if (!editor.content.contains(selection.anchorNode) ||
        !editor.content.contains(selection.focusNode)) {
        popup.style.display = 'none';
        return;
    }

    const range = selection.getRangeAt(0);
    const rect = range.getBoundingClientRect();
    const containerRect = editor.container.getBoundingClientRect();

    // Build popup content
    let popupHtml = `
        <div class="tag-popup-header" style="font-size: 11px; color: #6c757d; margin-bottom: 8px; text-transform: uppercase;">
            Tag selection as:
        </div>
        <div class="tag-popup-list" style="max-height: 200px; overflow-y: auto;">
    `;

    // Add available tags (references)
    if (editor.availableTags && editor.availableTags.length > 0) {
        editor.availableTags.forEach(tag => {
            popupHtml += `
                <button type="button" class="tag-popup-item" onclick="event.preventDefault(); event.stopPropagation(); taggedEditorApplyTagFromPopup('${editor.id}', '${escapeHtml(tag.name)}', '${tag.color || '#3498db'}')"
                    style="display: flex; align-items: center; width: 100%; padding: 6px 8px; margin: 2px 0; border: none; background: transparent; color: #e4e4e4; text-align: left; border-radius: 4px; cursor: pointer;"
                    onmouseover="this.style.background='#2d2d4a'" onmouseout="this.style.background='transparent'">
                    <span style="width: 10px; height: 10px; border-radius: 50%; background: ${tag.color || '#3498db'}; margin-right: 8px;"></span>
                    <span style="flex: 1;">${escapeHtml(tag.name)}</span>
                </button>
            `;
        });
    } else {
        popupHtml += `<div style="color: #6c757d; font-size: 12px; padding: 8px;">No references defined</div>`;
    }

    popupHtml += `
        </div>
        <div style="border-top: 1px solid #495057; margin-top: 8px; padding-top: 8px;">
            <button type="button" class="btn btn-sm btn-outline-secondary w-100 mb-2" onclick="event.preventDefault(); event.stopPropagation(); taggedEditorCreateNewReference('${editor.id}')">
                + New Reference
            </button>
            <button type="button" class="btn btn-sm btn-outline-secondary w-100" onclick="event.preventDefault(); event.stopPropagation(); taggedEditorClosePopup('${editor.id}')">
                Cancel
            </button>
        </div>
    `;

    popup.innerHTML = popupHtml;

    // Position popup below selection
    popup.style.left = `${rect.left - containerRect.left}px`;
    popup.style.top = `${rect.bottom - containerRect.top + 5}px`;
    popup.style.display = 'block';
}

/**
 * Show popup for editing an existing tag (change or remove)
 */
function showTagEditPopup(editor, taggedSpan) {
    const popup = document.getElementById(`${editor.id}-tag-popup`);
    if (!popup) return;

    const tagId = taggedSpan.dataset.tagId;
    const tagName = taggedSpan.dataset.tag;
    const rect = taggedSpan.getBoundingClientRect();
    const containerRect = editor.container.getBoundingClientRect();

    // Build popup content for editing
    let popupHtml = `
        <div class="tag-popup-header" style="font-size: 11px; color: #6c757d; margin-bottom: 8px;">
            <span style="text-transform: uppercase;">Tagged as:</span>
            <strong style="color: #e4e4e4; margin-left: 4px;">${escapeHtml(tagName)}</strong>
        </div>
        <div style="border-bottom: 1px solid #495057; margin-bottom: 8px; padding-bottom: 8px;">
            <button type="button" class="btn btn-sm btn-outline-danger w-100" onclick="event.preventDefault(); event.stopPropagation(); taggedEditorRemoveTagById('${editor.id}', '${tagId}')">
                <i class="bi bi-x-lg me-1"></i>Remove Tag
            </button>
        </div>
        <div class="tag-popup-header" style="font-size: 11px; color: #6c757d; margin-bottom: 8px; text-transform: uppercase;">
            Change to:
        </div>
        <div class="tag-popup-list" style="max-height: 150px; overflow-y: auto;">
    `;

    // Add available tags (references) except current one
    if (editor.availableTags && editor.availableTags.length > 0) {
        editor.availableTags.forEach(tag => {
            if (tag.name !== tagName) {
                popupHtml += `
                    <button type="button" class="tag-popup-item" onclick="event.preventDefault(); event.stopPropagation(); taggedEditorChangeTag('${editor.id}', '${tagId}', '${escapeHtml(tag.name)}', '${tag.color || '#3498db'}')"
                        style="display: flex; align-items: center; width: 100%; padding: 6px 8px; margin: 2px 0; border: none; background: transparent; color: #e4e4e4; text-align: left; border-radius: 4px; cursor: pointer;"
                        onmouseover="this.style.background='#2d2d4a'" onmouseout="this.style.background='transparent'">
                        <span style="width: 10px; height: 10px; border-radius: 50%; background: ${tag.color || '#3498db'}; margin-right: 8px;"></span>
                        <span style="flex: 1;">${escapeHtml(tag.name)}</span>
                    </button>
                `;
            }
        });
    }

    popupHtml += `
        </div>
        <div style="border-top: 1px solid #495057; margin-top: 8px; padding-top: 8px;">
            <button type="button" class="btn btn-sm btn-outline-secondary w-100" onclick="event.preventDefault(); event.stopPropagation(); taggedEditorClosePopup('${editor.id}')">
                Cancel
            </button>
        </div>
    `;

    popup.innerHTML = popupHtml;

    // Position popup below the tagged text
    popup.style.left = `${rect.left - containerRect.left}px`;
    popup.style.top = `${rect.bottom - containerRect.top + 5}px`;
    popup.style.display = 'block';
}

/**
 * Close the tag popup
 */
function taggedEditorClosePopup(editorId) {
    const popup = document.getElementById(`${editorId}-tag-popup`);
    if (popup) popup.style.display = 'none';
}

/**
 * Remove a tag by its ID
 */
function taggedEditorRemoveTagById(editorId, tagId) {
    const editor = window.taggedEditors[editorId];
    if (!editor) return;

    // Hide popup
    const popup = document.getElementById(`${editorId}-tag-popup`);
    if (popup) popup.style.display = 'none';

    // Remove the tag
    editor.tags = editor.tags.filter(t => t.id !== tagId);
    renderTaggedContent(editor);
    saveEditorState(editor);
}

/**
 * Change a tag to a different reference
 */
function taggedEditorChangeTag(editorId, tagId, newTagName, newTagColor) {
    const editor = window.taggedEditors[editorId];
    if (!editor) return;

    // Hide popup
    const popup = document.getElementById(`${editorId}-tag-popup`);
    if (popup) popup.style.display = 'none';

    // Find and update the tag
    const tag = editor.tags.find(t => t.id === tagId);
    if (tag) {
        tag.tag = newTagName;
        tag.color = newTagColor;
        renderTaggedContent(editor);
        saveEditorState(editor);
    }
}

/**
 * Apply tag from popup selection
 */
function taggedEditorApplyTagFromPopup(editorId, tagName, tagColor) {
    const editor = window.taggedEditors[editorId];
    if (!editor) return;

    // Hide popup
    const popup = document.getElementById(`${editorId}-tag-popup`);
    if (popup) popup.style.display = 'none';

    // Apply the tag
    taggedEditorApplyTag(editorId, tagName, tagColor);
}

/**
 * Create new reference dialog
 */
function taggedEditorCreateNewReference(editorId) {
    const editor = window.taggedEditors[editorId];
    if (!editor) return;

    // Hide popup
    const popup = document.getElementById(`${editorId}-tag-popup`);
    if (popup) popup.style.display = 'none';

    // Get selected text as default name
    const selection = window.getSelection();
    const selectedText = selection ? selection.toString().trim() : '';

    // Prompt for reference name
    const refName = prompt('Enter reference name:', selectedText);
    if (!refName) return;

    // Generate a color
    const colors = ['#3498db', '#2ecc71', '#e74c3c', '#9b59b6', '#f39c12', '#1abc9c'];
    const color = colors[editor.availableTags.length % colors.length];

    // Add to available tags
    const newRef = { name: refName, color: color };
    editor.availableTags.push(newRef);

    // Apply the tag
    taggedEditorApplyTag(editorId, refName, color);

    // If we have a vision ID, save the reference to the backend
    if (editor.visionId) {
        fetch(`/vision/htmx/reference-create/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRFToken': getCsrfToken(),
            },
            body: `vision_id=${editor.visionId}&name=${encodeURIComponent(refName)}&color=${encodeURIComponent(color)}`,
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Reference created:', data);
            // Trigger refresh of references list
            document.body.dispatchEvent(new CustomEvent('referencesUpdated'));
        })
        .catch(err => {
            console.error('Failed to save reference:', err);
            alert('Failed to create reference: ' + err.message);
        });
    }
}

/**
 * Get CSRF token from hidden input or cookie
 */
function getCsrfToken() {
    // First try hidden input (most reliable in forms)
    const input = document.querySelector('[name=csrfmiddlewaretoken]');
    if (input) return input.value;

    // Fallback to cookie
    const cookie = document.cookie.split(';').find(c => c.trim().startsWith('csrftoken='));
    return cookie ? cookie.split('=')[1] : '';
}

/**
 * Get the plain text content of the editor
 */
function getEditorText(editor) {
    // Use stored text to avoid issues with rendered HTML
    return editor.text || '';
}

/**
 * Render the content with tag annotations
 */
function renderTaggedContent(editor) {
    const text = getEditorText(editor);
    const tags = editor.tags;

    if (tags.length === 0) {
        editor.content.innerHTML = escapeHtml(text) || '';
        // Still call positionTagLabels to reset line-height
        positionTagLabels(editor);
        return;
    }

    // Sort tags by start position, then by length (longer first for nesting)
    const sortedTags = [...tags].sort((a, b) => {
        if (a.start !== b.start) return a.start - b.start;
        return (b.end - b.start) - (a.end - a.start);
    });

    // Build the HTML with nested spans
    let result = '';
    let pos = 0;

    // Create events for tag boundaries
    const events = [];
    sortedTags.forEach((tag, idx) => {
        events.push({ pos: tag.start, type: 'open', tag, idx });
        events.push({ pos: tag.end, type: 'close', tag, idx });
    });
    events.sort((a, b) => {
        if (a.pos !== b.pos) return a.pos - b.pos;
        if (a.type !== b.type) return a.type === 'close' ? -1 : 1;
        return 0;
    });

    for (const event of events) {
        if (event.pos > pos) {
            result += escapeHtml(text.substring(pos, event.pos));
            pos = event.pos;
        }

        if (event.type === 'open') {
            const tag = event.tag;
            const color = tag.color || '#3498db';
            // Container for the tag - lines will be added dynamically by JS
            result += `<span class="tagged-text" data-tag="${escapeHtml(tag.tag)}" data-tag-id="${tag.id}" style="--tag-color: ${color};">`;
        } else {
            // Close the span - all visual elements will be added by positionTagLabels
            result += '</span>';
        }
    }

    if (pos < text.length) {
        result += escapeHtml(text.substring(pos));
    }

    editor.content.innerHTML = result || '';

    // Position tag labels (for multi-line support)
    positionTagLabels(editor);
}

/**
 * Position tag labels and lines for multi-line support
 * Nested tags are drawn on separate lines - inner tags closest to text, outer tags below
 */
function positionTagLabels(editor) {
    // Remove any existing visual overlay
    let overlay = editor.content.querySelector('.tag-overlay');
    if (overlay) {
        overlay.remove();
    }

    // Create overlay container for all tag visuals
    overlay = document.createElement('div');
    overlay.className = 'tag-overlay';
    overlay.style.cssText = `
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        pointer-events: none;
        z-index: 1;
    `;

    const taggedSpans = Array.from(editor.content.querySelectorAll('.tagged-text'));

    // Calculate nesting level for each tag
    // A tag's nesting level = how many other tags it completely contains
    // Outer tags have higher nesting levels and are drawn further from text
    const tagNestingLevels = new Map();

    taggedSpans.forEach(span => {
        const tagId = span.dataset.tagId;
        const tag = editor.tags.find(t => t.id === tagId);
        if (!tag) return;

        let nestingLevel = 0;
        editor.tags.forEach(otherTag => {
            if (otherTag.id !== tagId) {
                // Check if this tag completely contains the other tag
                if (tag.start <= otherTag.start && tag.end >= otherTag.end) {
                    nestingLevel++;
                }
            }
        });
        tagNestingLevels.set(tagId, nestingLevel);
    });

    const baseBracketHeight = 5;
    const nestingOffset = 12; // Additional height per nesting level (increased for visibility)
    const baseLineHeight = 1.5; // From CSS
    const fontSize = 14; // From CSS
    const labelHeight = 10; // Space for the label text

    // Find maximum nesting level to set consistent line-height for entire editor
    let maxNestingLevel = 0;
    tagNestingLevels.forEach(level => {
        if (level > maxNestingLevel) maxNestingLevel = level;
    });

    // Set line-height based on whether there are tags
    if (taggedSpans.length > 0) {
        // Use max nesting level to set line-height for entire editor
        // This ensures all lines have consistent spacing when tags wrap across lines
        const maxBracketHeight = baseBracketHeight + (maxNestingLevel * nestingOffset);
        // Extra space: bracket height + label height + padding
        const extraSpace = maxBracketHeight + labelHeight + 4;
        const newLineHeight = (baseLineHeight * fontSize) + extraSpace;
        editor.content.style.lineHeight = `${newLineHeight}px`;
    } else {
        // Remove line-height override when no tags
        editor.content.style.removeProperty('line-height');
    }

    // Force reflow before calculating positions
    editor.content.offsetHeight;

    // Get content rect after line-height change
    const contentRect = editor.content.getBoundingClientRect();

    // Collect all bracket and label data first, then render in two passes
    // This ensures all labels are drawn on top of all bracket lines
    const labelsToRender = [];

    // First pass: Draw all brackets
    taggedSpans.forEach(span => {
        const tagName = span.dataset.tag;
        const tagId = span.dataset.tagId;
        const color = getComputedStyle(span).getPropertyValue('--tag-color').trim() || '#3498db';
        const nestingLevel = tagNestingLevels.get(tagId) || 0;

        // Get text content rects using Range for accurate multi-line detection
        const range = document.createRange();
        const textNodes = [];
        const walker = document.createTreeWalker(span, NodeFilter.SHOW_TEXT, null, false);
        let node;
        while (node = walker.nextNode()) {
            textNodes.push(node);
        }

        let rects;
        if (textNodes.length > 0) {
            range.setStart(textNodes[0], 0);
            range.setEnd(textNodes[textNodes.length - 1], textNodes[textNodes.length - 1].length);
            rects = Array.from(range.getClientRects());
        } else {
            rects = Array.from(span.getClientRects());
        }

        if (rects.length === 0) return;

        // Find the longest rect (widest line segment)
        let longestRect = rects[0];
        let longestRectIndex = 0;
        for (let i = 1; i < rects.length; i++) {
            if (rects[i].width > longestRect.width) {
                longestRect = rects[i];
                longestRectIndex = i;
            }
        }

        // Total height increases with nesting level
        const totalBracketHeight = baseBracketHeight + (nestingLevel * nestingOffset);

        // Create bracket for each line segment
        rects.forEach((rect, index) => {
            const isFirst = index === 0;
            const isLast = index === rects.length - 1;

            const segment = document.createElement('div');
            segment.className = 'tag-line-segment';
            segment.dataset.tagId = tagId;

            // Position relative to the content container
            const left = rect.left - contentRect.left;
            const top = rect.bottom - contentRect.top;

            segment.style.cssText = `
                position: absolute;
                pointer-events: none;
                left: ${left}px;
                top: ${top}px;
                width: ${rect.width}px;
                height: ${totalBracketHeight}px;
            `;

            // Left vertical line - only on first segment
            if (isFirst) {
                const leftLine = document.createElement('span');
                leftLine.style.cssText = `
                    position: absolute;
                    left: 0;
                    top: 0;
                    width: 1px;
                    height: 100%;
                    background-color: ${color};
                `;
                segment.appendChild(leftLine);
            }

            // Right vertical line - only on last segment
            if (isLast) {
                const rightLine = document.createElement('span');
                rightLine.style.cssText = `
                    position: absolute;
                    right: 0;
                    top: 0;
                    width: 1px;
                    height: 100%;
                    background-color: ${color};
                `;
                segment.appendChild(rightLine);
            }

            // Bottom horizontal line
            const bottomLine = document.createElement('span');
            bottomLine.style.cssText = `
                position: absolute;
                left: 0;
                right: 0;
                bottom: 0;
                height: 1px;
                background-color: ${color};
            `;
            segment.appendChild(bottomLine);

            overlay.appendChild(segment);

            // Store label data for second pass (only for longest segment)
            if (index === longestRectIndex) {
                labelsToRender.push({
                    tagName,
                    color,
                    left: left + (rect.width / 2),
                    top: top + totalBracketHeight,
                    maxWidth: Math.max(rect.width - 10, 10)
                });
            }
        });
    });

    // Second pass: Draw all labels on top of all brackets
    labelsToRender.forEach(labelData => {
        const label = document.createElement('span');
        label.className = 'tag-label';
        label.textContent = labelData.tagName;
        label.style.cssText = `
            position: absolute;
            left: ${labelData.left}px;
            top: ${labelData.top}px;
            transform: translate(-50%, -50%);
            display: inline-block;
            height: auto;
            font-size: 7px;
            line-height: 7px;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            color: ${labelData.color};
            text-transform: lowercase;
            letter-spacing: 0.2px;
            font-weight: 500;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            max-width: ${labelData.maxWidth}px;
            background-color: #1a1a2e;
            padding: 1px 2px;
            box-sizing: content-box;
        `;
        overlay.appendChild(label);
    });

    // Insert overlay as first child of content
    editor.content.insertBefore(overlay, editor.content.firstChild);
}

/**
 * Apply a tag to the current selection
 */
function taggedEditorApplyTag(editorId, tagName, tagColor) {
    const editor = window.taggedEditors[editorId];
    if (!editor) return;

    const selection = window.getSelection();
    if (!selection || selection.isCollapsed) {
        return;
    }

    if (!editor.content.contains(selection.anchorNode) ||
        !editor.content.contains(selection.focusNode)) {
        return;
    }

    // Sync editor.text with current DOM before calculating positions
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = editor.content.innerHTML;
    // Remove overlay and any tag visual elements to get clean text
    tempDiv.querySelectorAll('.tag-overlay, .tag-end-marker, .tag-bottom-line, .tag-label').forEach(el => el.remove());
    editor.text = tempDiv.innerText || tempDiv.textContent || '';

    const range = getSelectionTextRange(editor);
    if (range.start === range.end) return;

    // Check if selection crosses any existing tag boundaries
    const crossesBoundary = editor.tags.some(existingTag => {
        const newStart = range.start;
        const newEnd = range.end;
        const tagStart = existingTag.start;
        const tagEnd = existingTag.end;

        // Valid positions:
        // 1. Completely outside: newEnd <= tagStart || newStart >= tagEnd
        // 2. Completely inside: newStart >= tagStart && newEnd <= tagEnd
        // 3. Completely contains: newStart <= tagStart && newEnd >= tagEnd

        const completelyOutside = newEnd <= tagStart || newStart >= tagEnd;
        const completelyInside = newStart >= tagStart && newEnd <= tagEnd;
        const completelyContains = newStart <= tagStart && newEnd >= tagEnd;

        // If none of these, it crosses a boundary
        return !(completelyOutside || completelyInside || completelyContains);
    });

    if (crossesBoundary) {
        // Show error feedback - flash the editor border red briefly
        editor.container.style.outline = '2px solid #e74c3c';
        setTimeout(() => {
            editor.container.style.outline = '';
        }, 300);
        return;
    }

    const newTag = {
        id: 'tag-' + Date.now(),
        start: range.start,
        end: range.end,
        tag: tagName,
        color: tagColor,
    };

    editor.tags.push(newTag);
    renderTaggedContent(editor);
    saveEditorState(editor);

    // Clear selection
    selection.removeAllRanges();
}

/**
 * Remove tag from current selection or cursor position
 */
function taggedEditorRemoveTag(editorId) {
    const editor = window.taggedEditors[editorId];
    if (!editor) return;

    const selection = window.getSelection();
    if (!selection || selection.isCollapsed) {
        const range = getSelectionTextRange(editor);
        const pos = range.start;
        const tagsAtPos = editor.tags.filter(t => t.start <= pos && t.end >= pos);
        if (tagsAtPos.length > 0) {
            const tagToRemove = tagsAtPos.reduce((a, b) =>
                (b.end - b.start) < (a.end - a.start) ? b : a
            );
            editor.tags = editor.tags.filter(t => t.id !== tagToRemove.id);
        }
    } else {
        const range = getSelectionTextRange(editor);
        editor.tags = editor.tags.filter(t =>
            t.end <= range.start || t.start >= range.end
        );
    }

    renderTaggedContent(editor);
    saveEditorState(editor);
}

/**
 * Get the text position range of the current selection
 */
function getSelectionTextRange(editor) {
    const selection = window.getSelection();
    if (!selection || selection.rangeCount === 0) {
        return { start: 0, end: 0 };
    }

    const range = selection.getRangeAt(0);

    // Temporarily remove overlay to get accurate text positions
    // (overlay contains tag labels which would skew the text offset calculation)
    const overlay = editor.content.querySelector('.tag-overlay');
    if (overlay) {
        overlay.remove();
    }

    const preCaretRange = document.createRange();
    preCaretRange.selectNodeContents(editor.content);
    preCaretRange.setEnd(range.startContainer, range.startOffset);
    const start = preCaretRange.toString().length;
    preCaretRange.setEnd(range.endContainer, range.endOffset);
    const end = preCaretRange.toString().length;

    // Restore overlay
    if (overlay) {
        editor.content.insertBefore(overlay, editor.content.firstChild);
    }

    return { start, end };
}

/**
 * Update tag positions after text edit
 */
function updateTagPositions(editor) {
    const text = getEditorText(editor);
    const textLength = text.length;

    editor.tags = editor.tags.filter(tag => {
        return tag.start < textLength && tag.end <= textLength && tag.start < tag.end;
    });

    editor.tags.forEach(tag => {
        tag.start = Math.max(0, Math.min(tag.start, textLength));
        tag.end = Math.max(tag.start, Math.min(tag.end, textLength));
    });

    renderTaggedContent(editor);
}

/**
 * Save editor state to hidden input
 */
function saveEditorState(editor) {
    const state = {
        text: getEditorText(editor),
        tags: editor.tags,
    };
    editor.dataInput.value = JSON.stringify(state);

    editor.container.dispatchEvent(new CustomEvent('taggedEditorChange', {
        detail: state,
        bubbles: true,
    }));
}

/**
 * Get editor state
 */
function getTaggedEditorState(editorId) {
    const editor = window.taggedEditors[editorId];
    if (!editor) return null;
    return {
        text: getEditorText(editor),
        tags: editor.tags,
    };
}

/**
 * Set editor content and tags
 */
function setTaggedEditorContent(editorId, text, tags = []) {
    const editor = window.taggedEditors[editorId];
    if (!editor) return;
    editor.text = text;  // Store the text
    editor.tags = tags;
    renderTaggedContent(editor);
    saveEditorState(editor);
}

/**
 * Update available tags (references)
 */
function setTaggedEditorReferences(editorId, references) {
    const editor = window.taggedEditors[editorId];
    if (!editor) return;
    editor.availableTags = references;
}

/**
 * Escape HTML special characters
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Make functions globally available
window.initTaggedEditor = initTaggedEditor;
window.taggedEditorApplyTag = taggedEditorApplyTag;
window.taggedEditorApplyTagFromPopup = taggedEditorApplyTagFromPopup;
window.taggedEditorRemoveTag = taggedEditorRemoveTag;
window.taggedEditorRemoveTagById = taggedEditorRemoveTagById;
window.taggedEditorChangeTag = taggedEditorChangeTag;
window.taggedEditorClosePopup = taggedEditorClosePopup;
window.taggedEditorCreateNewReference = taggedEditorCreateNewReference;
window.getTaggedEditorState = getTaggedEditorState;
window.setTaggedEditorContent = setTaggedEditorContent;
window.setTaggedEditorReferences = setTaggedEditorReferences;
