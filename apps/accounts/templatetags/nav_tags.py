from django import template

register = template.Library()


@register.filter
def dedupe_messages(messages):
    """Show each distinct message text once (OAuth failures sometimes duplicate)."""
    if not messages:
        return []
    seen = set()
    unique = []
    for msg in messages:
        text = str(msg)
        if text not in seen:
            seen.add(text)
            unique.append(msg)
    return unique


@register.simple_tag
def nav_active(request_path, *patterns):
    """Return True if request_path matches any pattern. Prefix a pattern with
    ``!`` to treat it as an exclusion — all exclusions must pass for the tag
    to return True.

    Usage::

        {% nav_active request.path '/analytics/' '!/analytics/revenue' '!/analytics/pixel' as insights_active %}
    """
    includes = [p for p in patterns if not p.startswith("!")]
    excludes = [p[1:] for p in patterns if p.startswith("!")]
    matched = any(p in request_path for p in includes)
    excluded = any(p in request_path for p in excludes)
    return matched and not excluded
