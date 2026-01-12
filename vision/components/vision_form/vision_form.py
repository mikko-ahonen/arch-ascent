"""
Vision Form Component for Arch Ascent.

Modal form for creating and editing visions.
"""
from django_components import component
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.shortcuts import get_object_or_404
from vision.models import Vision


@component.register("vision_form")
class VisionForm(component.Component):
    template_name = "vision_form/vision_form.html"

    def get_context_data(self, vision=None, vision_id=None, **kwargs):
        if vision_id and not vision:
            vision = get_object_or_404(Vision, pk=vision_id)
        return {
            'vision': vision,
            'status_choices': Vision.STATUS_CHOICES,
        }

    def get(self, request, *args, **kwargs):
        """Handle GET request for form modal."""
        vision_id = request.GET.get('vision_id')
        context = self.get_context_data(vision_id=vision_id)
        html = render_to_string(self.template_name, context, request=request)
        return HttpResponse(html)

    def post(self, request, *args, **kwargs):
        """Create or update a vision."""
        vision_id = request.POST.get('vision_id')
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        status = request.POST.get('status', 'draft')

        if not name:
            return HttpResponse(
                '<div class="alert alert-danger">Name is required</div>',
                status=400
            )

        if vision_id:
            # Update existing
            vision = get_object_or_404(Vision, pk=vision_id)
            vision.name = name
            vision.description = description
            vision.status = status
            vision.save()
        else:
            # Create new
            vision = Vision.objects.create(
                name=name,
                description=description,
                status=status
            )

        # Return the updated vision card and trigger modal close
        from vision.components.vision_card.vision_card import VisionCard
        card_context = {'vision': vision}
        card_html = render_to_string(
            'vision_card/vision_card.html',
            card_context,
            request=request
        )

        response = HttpResponse(card_html)
        response['HX-Trigger'] = 'visionUpdated'
        return response
