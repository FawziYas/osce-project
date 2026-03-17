"""
Input sanitization utilities — strip stored XSS from user-supplied plain-text.

All fields in this project are plain-text (names, descriptions, notes, comments,
scenarios, instructions). None are intended to contain HTML markup.
Stripping tags at write-time means malicious payloads never reach the database,
providing defence-in-depth alongside Django's template auto-escaping.

Usage in views::

    from core.utils.sanitize import strip_html, html_safe_json

    name = strip_html(request.POST.get('name', ''))
    payload = html_safe_json({'description': name})  # safe for |safe in <script>

Usage in DRF serializers::

    def validate_notes(self, value):
        return strip_html(value)
"""

import json
import re

# Matches any complete HTML tag, including multi-line or self-closing, e.g.
# <script>, </div>, <img src="x" onerror="...">, <!-- comment -->, <!DOCTYPE ...>
_HTML_TAG_RE = re.compile(r'<[^>]*>', re.DOTALL)

# Null bytes are invalid in all text fields and can bypass some sanitisers
_NULL_BYTE_RE = re.compile(r'\x00')


def strip_html(value: str) -> str:
    """
    Return *value* with all HTML tags and null bytes removed.

    Designed for plain-text fields — names, descriptions, comments, notes,
    scenario text, etc.  The function does NOT escape — Django templates
    auto-escape on rendering; stripping ensures nothing dangerous is ever stored.

    Non-string input is returned unchanged so callers need not special-case None.
    """
    if not isinstance(value, str):
        return value
    value = _NULL_BYTE_RE.sub('', value)
    value = _HTML_TAG_RE.sub('', value)
    return value


def html_safe_json(obj) -> str:
    """
    Return a JSON string that is safe for inline injection into an HTML
    ``<script>`` block (i.e.  safe to use with Django's ``|safe`` filter).

    Standard ``json.dumps`` does NOT escape ``<``, ``>`` or ``&``, so a value
    containing ``</script>`` would break out of the surrounding script tag.
    This function replaces those three characters with their Unicode escapes,
    which are interpreted identically by JavaScript engines but are inert inside
    an HTML parser.

    Example::

        context['items_json'] = html_safe_json(items_list)
        # In template: const items = {{ items_json|safe }};
    """
    serialized = json.dumps(obj, ensure_ascii=False)
    # Unicode-escape the three HTML-sensitive characters
    return (
        serialized
        .replace('&', r'\u0026')
        .replace('<', r'\u003c')
        .replace('>', r'\u003e')
    )
