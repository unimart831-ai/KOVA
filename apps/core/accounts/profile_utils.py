"""Ensure every User has a UserProfile (backfill for legacy / failed signal rows)."""

from __future__ import annotations

from apps.core.accounts.models import User, UserProfile


def _unique_page_slug(base: str) -> str:
    from django.utils.text import slugify

    slug = slugify(base)[:60] or "page"
    candidate = slug
    n = 1
    while UserProfile.objects.filter(page_slug=candidate).exists():
        candidate = f"{slug}-{n}"
        n += 1
    return candidate


def ensure_user_profile(user: User) -> UserProfile:
    """Return the user's profile, creating one if missing."""
    if not user or not user.pk:
        raise ValueError("ensure_user_profile requires a saved User")

    existing = UserProfile.objects.filter(user_id=user.pk).first()
    if existing:
        return existing

    base = (user.username or user.email or "user").split("@")[0]
    return UserProfile.objects.create(
        user=user,
        page_slug=_unique_page_slug(base),
    )
