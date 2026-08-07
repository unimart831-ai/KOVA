"""Wire ContentBlueprint into seeds and the Create Agent prompt."""

from __future__ import annotations

import logging

from apps.create.content.blueprints import (
    build_blueprint_from_asset,
    validate_blueprint,
)

logger = logging.getLogger(__name__)


def asset_for_product(product):
    """Return linked BusinessAsset, creating one if needed."""
    if product is None:
        return None
    if getattr(product, "business_asset_id", None):
        return product.business_asset
    from apps.commerce.products.business_assets import sync_asset_from_product

    return sync_asset_from_product(product)


def blueprint_dict_for_context(
    *,
    product=None,
    asset=None,
    platforms: list[str] | None = None,
    objective: str = "",
) -> dict:
    """Build a validated blueprint dict from a product or asset."""
    resolved = asset or asset_for_product(product)
    if not resolved:
        return {}

    blueprint = build_blueprint_from_asset(
        resolved,
        objective=objective,
        platforms=platforms or None,
    )
    data = blueprint.to_dict()
    ok, errors = validate_blueprint(data)
    if not ok:
        logger.warning("Blueprint validation failed: %s", errors)
        return {}
    return data


def attach_blueprint_to_seed(
    seed,
    *,
    product=None,
    asset=None,
    platforms: list[str] | None = None,
    objective: str = "",
) -> dict:
    """Persist blueprint on a ContentSeed. Returns the blueprint dict."""
    data = blueprint_dict_for_context(
        product=product or getattr(seed, "product", None),
        asset=asset,
        platforms=platforms or (seed.target_platforms or None),
        objective=objective,
    )
    if not data:
        return {}

    resolved = asset or asset_for_product(product or getattr(seed, "product", None))
    if resolved and resolved.asset_type == resolved.AssetType.SERVICE:
        from apps.create.content.service_templates import apply_service_template_to_blueprint, pick_service_template

        template_key = pick_service_template(resolved, seed=str(seed.id))
        data = apply_service_template_to_blueprint(data, template_key, resolved, seed.user)
    elif resolved and resolved.asset_type in (
        resolved.AssetType.PORTFOLIO,
        resolved.AssetType.CASE_STUDY,
        resolved.AssetType.TESTIMONIAL,
    ):
        from apps.create.content.professional_templates import (
            apply_professional_template_to_blueprint,
            pick_professional_template,
        )

        template_key = pick_professional_template(resolved, seed=str(seed.id))
        data = apply_professional_template_to_blueprint(data, template_key, resolved, seed.user)
    elif getattr(seed.user.profile, "business_model", "") == "professional":
        from apps.create.content.professional_templates import (
            apply_professional_template_to_blueprint,
            pick_professional_template,
        )

        if resolved:
            template_key = pick_professional_template(resolved, seed=str(seed.id))
            data = apply_professional_template_to_blueprint(data, template_key, resolved, seed.user)

    seed.blueprint = data
    seed.save(update_fields=["blueprint", "updated_at"])
    return data


def blueprint_prompt_section(blueprint: dict) -> str:
    """Format blueprint as Create Agent instructions."""
    if not blueprint:
        return ""

    lines = [
        "### CONTENT BLUEPRINT (follow this structure)",
        f"- **Objective**: {blueprint.get('objective', 'sell')}",
        f"- **Asset**: {blueprint.get('title', '')} ({blueprint.get('asset_type', 'product')})",
    ]
    meta = blueprint.get("metadata") or {}
    if meta.get("price"):
        currency = meta.get("currency") or "KES"
        lines.append(f"- **Price**: {currency} {meta['price']}")

    lines.append("")
    lines.append("Generate one post per platform below. Fill each slot in `content_text` naturally:")
    for spec in blueprint.get("platforms") or []:
        platform = spec.get("platform", "")
        fmt = spec.get("format", "feed")
        slots = spec.get("slots") or {}
        slot_names = ", ".join(slots.keys()) or "body"
        lines.append(f"- **{platform.title()}** ({fmt}): use slots — {slot_names}")
        if platform == "instagram":
            lines.append("  → Combine hook + caption + hashtags + CTA in content_text.")
        elif platform == "tiktok":
            lines.append("  → Lead with hook; mention on-screen text in reasoning.")
        elif platform in ("facebook", "linkedin"):
            lines.append("  → Use headline as first line; body follows; end with CTA.")

    lines.append("")
    lines.append(
        "Match post_format to the blueprint format (carousel for IG product, reel for tiktok, etc.)."
    )
    from apps.create.content.service_templates import service_template_prompt_lines

    template_lines = service_template_prompt_lines(blueprint)
    if template_lines:
        lines.append("")
        lines.append(template_lines)
    from apps.create.content.professional_templates import professional_template_prompt_lines

    pro_lines = professional_template_prompt_lines(blueprint)
    if pro_lines:
        lines.append("")
        lines.append(pro_lines)
    return "\n".join(lines)
