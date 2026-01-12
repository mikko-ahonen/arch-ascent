"""
Vision List Component for Arch Ascent.

Displays a list of visions with HTMX support for CRUD operations.
"""
from django_components import component
from django.http import HttpResponse
from django.template.loader import render_to_string
from vision.models import Vision


@component.register("vision_list")
class VisionList(component.Component):
    template_name = "vision_list/vision_list.html"

    def get_context_data(self, status_filter=None, **kwargs):
        visions = Vision.objects.all()
        if status_filter:
            visions = visions.filter(status=status_filter)
        return {
            'visions': visions,
            'status_filter': status_filter,
        }

    def post(self, request, *args, **kwargs):
        """Create a new vision."""
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()

        if name:
            vision = Vision.objects.create(name=name, description=description)

        # Re-render the list
        context = self.get_context_data()
        html = render_to_string(self.template_name, context, request=request)
        return HttpResponse(html)
