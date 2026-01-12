"""
Tagged Editor Component for Arch Ascent.

A text editor that allows tagging/annotating portions of text with
visual underlines and tag labels.
"""
from django_components import component


@component.register("tagged_editor")
class TaggedEditor(component.Component):
    template_name = "tagged_editor/tagged_editor.html"

    class Media:
        css = ['tagged_editor/tagged_editor.css']
        js = ['tagged_editor/tagged_editor.js']

    def get_context_data(self,
                         editor_id="tagged-editor",
                         content="",
                         tags=None,
                         placeholder="Enter text...",
                         readonly=False,
                         available_tags=None,
                         vision_id=None,
                         **kwargs):
        """
        Args:
            editor_id: Unique ID for the editor instance
            content: Initial text content
            tags: List of tag annotations, each with:
                  {start: int, end: int, tag: str, color: str (optional)}
            placeholder: Placeholder text when empty
            readonly: If True, disable editing
            available_tags: List of available tag types for the toolbar
                           [{name: str, color: str, description: str}]
            vision_id: Vision ID for creating new references
        """
        import json as json_module

        if tags is None:
            tags = []
        if available_tags is None:
            available_tags = []

        # Convert Reference queryset to list of dicts if needed
        tags_list = []
        for tag in available_tags:
            if hasattr(tag, 'name'):
                # It's a Reference model instance
                tags_list.append({
                    'name': tag.name,
                    'color': '#3498db',  # Default color for references
                    'description': tag.description or '',
                })
            else:
                tags_list.append(tag)

        return {
            'editor_id': editor_id,
            'content': content,
            'tags': json_module.dumps(tags) if not isinstance(tags, str) else tags,
            'placeholder': placeholder,
            'readonly': readonly,
            'available_tags': tags_list,
            'available_tags_json': json_module.dumps(tags_list),
            'vision_id': vision_id,
        }
