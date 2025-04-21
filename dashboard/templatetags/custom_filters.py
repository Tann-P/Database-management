from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Get an item from a dictionary by key.
    Usage: {{ dictionary|get_item:key }}
    """
    return dictionary.get(key, '')

@register.filter
def subtract_from(value, arg):
    """
    Subtract value from arg.
    Usage: {{ value|subtract_from:100 }}
    Returns: 100 - value
    """
    try:
        return arg - value
    except (ValueError, TypeError):
        return 0