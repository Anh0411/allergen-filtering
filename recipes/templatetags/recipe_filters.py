from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Get item from dictionary by key or list by index"""
    if hasattr(dictionary, 'get'):
        # It's a dictionary
        return dictionary.get(key, False)
    elif hasattr(dictionary, '__getitem__'):
        # It's a list or similar sequence
        try:
            if isinstance(key, str) and key.isdigit():
                return dictionary[int(key)]
            else:
                return dictionary[key]
        except (IndexError, KeyError, TypeError):
            return False
    return False 