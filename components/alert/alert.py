from django_components import Component, register


@register("alert")
class Alert(Component):
    template_name = "alert/alert.html"

    def get_context_data(self, variant="info", dismissible=False, icon=""):
        icon_map = {
            "info": "bi-info-circle",
            "success": "bi-check-circle",
            "warning": "bi-exclamation-triangle",
            "danger": "bi-x-circle",
        }
        return {
            "variant": variant,
            "dismissible": dismissible,
            "icon": icon or icon_map.get(variant, "bi-info-circle"),
        }
