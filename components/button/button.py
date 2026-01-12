from django_components import Component, register


@register("button")
class Button(Component):
    template_name = "button/button.html"

    def get_context_data(self, variant="primary", size="", icon="", href="", **attrs):
        return {
            "variant": variant,
            "size": size,
            "icon": icon,
            "href": href,
            "attrs": attrs,
        }
