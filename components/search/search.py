from django_components import Component, register
from django.http import HttpRequest
from django.urls import path


@register("search")
class Search(Component):
    template_name = "search/search.html"

    def get_context_data(self, placeholder="Search...", items=None):
        return {
            "placeholder": placeholder,
            "items": items or [],
        }

    @staticmethod
    def htmx_search(request: HttpRequest):
        query = request.GET.get('q', '')
        items = ['Apple', 'Banana', 'Cherry', 'Date', 'Elderberry', 'Fig', 'Grape', 'Honeydew']
        results = [item for item in items if query.lower() in item.lower()] if query else []
        return SearchResults.render_to_response(
            kwargs={"results": results, "query": query},
            request=request
        )

    @classmethod
    def get_urls(cls):
        return [
            path('search/', cls.htmx_search, name='search_query'),
        ]


@register("search_results")
class SearchResults(Component):
    template_name = "search/search_results.html"

    def get_context_data(self, results=None, query=""):
        return {
            "results": results or [],
            "query": query,
        }
