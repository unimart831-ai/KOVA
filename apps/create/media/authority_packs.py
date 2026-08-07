"""Authority content packs — FAQ / myth / tip from Brand DNA."""

from __future__ import annotations

from apps.create.media.brand_dna import resolve_brand_dna


def build_authority_pack(user, *, pack_type: str = "faq") -> list[dict]:
    """Generate authority seed ideas for consultants."""
    dna = resolve_brand_dna(user)
    industry = dna.industry or "your industry"
    brand = dna.brand_name or "your brand"
    if pack_type == "myth":
        return [
            {"title": f"Myth: {industry} is too crowded", "angle": "Debunk the myth with proof"},
            {"title": "What clients get wrong", "angle": "Educate with a contrarian take"},
        ]
    if pack_type == "tips":
        return [
            {"title": f"3 mistakes in {industry}", "angle": "Actionable tips"},
            {"title": f"How {brand} approaches results", "angle": "Authority positioning"},
        ]
    return [
        {"title": f"FAQ: How to choose in {industry}", "angle": "Answer the #1 buyer question"},
        {"title": "Before you buy — read this", "angle": "Trust-building FAQ carousel"},
    ]


def is_authority_business(user) -> bool:
    """Consultants, coaches, and agencies benefit from weekly authority seeds."""
    profile = getattr(user, "profile", None)
    if not profile:
        return False
    if getattr(profile, "business_model", "") == "professional":
        return True
    industry = (getattr(profile, "industry", "") or "").lower()
    return industry in {"consulting", "coaching", "legal", "finance", "education"}


def weekly_authority_pack_type(user) -> str:
    """Rotate FAQ / myth / tips packs week over week."""
    from django.utils import timezone

    week = timezone.localdate().isocalendar()[1]
    return ("faq", "myth", "tips")[week % 3]


def authority_seed_ideas_for_user(user, *, limit: int = 2) -> list[dict]:
    if not is_authority_business(user):
        return []
    pack_type = weekly_authority_pack_type(user)
    return build_authority_pack(user, pack_type=pack_type)[:limit]
