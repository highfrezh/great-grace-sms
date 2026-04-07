from django import template

register = template.Library()


@register.filter
def dict_get(dictionary, key):
    """
    Safely get a value from a dictionary in a template.
    Usage: {{ dict|dict_get:key_value }}
    """
    if isinstance(dictionary, dict):
        return dictionary.get(key, '')
    return ''


@register.filter
def get_option(question, letter):
    """
    Get the option text for a given question and letter.
    Usage: {{ question|get_option:"A" }}
    """
    return getattr(question, f'option_{letter.lower()}', '')
