from django_components import Component, register
from django.http import HttpRequest
from django.urls import path
from django.views.decorators.csrf import csrf_exempt


@register("counter")
class Counter(Component):
    template_name = "counter/counter.html"

    def get_context_data(self, count=0):
        return {"count": count}

    @staticmethod
    @csrf_exempt
    def htmx_increment(request: HttpRequest):
        count = int(request.POST.get('count', 0)) + 1
        return Counter.render_to_response(kwargs={"count": count}, request=request)

    @classmethod
    def get_urls(cls):
        return [
            path('counter/increment/', cls.htmx_increment, name='counter_increment'),
        ]
