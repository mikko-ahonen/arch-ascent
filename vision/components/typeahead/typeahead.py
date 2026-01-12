"""
Typeahead Component for Arch Ascent.

A reusable typeahead/autocomplete component using HTMX.
Supports searching for tags and creating new ones.
"""
from django_components import component
from django.http import HttpResponse
from django.template.loader import render_to_string
from taggit.models import Tag


@component.register("typeahead")
class Typeahead(component.Component):
    template_name = "typeahead/typeahead.html"

    def get_context_data(self, target="tags", placeholder="Search...", x_model=None, **kwargs):
        """
        Args:
            target: Type of search (tags, projects, etc.)
            placeholder: Placeholder text for input
            x_model: Alpine.js x-model variable name for two-way binding
        """
        return {
            "target": target,
            "placeholder": placeholder,
            "x_model": x_model or "selected",
        }

    class Media:
        css = ['typeahead/typeahead.css']


@component.register("typeahead_results")
class TypeaheadResults(component.Component):
    """Renders typeahead search results."""
    template_name = "typeahead/typeahead_results.html"

    def get_context_data(self, results=None, target="tags", **kwargs):
        return {
            "results": results or [],
            "target": target,
        }

    def post(self, request, *args, **kwargs):
        """Handle search requests."""
        q = request.POST.get('q', '').strip()
        target = request.POST.get('target', 'tags')

        results = []
        if target == 'tags':
            tags = Tag.objects.filter(name__icontains=q)[:10] if q else Tag.objects.all()[:10]
            results = [{'id': t.id, 'name': t.name, 'type': 'tag'} for t in tags]

        context = self.get_context_data(results=results, target=target)
        html = render_to_string(self.template_name, context, request=request)
        return HttpResponse(html)
