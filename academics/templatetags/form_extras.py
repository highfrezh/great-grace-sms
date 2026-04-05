from django import template

register = template.Library()


@register.filter
def widget_class_name(field):
    """Return the class name of a form field's widget"""
    return field.field.widget.__class__.__name__
