from django_components import Component, register


@register("card")
class Card(Component):
    template_name = "card/card.html"

    def get_context_data(self, title="", icon=""):
        return {
            "title": title,
            "icon": icon,
        }
