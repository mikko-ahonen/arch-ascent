from django_components import Component, register
from django.http import HttpRequest
from django.urls import path
import random


@register("quote")
class Quote(Component):
    template_name = "quote/quote.html"

    QUOTES = [
        ("The only way to do great work is to love what you do.", "Steve Jobs"),
        ("Innovation distinguishes between a leader and a follower.", "Steve Jobs"),
        ("Stay hungry, stay foolish.", "Steve Jobs"),
        ("Code is like humor. When you have to explain it, it's bad.", "Cory House"),
        ("First, solve the problem. Then, write the code.", "John Johnson"),
        ("Simplicity is the soul of efficiency.", "Austin Freeman"),
        ("Make it work, make it right, make it fast.", "Kent Beck"),
    ]

    def get_context_data(self, quote="", author="", show_button=True):
        return {
            "quote": quote,
            "author": author,
            "show_button": show_button,
        }

    @staticmethod
    def htmx_random(request: HttpRequest):
        quote, author = random.choice(Quote.QUOTES)
        return Quote.render_to_response(
            kwargs={"quote": quote, "author": author, "show_button": True},
            request=request
        )

    @classmethod
    def get_urls(cls):
        return [
            path('quote/random/', cls.htmx_random, name='quote_random'),
        ]
