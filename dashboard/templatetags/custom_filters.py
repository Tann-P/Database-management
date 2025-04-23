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

@register.filter
def field_filter(items, args):
    """Filter a list of items by checking if an attribute equals a value
    
    Usage: {{ items|field_filter:"field_name:value" }}
    Example: {{ logs|field_filter:"action_type:registration" }}
    """
    if not args or ':' not in args:
        return items
    
    field, value = args.split(':')
    return [item for item in items if getattr(item, field, None) == value]