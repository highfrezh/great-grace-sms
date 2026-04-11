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


@register.filter
def get_item(obj, key):
    """
    Get an item from a dictionary or form using a key.
    Usage: {{ form|get_item:field_name }}
    """
    try:
        if obj is None:
            return None
        return obj[key]
    except (KeyError, TypeError, IndexError):
        return None


@register.simple_tag
def get_form_field(form, prefix, student_id):
    """
    Get a specific field from a form using a prefix and student_id.
    Usage: {% get_form_field form 'ca1_' student.id %}
    """
    field_name = f"{prefix}{student_id}"
    try:
        if form is None:
            return None
        return form[field_name]
    except KeyError:
        return None
