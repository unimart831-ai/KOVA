from django import template

from apps.create.media.content_types import MediaPlan
from apps.create.media.labels import (
    carousel_backend_label,
    format_label,
    reel_backend_label,
    reel_compose_hint,
)

register = template.Library()


@register.filter
def reel_backend_label_filter(backend):
    return reel_backend_label(backend)


@register.filter
def reel_compose_hint_filter(backend):
    return reel_compose_hint(backend)


@register.filter
def carousel_backend_label_filter(backend):
    return carousel_backend_label(backend)


@register.filter
def media_format_label(fmt):
    return format_label(fmt)


@register.simple_tag
def post_reel_backend_label(post):
    backend = getattr(post, "reel_compose_backend", None) or ""
    return reel_backend_label(backend)


@register.simple_tag
def post_reel_compose_hint(post):
    backend = getattr(post, "reel_compose_backend", None) or ""
    return reel_compose_hint(backend)


@register.inclusion_tag("components/_media_format_badges.html", takes_context=False)
def media_plan_badges(media_plan):
    if isinstance(media_plan, MediaPlan):
        plan = media_plan
    elif isinstance(media_plan, dict):
        plan = MediaPlan.from_metadata(media_plan)
    else:
        plan = MediaPlan()
    return {
        "formats": [format_label(f.value) for f in plan.formats],
        "reel_label": reel_backend_label(plan.reel_backend.value),
        "carousel_label": carousel_backend_label(plan.carousel_backend.value),
        "has_plan": bool(plan.formats),
    }
