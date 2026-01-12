"""
Modal Component for Arch Ascent.

Creates a Bootstrap modal container that can be targeted by HTMX requests.
Use hx-target="#dialog" and hx-get/hx-post to load content into the modal.
"""
from django_components import component


@component.register("modal")
class Modal(component.Component):
    template_name = "modal/modal.html"

    def get_context_data(self):
        return {}

    class Media:
        js = ['modal/modal.js']
        css = ['modal/modal.css']
