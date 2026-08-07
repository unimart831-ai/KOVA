"""
Campaign Visual Brief — structured input for Photoroom and visual production.

All Photoroom jobs must originate from this brief, not ad-hoc prompts.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from apps.create.media.brand_dna import BrandDNA, resolve_brand_dna
from apps.create.media.orchestrator import MAX_PHOTOROOM_SCENES_PER_CAMPAIGN, cap_photoroom_scenes_for_plan

DEFAULT_SCENE_ROLES = (
    "studio",
    "lifestyle",
    "feature",
    "offer",
    "cta",
)

SCENE_ROLE_ALIASES = {
    "studio": "studio",
    "studio_white": "studio",
    "white_studio": "studio",
    "lifestyle": "lifestyle",
    "ai_scene": "lifestyle",
    "feature": "feature",
    "feature_highlight": "feature",
    "offer": "offer",
    "promo": "offer",
    "promo_frame": "offer",
    "cta": "cta",
}


@dataclass
class CampaignVisualBrief:
    objective: str = "sales"
    audience: str = ""
    visual_style: str = "photography"
    business_type: str = "product"
    brand_dna: dict[str, Any] = field(default_factory=dict)
    asset_refs: list[str] = field(default_factory=list)
    scenes: list[str] = field(default_factory=list)
    platform_requirements: list[str] = field(default_factory=list)
    campaign_id: str = ""
    seed_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict | None) -> CampaignVisualBrief | None:
        if not data or not isinstance(data, dict):
            return None
        return cls(
            objective=data.get("objective", "sales"),
            audience=data.get("audience", ""),
            visual_style=data.get("visual_style", "photography"),
            business_type=data.get("business_type", "product"),
            brand_dna=dict(data.get("brand_dna") or {}),
            asset_refs=list(data.get("asset_refs") or []),
            scenes=list(data.get("scenes") or []),
            platform_requirements=list(data.get("platform_requirements") or []),
            campaign_id=str(data.get("campaign_id") or ""),
            seed_id=str(data.get("seed_id") or ""),
        )

    def capped_scenes(self, user) -> list[str]:
        """Enforce MAX_SCENES_PER_CAMPAIGN — no campaign may exceed the cap."""
        raw = self.scenes or list(DEFAULT_SCENE_ROLES)
        normalized = []
        for s in raw:
            key = SCENE_ROLE_ALIASES.get(str(s).lower().replace(" ", "_"), str(s).lower())
            if key not in normalized:
                normalized.append(key)
        cap = cap_photoroom_scenes_for_plan(user, MAX_PHOTOROOM_SCENES_PER_CAMPAIGN)
        return normalized[:cap]

    def photoroom_scene_prompt(self, scene_role: str, *, product_name: str = "") -> str:
        """Structured scene instruction for Photoroom — derived from brief, not ad-hoc."""
        style = self.visual_style.replace("_", " ")
        audience = self.audience or "your customers"
        name = product_name or "the product"
        role = SCENE_ROLE_ALIASES.get(scene_role.lower(), scene_role.lower())

        prompts = {
            "studio": (
                f"Clean studio product shot of {name}, {style} aesthetic, "
                f"premium lighting, no text, for {audience}"
            ),
            "lifestyle": (
                f"Lifestyle scene featuring {name} in natural use context, "
                f"{style}, aspirational for {audience}"
            ),
            "feature": (
                f"Close-up feature highlight of {name}, detail-focused, "
                f"{style}, compelling for {audience}"
            ),
            "offer": (
                f"Promotional visual for {name}, {self.objective} objective, "
                f"urgency and value, {style}"
            ),
            "cta": (
                f"Call-to-action hero frame for {name}, bold composition, "
                f"{style}, conversion-focused"
            ),
        }
        return prompts.get(role, prompts["studio"])


def build_campaign_visual_brief(seed, campaign=None, *, user=None) -> CampaignVisualBrief:
    """Build visual brief from Campaign → Seed → Asset → Brand DNA chain."""
    user = user or seed.user
    profile = getattr(user, "profile", None)
    dna: BrandDNA = resolve_brand_dna(user, profile)

    blueprint = getattr(seed, "blueprint", None) or {}
    objective = (
        getattr(campaign, "objective", None)
        or blueprint.get("objective")
        or "sales"
    )
    if isinstance(objective, str):
        objective = objective.replace("sell", "sales").replace("announce", "awareness")

    audience = (getattr(profile, "target_audience", None) or "").strip()
    if not audience and blueprint.get("metadata", {}).get("audience"):
        audience = str(blueprint["metadata"]["audience"])

    business_type = dna.business_model or "product"
    if profile and profile.industry:
        business_type = profile.industry

    asset_refs: list[str] = []
    product = getattr(seed, "product", None)
    if product:
        asset_refs = list(getattr(product, "all_image_urls", None) or [])[:5]
    elif campaign and getattr(campaign, "business_asset_id", None):
        try:
            asset = campaign.business_asset
            asset_refs = list((asset.metadata or {}).get("image_urls") or [])[:5]
        except Exception:
            pass

    platforms = list(seed.target_platforms or [])
    if not platforms:
        from apps.core.platforms.models import SocialAccount

        platforms = list(
            SocialAccount.objects.filter(user=user, is_active=True).values_list("platform", flat=True)
        )

    brief = CampaignVisualBrief(
        objective=str(objective),
        audience=audience or "local customers",
        visual_style=dna.visual_style or dna.image_style or "photography",
        business_type=str(business_type),
        brand_dna=dna.to_dict(),
        asset_refs=asset_refs,
        scenes=list(DEFAULT_SCENE_ROLES),
        platform_requirements=platforms,
        campaign_id=str(campaign.pk) if campaign else "",
        seed_id=str(seed.pk),
    )
    brief.scenes = brief.capped_scenes(user)
    return brief


def persist_visual_brief(campaign, brief: CampaignVisualBrief) -> None:
    meta = dict(campaign.proposal_meta or {})
    meta["visual_brief"] = brief.to_dict()
    campaign.proposal_meta = meta
    campaign.save(update_fields=["proposal_meta", "updated_at"])


def get_visual_brief_for_seed(seed) -> CampaignVisualBrief | None:
    campaign = getattr(seed, "marketing_campaign", None)
    if campaign:
        data = (campaign.proposal_meta or {}).get("visual_brief")
        brief = CampaignVisualBrief.from_dict(data)
        if brief:
            return brief
    blueprint = getattr(seed, "blueprint", None) or {}
    return CampaignVisualBrief.from_dict(blueprint.get("visual_brief"))


def get_visual_brief_for_product(product) -> CampaignVisualBrief | None:
    """Latest campaign visual brief for a product-linked seed."""
    from apps.create.content.models import ContentSeed

    seed = (
        ContentSeed.objects.filter(product=product)
        .select_related("marketing_campaign")
        .order_by("-created_at")
        .first()
    )
    if seed:
        return get_visual_brief_for_seed(seed)
    return None
