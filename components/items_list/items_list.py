from django_components import Component, register
from django.http import HttpRequest
from django.urls import path


@register("items_list")
class ItemsList(Component):
    template_name = "items_list/items_list.html"

    def get_context_data(self, items=None, next_page=2):
        if items is None:
            items = [f'Item {i}' for i in range(1, 6)]
        return {
            "items": items,
            "next_page": next_page,
        }

    @staticmethod
    def htmx_load_more(request: HttpRequest):
        page = int(request.GET.get('page', 2))
        items = [f'Item {i}' for i in range((page - 1) * 5 + 1, page * 5 + 1)]
        return ItemsPartial.render_to_response(
            kwargs={"items": items, "next_page": page + 1},
            request=request
        )

    @classmethod
    def get_urls(cls):
        return [
            path('items/load-more/', cls.htmx_load_more, name='items_load_more'),
        ]


@register("items_partial")
class ItemsPartial(Component):
    template_name = "items_list/items_partial.html"

    def get_context_data(self, items=None, next_page=2):
        return {
            "items": items or [],
            "next_page": next_page,
        }
