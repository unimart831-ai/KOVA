"""Showcase type labels for Studio post cards (professional / authority posts)."""

from __future__ import annotations

SHOWCASE_LABELS = {
    "portfolio": ("Portfolio", "purple"),
    "case_study": ("Case study", "indigo"),
    "testimonial": ("Testimonial", "emerald"),
    "product": ("Product", "kova"),
    "service": ("Service", "blue"),
    "thought_leadership": ("Thought leadership", "sky"),
    "authority": ("Authority", "sky"),
}


def _asset_type_from_seed(seed) -> str:
    if not seed:
        return ""
    blueprint = getattr(seed, "blueprint", None) or {}
    asset_type = (blueprint.get("asset_type") or "").strip()
    if asset_type:
        return asset_type
    product = getattr(seed, "product", None)
    if product:
        asset = getattr(product, "business_asset", None)
        if asset is None:
            try:
                from apps.commerce.products.models import BusinessAsset

                asset = BusinessAsset.objects.filter(product=product).only("asset_type").first()
            except Exception:
                asset = None
        if asset:
            return asset.asset_type
    return ""


def post_showcase_label(post) -> dict | None:
    """
    Return {text, tone} for a post card badge, or None if generic.
    tone is a Tailwind color family suffix (purple, indigo, …).
    """
    seed = getattr(post, "seed", None)
    asset_type = _asset_type_from_seed(seed)

    if not asset_type and seed:
        dna = getattr(post, "content_dna", None) or {}
        blueprint = dna.get("blueprint") or {}
        asset_type = (blueprint.get("asset_type") or "").strip()

    if not asset_type:
        profile = getattr(getattr(post, "user", None), "profile", None)
        if profile and getattr(profile, "business_model", "") == "professional":
            platform = post.platform or (
                post.social_account.platform if getattr(post, "social_account", None) else ""
            )
            if platform in ("linkedin", "facebook"):
                asset_type = "thought_leadership"

    if not asset_type or asset_type == "product":
        return None

    text, tone = SHOWCASE_LABELS.get(asset_type, (asset_type.replace("_", " ").title(), "gray"))
    return {"text": text, "tone": tone}


def summarize_showcase_types(posts) -> str:
    """One-line summary for batch-approve modal, e.g. '2 case studies · 1 portfolio'."""
    counts: dict[str, int] = {}
    for post in posts:
        label = post_showcase_label(post)
        if not label:
            continue
        key = label["text"]
        counts[key] = counts.get(key, 0) + 1
    if not counts:
        return ""
    parts = [f"{n} {name.lower()}{'s' if n != 1 else ''}" for name, n in sorted(counts.items(), key=lambda x: -x[1])]
    return " · ".join(parts)
