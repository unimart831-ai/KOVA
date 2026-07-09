"""
Campaign quality assurance — multi-dimension scoring and publish gate.

Dimensions (each 0–100, weighted into campaign score):
  brand      — blueprint alignment, voice, no placeholders
  visual     — media readiness, format fit
  platform   — length, native formatting
  cta        — commerce URL, UTM, first-comment CTAs
  compliance — policy patterns, no engagement bait

Default publish minimum: 75 (override via settings or profile).
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)

DEFAULT_PUBLISH_MIN_SCORE = 75
POST_FLOOR_BELOW_CAMPAIGN = 10  # single post may be min_score - 10

DIMENSION_WEIGHTS = {
    "brand": 0.20,
    "visual": 0.25,
    "platform": 0.20,
    "cta": 0.20,
    "compliance": 0.15,
}

DIMENSION_LABELS = {
    "brand": "Brand",
    "visual": "Visual",
    "platform": "Platform",
    "platform_fit": "Platform fit",
    "cta": "CTA",
    "compliance": "Compliance",
}

PLATFORM_MIN_CHARS = {
    "instagram": 40,
    "facebook": 60,
    "linkedin": 80,
    "tiktok": 30,
    "twitter": 30,
}

MARKDOWN_PATTERN = re.compile(r"(\*\*|__|\*[^*]+\*|_[^_]+_)")


@dataclass
class PostQAScore:
    post_id: str
    platform: str
    post_format: str
    overall: int
    dimensions: dict[str, int]
    issues: list[str] = field(default_factory=list)


@dataclass
class CampaignQAReport:
    overall: int
    publish_ready: bool
    min_required: int
    dimensions: dict[str, int]
    posts: list[PostQAScore]
    issues: list[str] = field(default_factory=list)
    gates_failed: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["posts"] = [asdict(p) for p in self.posts]
        return data


def get_publish_min_score(user) -> int:
    """Per-user threshold; falls back to settings then default 75."""
    profile = getattr(user, "profile", None)
    override = getattr(profile, "campaign_publish_min_score", None) if profile else None
    if override is not None:
        try:
            return max(50, min(100, int(override)))
        except (TypeError, ValueError):
            pass
    return int(getattr(settings, "CAMPAIGN_PUBLISH_MIN_QUALITY", DEFAULT_PUBLISH_MIN_SCORE))


def _weighted_overall(dimensions: dict[str, int]) -> int:
    total = 0.0
    for key, weight in DIMENSION_WEIGHTS.items():
        total += dimensions.get(key, 0) * weight
    return int(round(total))


def _score_brand(post, *, blueprint: dict | None) -> tuple[int, list[str]]:
    issues: list[str] = []
    dna = post.content_dna or {}
    raw = dna.get("blueprint_quality")
    if isinstance(raw, (int, float)):
        return max(0, min(100, int(raw))), issues

    text = (post.content_text or "").strip()
    score = 55
    if len(text) >= 40:
        score += 15
    if len(text) >= 120:
        score += 10
    if (post.ai_angle or "").strip():
        score += 10
    if (post.ai_framework or "").strip():
        score += 5

    if blueprint:
        from apps.content.renderers import blueprint_quality_score

        pseudo = {
            "platform": post.platform,
            "content_text": text,
            "post_format": post.post_format,
            "_blueprint_slots": dna.get("blueprint_slots"),
        }
        score = blueprint_quality_score(pseudo, blueprint)

    from apps.content.safety import HALLUCINATION_PATTERNS

    for pattern in HALLUCINATION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            issues.append("Placeholder or AI artifact in caption")
            score -= 25
            break

    return max(0, min(100, score)), issues


def _score_visual(post) -> tuple[int, list[str]]:
    issues: list[str] = []
    plat = post.platform or ""
    fmt = post.post_format or "text"

    if plat in post.MEDIA_REQUIRED_PLATFORMS:
        if post.needs_media:
            issues.append(f"{plat.title()} post needs media")
            return 25, issues
        if post.media_status == post.MediaStatus.PENDING:
            issues.append("Images still generating")
            return 55, issues
        if not post.has_media and fmt not in ("text",):
            return 30, issues
        return 92, issues

    if fmt == "carousel":
        slides = post.carousel_slides or []
        with_images = sum(
            1 for s in slides if isinstance(s, dict) and s.get("image_url")
        )
        if len(slides) >= 5 and with_images >= 5:
            return 95, issues
        if len(slides) >= 3:
            return 75, issues
        issues.append("Carousel needs more slides")
        return 50, issues

    if fmt == "reel":
        meta = post.visual_metadata or {}
        if getattr(post, "reel_has_video", False) or post.has_media:
            return 90, issues
        if meta.get("video_compose_status") == "done" and meta.get("reel_video_url"):
            return 90, issues
        if getattr(post, "reel_compose_pending", False) or meta.get("video_compose_status") == "pending":
            return 65, issues
        if meta.get("video_compose_status") == "failed":
            issues.append("Reel video composition failed")
            return 35, issues
        issues.append("Reel video not ready")
        return 40, issues

    if fmt in ("image", "story") and post.has_media:
        return 88, issues

    if fmt == "text":
        return 85, issues

    return 70, issues


def _score_platform(post) -> tuple[int, list[str]]:
    issues: list[str] = []
    text = (post.content_text or "").strip()
    plat = (post.platform or "").lower()
    score = 70

    min_chars = PLATFORM_MIN_CHARS.get(plat, 40)
    if len(text) < min_chars:
        issues.append(f"Caption short for {plat or 'platform'}")
        score -= 20
    elif len(text) >= min_chars * 2:
        score += 15

    if MARKDOWN_PATTERN.search(text):
        issues.append("Markdown may render incorrectly")
        score -= 15

    if plat == "instagram" and post.post_format == "carousel":
        if len(post.carousel_slides or []) >= 5:
            score += 10

    if plat == "linkedin" and len(text) > 100:
        score += 10

    return max(0, min(100, score)), issues


def _score_cta(post, *, seed=None) -> tuple[int, list[str]]:
    issues: list[str] = []
    score = 40

    if (post.cta_url or "").strip():
        score += 25
    else:
        issues.append("No CTA link on post")

    if (post.utm_campaign or "").strip():
        score += 15

    if (post.first_comment or "").strip():
        score += 10

    url = (post.cta_url or "").lower()
    if "/c/" in url or "/shop/" in url:
        score += 10
    elif seed and getattr(seed, "product_id", None):
        issues.append("CTA not pointing to Kova commerce")

    return max(0, min(100, score)), issues


def _score_compliance(post) -> tuple[int, list[str]]:
    from apps.content.safety import ENGAGEMENT_BAIT_PATTERNS, HALLUCINATION_PATTERNS

    issues: list[str] = []
    text = (post.content_text or "") + " " + (post.first_comment or "")
    score = 90

    for pattern in HALLUCINATION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            issues.append("AI placeholder text detected")
            score -= 30
            break

    for pattern in ENGAGEMENT_BAIT_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            issues.append("Engagement-bait phrasing")
            score -= 15
            break

    if "[insert" in text.lower() or "lorem ipsum" in text.lower():
        issues.append("Unfinished template text")
        score -= 25

    return max(0, min(100, score)), issues


def score_post_qa(post, *, seed=None, blueprint: dict | None = None) -> PostQAScore:
    """Score one post across all QA dimensions."""
    if blueprint is None and seed:
        blueprint = getattr(seed, "blueprint", None) or {}

    brand, bi = _score_brand(post, blueprint=blueprint)
    visual, vi = _score_visual(post)
    platform, pi = _score_platform(post)
    cta, ci = _score_cta(post, seed=seed)
    compliance, coi = _score_compliance(post)

    dimensions = {
        "brand": brand,
        "visual": visual,
        "platform": platform,
        "cta": cta,
        "compliance": compliance,
    }
    issues = bi + vi + pi + ci + coi

    result = PostQAScore(
        post_id=str(post.pk),
        platform=post.platform or "",
        post_format=post.post_format or "",
        overall=_weighted_overall(dimensions),
        dimensions=dimensions,
        issues=issues[:4],
    )

    from apps.content.platform_fit import enrich_post_qa_with_platform_fit

    audience = ""
    if seed and getattr(seed.user, "profile", None):
        audience = (seed.user.profile.target_audience or "").strip()
    enrich_post_qa_with_platform_fit(result, post, blueprint=blueprint, audience=audience)
    return result


def audit_campaign_qa(campaign, posts: list, user) -> CampaignQAReport:
    """Compute QA report for a campaign and its posts (read-only)."""
    min_required = get_publish_min_score(user)
    seed = getattr(campaign, "content_seed", None) if campaign else None
    if seed is None and posts:
        seed = getattr(posts[0], "seed", None)
    blueprint = (getattr(seed, "blueprint", None) or {}) if seed else {}

    post_scores = [
        score_post_qa(p, seed=seed, blueprint=blueprint)
        for p in posts
    ]

    if not post_scores:
        empty_dims = {k: 0 for k in DIMENSION_WEIGHTS}
        return CampaignQAReport(
            overall=0,
            publish_ready=False,
            min_required=min_required,
            dimensions=empty_dims,
            posts=[],
            issues=["No posts to score"],
            gates_failed=["empty"],
        )

    dim_totals = {k: 0 for k in DIMENSION_WEIGHTS}
    dim_totals["platform_fit"] = 0
    for ps in post_scores:
        for k in dim_totals:
            if k == "platform_fit":
                dim_totals[k] += ps.dimensions.get("platform_fit", 0)
            else:
                dim_totals[k] += ps.dimensions.get(k, 0)
    n = len(post_scores)
    dimensions = {k: int(round(dim_totals[k] / n)) for k in dim_totals}

    overall = int(round(sum(ps.overall for ps in post_scores) / n))
    post_floor = max(50, min_required - POST_FLOOR_BELOW_CAMPAIGN)

    gates_failed: list[str] = []
    issues: list[str] = []

    if overall < min_required:
        gates_failed.append("campaign_score")
        issues.append(f"Campaign quality {overall}/100 is below {min_required}")

    weak_posts = [ps for ps in post_scores if ps.overall < post_floor]
    if weak_posts:
        gates_failed.append("post_floor")
        issues.append(
            f"{len(weak_posts)} post{'s' if len(weak_posts) != 1 else ''} "
            f"below {post_floor}/100"
        )

    for ps in post_scores:
        for issue in ps.issues:
            if issue not in issues and len(issues) < 6:
                issues.append(issue)

    from apps.content.platform_fit import PLATFORM_FIT_MIN_SCORE, platform_fit_gate

    weak_fit = [
        ps for ps in post_scores
        if ps.dimensions.get("platform_fit", 100) < PLATFORM_FIT_MIN_SCORE
    ]
    if weak_fit:
        gates_failed.append("platform_fit")
        fit_score = weak_fit[0].dimensions.get("platform_fit", 0)
        ok, msg = platform_fit_gate(fit_score)
        if msg and msg not in issues:
            issues.append(msg)

    publish_ready = len(gates_failed) == 0

    return CampaignQAReport(
        overall=overall,
        publish_ready=publish_ready,
        min_required=min_required,
        dimensions=dimensions,
        posts=post_scores,
        issues=issues,
        gates_failed=gates_failed,
    )


def refresh_campaign_qa(campaign, *, posts: list | None = None, user=None) -> CampaignQAReport:
    """Recompute QA, persist on MarketingCampaign, tag posts."""
    from apps.content.models import Post

    if campaign is None:
        raise ValueError("campaign required")

    user = user or campaign.user
    if posts is None:
        posts = list(
            Post.objects.filter(seed=campaign.content_seed).select_related("seed")
        )

    report = audit_campaign_qa(campaign, posts, user)

    meta = dict(campaign.proposal_meta or {})
    meta["qa_report"] = report.to_dict()
    campaign.proposal_meta = meta
    campaign.quality_score = report.overall
    campaign.save(update_fields=["proposal_meta", "quality_score", "updated_at"])

    for ps in report.posts:
        try:
            post = next(p for p in posts if str(p.pk) == ps.post_id)
        except StopIteration:
            continue
        dna = dict(post.content_dna or {})
        dna["qa_score"] = ps.overall
        dna["qa_dimensions"] = ps.dimensions
        post.content_dna = dna
        post.save(update_fields=["content_dna", "updated_at"])

    logger.info(
        "Campaign QA %s: %d/100 publish_ready=%s",
        campaign.pk, report.overall, report.publish_ready,
    )
    return report


def _publish_blocking_reason(post, ps: PostQAScore) -> str | None:
    """Hard block reasons for this post only — not sibling posts in a campaign.

    "Reel video not ready" is intentionally NOT a hard QA block — publish_post
    retries while composition is in progress. Only permanent compose failure blocks here.
    """
    for issue in ps.issues:
        if issue.endswith(" post needs media") or issue in (
            "Images still generating",
            "Carousel needs more slides",
            "Reel video composition failed",
        ):
            return issue
    return None


def check_post_publish_gate(post, user) -> tuple[bool, str, int]:
    """
    Returns (allowed, reason, score).
    Scores only the post being published — sibling posts in a campaign do not block this one.

    When CAMPAIGN_PUBLISH_QA_ENABLED is False (default), score thresholds are skipped.
    Hard blockers (reel compose failed / media missing) still apply so we never
    send incomplete posts to platforms.
    """
    from django.conf import settings

    seed = getattr(post, "seed", None)
    ps = score_post_qa(post, seed=seed)

    blocking = _publish_blocking_reason(post, ps)
    if blocking:
        return False, blocking, ps.overall

    stock_block = _stock_publish_block(post)
    if stock_block:
        return False, stock_block, ps.overall

    qa_enabled = bool(getattr(settings, "CAMPAIGN_PUBLISH_QA_ENABLED", False))
    if not qa_enabled:
        return True, "", ps.overall

    min_required = get_publish_min_score(user)
    post_floor = max(50, min_required - POST_FLOOR_BELOW_CAMPAIGN)

    if ps.overall < post_floor:
        reason = ps.issues[0] if ps.issues else f"Post quality {ps.overall}/100 is too low"
        return False, reason, ps.overall

    return True, "", ps.overall


def _stock_publish_block(post) -> str | None:
    """Block publishing promos for out-of-stock products."""
    product = getattr(post, "product", None)
    if not product:
        return None
    from apps.products.models import Product

    if product.stock_status == Product.StockStatus.OUT_OF_STOCK:
        return f"{product.name} is out of stock — update STOCK or hide before publishing."
    return None


def brand_consistency_hint(post, user) -> str | None:
    """Lightweight brand consistency note for QA display (not a hard block)."""
    profile = getattr(user, "profile", None)
    if not profile:
        return None
    voice = (getattr(profile, "brand_voice", "") or "").lower()
    text = (post.content_text or "").lower()
    if not voice or len(text) < 20:
        return None
    tone_words = [w.strip() for w in (getattr(profile, "tone_attributes", "") or "").split(",") if w.strip()]
    if tone_words and not any(w.lower() in text for w in tone_words[:3]):
        return "Caption may not match your tone — quick review suggested."
    return None


def qa_display_for_studio(report: CampaignQAReport) -> dict[str, Any]:
    """Template-friendly QA summary for campaign cards."""
    items = []
    for key, label in DIMENSION_LABELS.items():
        val = report.dimensions.get(key, 0)
        items.append({
            "key": key,
            "label": label,
            "score": val,
            "tone": "growth" if val >= 80 else ("gold" if val >= 65 else "gray"),
        })

    if report.publish_ready:
        status_label = "Publish ready"
        status_tone = "growth"
    elif report.overall >= report.min_required - 10:
        status_label = "Review recommended"
        status_tone = "gold"
    else:
        status_label = f"Below {report.min_required}/100"
        status_tone = "red"

    return {
        "overall": report.overall,
        "min_required": report.min_required,
        "publish_ready": report.publish_ready,
        "status_label": status_label,
        "status_tone": status_tone,
        "dimensions": items,
        "issues": report.issues[:4],
        "summary_line": " · ".join(f"{it['label']} {it['score']}" for it in items),
    }
