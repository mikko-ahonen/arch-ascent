"""
Vision Card Component for Arch Ascent.

Displays a single vision as a card.
"""
from django_components import component
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from vision.models import Vision


@component.register("vision_card")
class VisionCard(component.Component):
    template_name = "vision_card/vision_card.html"

    def get_context_data(self, vision=None, vision_id=None, **kwargs):
        if vision_id and not vision:
            vision = get_object_or_404(Vision, pk=vision_id)
        return {
            'vision': vision,
        }

    def delete(self, request, *args, **kwargs):
        """Delete a vision."""
        vision_id = request.GET.get('vision_id') or request.POST.get('vision_id')
        if vision_id:
            Vision.objects.filter(pk=vision_id).delete()
        return HttpResponse('')  # Empty response to remove the card
