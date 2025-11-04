# estimator/templatetags/dict_filters.py
from django import template

register = template.Library()

@register.filter(name='get')
def get(dictionary, key):
    """Return dictionary[key] or None"""
    return dictionary.get(key)