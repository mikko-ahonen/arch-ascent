"""Template filters for the scope app."""
from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary using a variable key."""
    if dictionary is None:
        return None
    return dictionary.get(key, '')


@register.filter
def status_display(status):
    """Convert status code to display label."""
    if not status:
        return ''
    return status.replace('_', ' ').capitalize()
