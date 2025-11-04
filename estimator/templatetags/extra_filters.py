# estimator/templatetags/extra_filters.py
from django import template
from decimal import Decimal

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter(name='abs')
def abs_filter(value):
    """Return absolute value of a number (Decimal-safe)."""
    try:
        return abs(Decimal(value))
    except (TypeError, ValueError, decimal.InvalidOperation):
        return value  # fallback

@register.filter
def subtract(value, arg):
    try:
        return Decimal(value) - Decimal(arg)
    except (TypeError, ValueError, decimal.InvalidOperation):
        return value