from django import template
from django.utils.safestring import mark_safe

from apps.insight.help.mermaid_utils import sanitize_mermaid

register = template.Library()


@register.filter
def mermaid_diagram(value: str) -> str:
    """Sanitize and mark safe so Mermaid source is not HTML-entity escaped."""
    if not value:
        return ""
    return mark_safe(sanitize_mermaid(value))
