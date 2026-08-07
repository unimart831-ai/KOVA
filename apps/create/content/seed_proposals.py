"""
Seed Generation Engine — propose multiple marketing opportunities from one BusinessAsset.

Kova Brain decides angles; activating a proposal consumes one campaign from monthly quota.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field

from django.utils import timezone

logger = logging.getLogger(__name__)

PROPOSAL_SESSION_KEY = "kova_proposal_cache"


def _proposal_cache_key(asset_id) -> str:
    return f"{asset_id}"


def cache_proposals_for_asset(request, asset, proposals: list[SeedProposal]) -> None:
    """Persist proposals in session so POST activation matches GET."""
    if not hasattr(request, "session"):
        return
    cache = dict(request.session.get(PROPOSAL_SESSION_KEY) or {})
    cache[_proposal_cache_key(asset.pk)] = {
        "proposals": [p.to_dict() for p in proposals],
        "cached_at": timezone.now().isoformat(),
    }
    request.session[PROPOSAL_SESSION_KEY] = cache
    request.session.modified = True


def get_cached_proposals(request, asset) -> dict[str, SeedProposal] | None:
    if not hasattr(request, "session"):
        return None
    cache = request.session.get(PROPOSAL_SESSION_KEY) or {}
    bucket = cache.get(_proposal_cache_key(asset.pk))
    if not bucket:
        return None
    return {
        item["id"]: SeedProposal(**item)
        for item in bucket.get("proposals", [])
        if item.get("id")
    }


def _vision_context_from_asset(asset, user=None) -> dict:
    from apps.commerce.products.asset_metadata import normalize_asset_metadata

    meta = normalize_asset_metadata(getattr(asset, "metadata", None) or {})
    intel = meta.get("intelligence") or {}
    vision = meta.get("vision_analysis") or {}
    ctx = {
        "description": (vision.get("description") or getattr(asset, "description", "") or "")[:400],
        "campaign_angle": intel.get("campaign_angle") or vision.get("campaign_angle") or meta.get("campaign_angle") or "",
        "target_audience": intel.get("target_audience") or vision.get("target_audience") or meta.get("target_audience") or "",
        "objective": intel.get("objective") or "",
        "key_features": vision.get("key_features") or [],
        "visual_style": vision.get("visual_style") or "",
    }
    if user and not ctx["target_audience"]:
        try:
            from apps.create.media.audience_dna import infer_audience_dna

            dna = infer_audience_dna(user)
            if dna.primary_audience:
                ctx["target_audience"] = dna.primary_audience
            if dna.desires:
                ctx["audience_desires"] = dna.desires[:3]
        except Exception:
            pass
    return ctx


def _retire_snap_orphan_seeds(user, product) -> int:
    """Remove in-flight snap seeds superseded by proposal activation."""
    if not product:
        return 0
    from apps.create.content.models import ContentSeed

    qs = ContentSeed.objects.filter(
        user=user,
        product=product,
        status__in=(ContentSeed.SeedStatus.NEW, ContentSeed.SeedStatus.PROCESSING),
    ).filter(notes__icontains="Snap to Sell")
    count = qs.count()
    if count:
        qs.update(
            status=ContentSeed.SeedStatus.FAILED,
            error_message="Superseded — campaign started from marketing proposal.",
        )
    return count


@dataclass
class SeedProposal:
    id: str
    title: str
    angle: str
    intent: str
    suggested_formats: list[str] = field(default_factory=list)
    rationale: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# Rule-based angles by asset type — LLM enriches when budget allows.
_ANGLE_LIBRARY: dict[str, list[tuple[str, str, str, list[str]]]] = {
    "product": [
        ("new_arrival", "New arrival", "offer", ["reel", "carousel", "story"]),
        ("styling_tips", "Styling tips", "solution", ["carousel", "reel"]),
        ("weekend_offer", "Weekend offer", "offer", ["carousel", "reel", "story"]),
        ("gift_idea", "Gift idea", "offer", ["carousel", "story"]),
        ("social_proof", "Customer favorite", "proof", ["carousel", "single_post"]),
        ("trend_angle", "Trending now", "awareness", ["reel", "story"]),
    ],
    "service": [
        ("transformation", "Before & after", "proof", ["reel", "carousel"]),
        ("book_now", "Book this week", "offer", ["reel", "story"]),
        ("expert_tips", "Pro tips", "authority", ["carousel"]),
        ("testimonial", "Happy client", "proof", ["carousel", "reel"]),
        ("limited_slots", "Limited slots", "offer", ["story", "reel"]),
    ],
    "portfolio": [
        ("case_highlight", "Project spotlight", "authority", ["carousel", "reel"]),
        ("results", "Results we delivered", "proof", ["carousel"]),
        ("consult_cta", "Book a consultation", "offer", ["single_post", "story"]),
    ],
    "testimonial": [
        ("story", "Client success story", "proof", ["reel", "carousel"]),
        ("trust", "Why clients choose us", "proof", ["carousel"]),
    ],
    "offer": [
        ("flash", "Flash sale", "offer", ["reel", "carousel", "story"]),
        ("last_chance", "Last chance", "offer", ["story", "reel"]),
    ],
    "default": [
        ("launch", "Announce it", "awareness", ["reel", "carousel"]),
        ("benefits", "Key benefits", "solution", ["carousel"]),
        ("cta", "Take action", "offer", ["story", "single_post"]),
    ],
}


def _asset_type_key(asset) -> str:
    from apps.commerce.products.models import BusinessAsset

    if asset is None:
        return "default"
    raw = getattr(asset, "asset_type", None) or BusinessAsset.AssetType.PRODUCT
    if raw in (BusinessAsset.AssetType.SERVICE,):
        return "service"
    if raw in (BusinessAsset.AssetType.PORTFOLIO, BusinessAsset.AssetType.CASE_STUDY):
        return "portfolio"
    if raw == BusinessAsset.AssetType.TESTIMONIAL:
        return "testimonial"
    if raw in (BusinessAsset.AssetType.OFFER, BusinessAsset.AssetType.PROMOTION, BusinessAsset.AssetType.EVENT):
        return "offer"
    return "product"


def _rule_proposals(asset, *, max_proposals: int = 5, user=None) -> list[SeedProposal]:
    key = _asset_type_key(asset)
    library = _ANGLE_LIBRARY.get(key) or _ANGLE_LIBRARY["default"]
    title = (getattr(asset, "title", None) or getattr(asset, "name", "") or "Your offer").strip()
    vision = _vision_context_from_asset(asset, user=user)
    proposals: list[SeedProposal] = []
    for angle_id, label, intent, formats in library[:max_proposals]:
        rationale = f"Strong {intent} angle for {key.replace('_', ' ')} businesses."
        if vision.get("target_audience"):
            rationale += f" Audience: {vision['target_audience']}."
        if vision.get("campaign_angle") and angle_id in ("weekend_offer", "flash", "new_arrival"):
            rationale += f" Fits your {vision['campaign_angle']} positioning."
        display_title = f"{label}: {title}"[:200]
        proposals.append(
            SeedProposal(
                id=angle_id,
                title=display_title,
                angle=angle_id,
                intent=intent,
                suggested_formats=formats,
                rationale=rationale,
            )
        )
    return proposals


def propose_seeds_from_asset(asset, user, *, max_proposals: int = 5) -> list[SeedProposal]:
    """
    Return marketing opportunities for a BusinessAsset.

    Uses rule library first; optionally enriches via LLM when user has token budget.
    """
    proposals = _rule_proposals(asset, max_proposals=max_proposals, user=user)
    if not proposals:
        return proposals

    try:
        enriched = _llm_enrich_proposals(asset, user, proposals)
        if enriched:
            proposals = enriched[:max_proposals]
    except Exception as exc:
        logger.info("LLM seed proposals skipped for asset %s: %s", getattr(asset, "pk", ""), exc)

    from apps.create.content.campaign_attribution import rank_proposals_by_revenue_history
    from apps.create.media.revenue_dna import bias_proposals_with_revenue_dna, get_revenue_dna_hints

    ranked = rank_proposals_by_revenue_history(user, proposals)
    return bias_proposals_with_revenue_dna(ranked, get_revenue_dna_hints(user))


def _llm_enrich_proposals(asset, user, proposals: list[SeedProposal]) -> list[SeedProposal] | None:
    """Optional LLM pass — rewrites titles/rationale in brand voice."""
    from apps.create.agents.llm import generate, parse_llm_json
    from apps.create.media.brand_dna import resolve_brand_dna

    dna = resolve_brand_dna(user)
    title = (getattr(asset, "title", "") or "").strip()
    desc = (getattr(asset, "description", "") or "")[:400]
    angles_json = [p.to_dict() for p in proposals]

    audience_hint = ""
    try:
        from apps.create.media.audience_dna import infer_audience_dna

        aud = infer_audience_dna(user)
        if aud.primary_audience or aud.desires:
            audience_hint = (
                f"Audience: {aud.primary_audience or 'general'}. "
                f"Desires: {', '.join(aud.desires or [])}. "
                f"Geography: {aud.geography or 'regional'}.\n"
            )
    except Exception:
        pass

    prompt = (
        f"Business: {dna.brand_name}\n"
        f"{audience_hint}"
        f"Asset: {title}\n"
        f"Description: {desc}\n\n"
        f"Improve these marketing angle proposals for an African SME. "
        f"Keep the same id/angle/intent/suggested_formats but rewrite title and rationale "
        f"in brand voice. Return JSON array of {len(proposals)} objects.\n"
        f"Proposals: {angles_json}"
    )
    response = generate(
        prompt=prompt,
        system="You are Kova, a marketing strategist. Return only valid JSON array.",
        temperature=0.7,
        max_tokens=1200,
        json_mode=True,
        user=user,
    )
    if not response.content:
        return None
    data = parse_llm_json(response.content)
    if not isinstance(data, list):
        return None

    out: list[SeedProposal] = []
    for item, fallback in zip(data, proposals):
        if not isinstance(item, dict):
            out.append(fallback)
            continue
        out.append(
            SeedProposal(
                id=str(item.get("id") or fallback.id),
                title=str(item.get("title") or fallback.title)[:200],
                angle=str(item.get("angle") or fallback.angle),
                intent=str(item.get("intent") or fallback.intent),
                suggested_formats=list(item.get("suggested_formats") or fallback.suggested_formats),
                rationale=str(item.get("rationale") or fallback.rationale)[:500],
            )
        )
    return out or None


def _map_intent_to_seed(intent: str) -> str:
    from apps.create.content.models import ContentSeed

    mapping = {
        "sales": ContentSeed.Intent.OFFER,
        "offer": ContentSeed.Intent.OFFER,
        "leads": ContentSeed.Intent.OFFER,
        "bookings": ContentSeed.Intent.OFFER,
        "awareness": ContentSeed.Intent.PROBLEM_AWARENESS,
        "solution": ContentSeed.Intent.SOLUTION,
        "proof": ContentSeed.Intent.PROOF,
        "authority": ContentSeed.Intent.AUTHORITY,
    }
    return mapping.get(intent, ContentSeed.Intent.OFFER)


def parse_content_types_from_post(post_data) -> list[str]:
    """Parse content-type checkboxes from a request.POST / dict. Default = all."""
    from apps.create.content.campaign_bundle import CONTENT_TYPE_ALL, normalize_content_types

    raw = post_data.getlist("content_types") if hasattr(post_data, "getlist") else post_data.get("content_types")
    if raw is None:
        return sorted(CONTENT_TYPE_ALL)
    if isinstance(raw, str):
        raw = [x.strip() for x in raw.split(",") if x.strip()]
    return sorted(normalize_content_types(raw))


def activate_proposal(
    user,
    asset,
    proposal: SeedProposal | dict,
    *,
    target_platforms: list | None = None,
    content_types: list[str] | None = None,
):
    """
    User picked one proposal — create ContentSeed + MarketingCampaign and queue generation.
    """
    from apps.core.billing.enforcement import check_seed_limit
    from apps.create.content.campaign_bundle import CONTENT_TYPE_ALL, normalize_content_types
    from apps.create.content.campaigns import ensure_campaign_for_seed
    from apps.create.content.models import ContentSeed
    from apps.create.content.tasks import generate_from_seed
    from apps.core.utils import fire_task

    allowed, message = check_seed_limit(user)
    if not allowed:
        from apps.core.billing.exceptions import PlanLimitExceeded
        raise PlanLimitExceeded(message)

    if isinstance(proposal, dict):
        proposal = SeedProposal(**proposal)

    product = getattr(asset, "product", None)
    _retire_snap_orphan_seeds(user, product)

    selected_types = sorted(normalize_content_types(content_types))
    meta = proposal.to_dict()
    idea = proposal.title
    if proposal.rationale:
        idea = f"{proposal.title}\n\nAngle: {proposal.rationale}"

    seed = ContentSeed.objects.create(
        user=user,
        product=product,
        idea=idea,
        notes=f"Activated from proposal `{proposal.id}`",
        target_platforms=target_platforms or [],
        target_intent=_map_intent_to_seed(proposal.intent),
        status=ContentSeed.SeedStatus.PROCESSING,
        blueprint={
            "proposal": meta,
            "suggested_formats": proposal.suggested_formats,
            "selected_content_types": selected_types,
            "objective": proposal.intent,
        },
    )

    ensure_campaign_for_seed(
        seed,
        title=proposal.title,
        objective=proposal.intent,
        proposal_meta=meta,
        business_asset=asset,
    )

    fire_task(generate_from_seed, str(seed.pk))
    return seed
