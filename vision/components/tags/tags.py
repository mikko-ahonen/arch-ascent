"""
Tags Component for Arch Ascent.

A reusable component for displaying and managing tags with two modes:
1. readonly - Display tags only
2. input - Allow adding/removing tags via typeahead
"""
from django_components import component
from django.http import HttpResponse
from django.template.loader import render_to_string


@component.register("tags")
class Tags(component.Component):
    template_name = "tags/tags.html"

    def get_context_data(self, tags=None, mode='readonly', field_name='tags', x_model=None, **kwargs):
        """
        Args:
            tags: List of tag names or objects with 'name' attribute
            mode: 'readonly' or 'input'
            field_name: Name of the hidden input field
            x_model: Alpine.js x-model variable for tag list
        """
        tag_list = []
        if tags:
            for tag in tags:
                if isinstance(tag, str):
                    tag_list.append(tag)
                elif hasattr(tag, 'name'):
                    tag_list.append(tag.name)

        return {
            'tags': tag_list,
            'tag_string': ','.join(tag_list),
            'mode': mode,
            'field_name': field_name,
            'x_model': x_model or 'tagList',
        }

    def post(self, request, *args, **kwargs):
        """Handle tag add/remove via HTMX."""
        field_name = request.POST.get('field_name', 'tags')
        current_tags = request.POST.get('current_tags', '')
        added_tag = request.POST.get('added_tag', '')
        removed_tag = request.POST.get('removed_tag', '')
        x_model = request.POST.get('x_model', 'tagList')

        # Parse current tags
        tag_list = [t.strip() for t in current_tags.split(',') if t.strip()]

        # Add or remove
        if added_tag and added_tag not in tag_list:
            tag_list.append(added_tag)
        if removed_tag and removed_tag in tag_list:
            tag_list.remove(removed_tag)

        context = self.get_context_data(
            tags=tag_list,
            mode='input',
            field_name=field_name,
            x_model=x_model,
        )
        html = render_to_string(self.template_name, context, request=request)
        return HttpResponse(html)

    class Media:
        css = ['tags/tags.css']
