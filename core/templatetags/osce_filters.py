"""
Custom template tags and filters for the OSCE project.
"""
from datetime import datetime, timezone
from django import template

register = template.Library()


@register.filter(name='strftime')
def strftime_filter(value, fmt='%Y-%m-%d %H:%M'):
    """
    Format a Unix integer timestamp as a date string.

    Usage: {{ score.completed_at|strftime:"%Y-%m-%d %H:%M" }}
    """
    if value is None:
        return ''
    try:
        ts = int(value)
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        return dt.strftime(fmt)
    except (ValueError, TypeError, OSError):
        return str(value)


@register.filter(name='to_letter')
def to_letter_filter(value):
    """
    Convert a 1-based integer to a letter (1->A, 2->B, ...).

    Usage: {{ option.option_number|to_letter }}
    """
    try:
        return chr(64 + int(value))
    except (ValueError, TypeError):
        return str(value)


@register.filter(name='get_item')
def get_item_filter(dictionary, key):
    """
    Get an item from a dictionary using a key.

    Usage: {{ data.scores|get_item:station.id }}
    """
    if dictionary is None:
        return None
    try:
        return dictionary.get(key) if isinstance(dictionary, dict) else None
    except (KeyError, TypeError):
        return None
