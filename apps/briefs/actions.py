"""Shared Daily Brief actions — web UI and WhatsApp reply-to-act."""

from __future__ import annotations

from apps.content.models import ContentSeed
from apps.platforms.models import SocialAccount


def create_seed_from_brief_idea(
    user,
    idea: str,
    *,
    context: str = "",
    platform_hint: str = "",
    action_type: str = "whatsapp",
) -> ContentSeed:
    """Turn a brief suggestion into a ContentSeed."""
    active_platforms = set(
        SocialAccount.objects.filter(user=user, is_active=True)
        .values_list("platform", flat=True)
    )
    if platform_hint:
        hint_platforms = [p.strip() for p in platform_hint.split(",") if p.strip()]
        target_platforms = [p for p in hint_platforms if p in active_platforms] or list(active_platforms)[:3]
    else:
        target_platforms = list(active_platforms)[:3]

    seed_idea = idea.strip()
    if context:
        seed_idea += f"\n\nContext: {context.strip()}"

    return ContentSeed.objects.create(
        user=user,
        idea=seed_idea,
        notes=f"Created from Daily Brief ({action_type})",
        target_platforms=target_platforms[:3],
    )
