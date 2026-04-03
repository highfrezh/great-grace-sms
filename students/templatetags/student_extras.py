from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Get item from dictionary by key in templates"""
    return dictionary.get(key)

@register.filter
def get_option(question, letter):
    """Get question option by letter (A, B, C, D)"""
    if letter == 'A':
        return question.option_a
    elif letter == 'B':
        return question.option_b
    elif letter == 'C':
        return question.option_c
    elif letter == 'D':
        return question.option_d
    return ''

@register.filter
def filter_by(queryset, filter_str):
    """Filter queryset by field:value (e.g., 'difficulty:EASY')"""
    if not filter_str or ':' not in filter_str:
        return queryset
    
    field, value = filter_str.split(':', 1)
    return queryset.filter(**{field: value})