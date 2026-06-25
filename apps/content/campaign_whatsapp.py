"""
WhatsApp campaign operations — ready notifications, approve package, commerce share.

Powers Phase 4: owner completes loop on phone without opening Studio.
"""

from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def _owner_wa_id(user) -> str:
    from apps.accounts.phone_utils import phone_to_whatsapp_digits

    return phone_to_whatsapp_digits(getattr(user, "phone_number", "") or "")


def send_owner_whatsapp(user, body: str, *, send_buttons: bool = True) -> bool:
    """Send a text message to the business owner on Kova's master WA number."""
    wa_id = _owner_wa_id(user)
    if not wa_id:
        return False
    from apps.briefs.whatsapp_commands import _get_today_brief, _send_owner_reply

    return _send_owner_reply(
        wa_id,
        body[:4096],
        user=user,
        brief=_get_today_brief(user),
        send_buttons=send_buttons,
    )


def owner_whatsapp_enabled(user) -> bool:
    if not getattr(user, "phone_number", ""):
        return False
    if not getattr(user, "brief_whatsapp_enabled", True):
        return False
    from apps.billing.models import get_user_plan_limits

    return bool(get_user_plan_limits(user).get("whatsapp_brief"))


def campaigns_pending_review(user, *, limit: int = 5) -> list[dict]:
    """Campaigns with posts still awaiting approval."""
    from apps.content.models import MarketingCampaign, Post

    rows = []
    campaigns = (
        MarketingCampaign.objects.filter(
            user=user,
            status__in=(
                MarketingCampaign.Status.REVIEW,
                MarketingCampaign.Status.GENERATING,
            ),
        )
        .select_related("content_seed")
        .order_by("-created_at")[:limit * 2]
    )
    for campaign in campaigns:
        seed = campaign.content_seed
        if not seed:
            continue
        pending = Post.objects.filter(
            seed=seed,
            status__in=(Post.Status.DRAFT, Post.Status.PENDING_APPROVAL),
        ).count()
        if pending == 0:
            continue
        total = Post.objects.filter(seed=seed).count()
        rows.append({
            "campaign": campaign,
            "pending": pending,
            "total_posts": total,
            "quality_score": campaign.quality_score,
        })
        if len(rows) >= limit:
            break
    return rows


def format_campaign_ready_message(campaign, *, pending: int, total_posts: int) -> str:
    from apps.content.campaign_pages import campaign_page_url

    site = getattr(settings, "SITE_URL", "").rstrip("/")
    page_url = campaign_page_url(campaign)
    if site and page_url.startswith("/"):
        page_url = f"{site}{page_url}"

    lines = [
        f"✅ Campaign ready: *{campaign.title}*",
        f"{pending} of {total_posts} posts waiting for approval",
    ]
    if campaign.quality_score is not None:
        lines.append(f"Quality score: {campaign.quality_score}/100")
    lines.append(f"\n🛍 Campaign page:\n{page_url}")
    lines.append("\nReply *APPROVE CAMPAIGN* to schedule the full package")
    lines.append("Reply *SHARE* to get links for WhatsApp Status")
    if site:
        lines.append(f"\nStudio: {site}/content/studio/")
    return "\n".join(lines)


def notify_campaign_ready(campaign) -> bool:
    """Push WA notification when generation finishes."""
    if not owner_whatsapp_enabled(campaign.user):
        return False

    from apps.content.models import MarketingCampaign

    if campaign.status != MarketingCampaign.Status.REVIEW:
        return False

    rows = campaigns_pending_review(campaign.user, limit=5)
    match = next((r for r in rows if r["campaign"].pk == campaign.pk), None)
    if not match:
        return False

    body = format_campaign_ready_message(
        campaign,
        pending=match["pending"],
        total_posts=match["total_posts"],
    )
    return send_owner_whatsapp(campaign.user, body, send_buttons=True)


def format_campaigns_list_message(user) -> str:
    rows = campaigns_pending_review(user)
    if not rows:
        return "No campaigns waiting for approval. You're clear!"

    lines = [f"{len(rows)} campaign(s) ready:\n"]
    for i, row in enumerate(rows, start=1):
        c = row["campaign"]
        q = f" · {c.quality_score}/100" if c.quality_score is not None else ""
        lines.append(f"{i}. {c.title} — {row['pending']} post(s){q}")
    lines.append("\nReply APPROVE CAMPAIGN to approve the latest")
    lines.append("Reply APPROVE CAMPAIGN 2 to approve #2")
    lines.append("Reply SHARE 1 for commerce links")
    return "\n".join(lines)


def approve_campaign_via_whatsapp(user, *, index: int = 1) -> tuple[str, bool, dict]:
    """Approve an entire campaign package from WhatsApp."""
    from apps.content.campaign_approval import (
        approval_flash_messages,
        approve_campaign_posts,
        sync_campaign_after_approval,
    )
    from apps.content.models import Post
    from apps.utils import fire_task

    rows = campaigns_pending_review(user)
    if not rows:
        return "No campaigns waiting for approval.", True, {}

    if index < 1 or index > len(rows):
        return f"Pick a number 1–{len(rows)} (e.g. APPROVE CAMPAIGN 2).", False, {}

    row = rows[index - 1]
    campaign = row["campaign"]
    seed = campaign.content_seed
    posts = list(
        Post.objects.filter(
            seed=seed,
            status__in=(Post.Status.DRAFT, Post.Status.PENDING_APPROVAL),
        ).select_related("social_account")
    )
    if not posts:
        return f"\"{campaign.title}\" has nothing left to approve.", True, {}

    result = approve_campaign_posts(user, posts, "next_best")
    sync_campaign_after_approval(campaign, seed)

    if result.post_now_ids:
        from apps.content.tasks import publish_post
        for post_id in result.post_now_ids:
            fire_task(publish_post, post_id)

    flashes = approval_flash_messages(result)
    if result.approved_count == 0:
        msg = flashes[0][1] if flashes else "Couldn't approve — posts may need media first."
        return msg, False, {"campaign_id": str(campaign.pk)}

    msg = f"Approved *{campaign.title}* — {result.approved_count} post(s) scheduled."
    if result.skipped_media:
        msg += f" ({result.skipped_media} skipped — need media)"
    return msg, True, {
        "campaign_id": str(campaign.pk),
        "approved": result.approved_count,
        "skipped_media": result.skipped_media,
    }


def format_commerce_share_message(user, *, index: int = 1) -> tuple[str, bool, dict]:
    """Share card text: campaign page + shop/product URLs for WA Status."""
    from apps.content.campaign_pages import campaign_page_url
    from apps.products.commerce_links import commerce_link_url, resolve_page_slug

    rows = campaigns_pending_review(user, limit=10)
    if not rows:
        # Fall back to latest published campaign
        from apps.content.models import MarketingCampaign

        campaign = (
            MarketingCampaign.objects.filter(user=user)
            .exclude(status=MarketingCampaign.Status.ARCHIVED)
            .order_by("-created_at")
            .first()
        )
        if not campaign:
            return "No campaigns yet — snap a product photo to start.", True, {}
        rows = [{"campaign": campaign, "pending": 0, "total_posts": 0}]

    if index < 1 or index > len(rows):
        return f"Pick 1–{len(rows)} (e.g. SHARE 2).", False, {}

    campaign = rows[index - 1]["campaign"]
    site = getattr(settings, "SITE_URL", "").rstrip("/")
    page_url = campaign_page_url(campaign)
    if site and page_url.startswith("/"):
        page_url = f"{site}{page_url}"

    product = None
    if campaign.content_seed_id:
        product = getattr(campaign.content_seed, "product", None)
    shop_slug = resolve_page_slug(campaign.user.profile)
    shop_url = f"{site}/shop/{shop_slug}/" if site else f"/shop/{shop_slug}/"

    lines = [
        f"🛍 *{campaign.title}*",
        f"\nCampaign page (flash sale / offer):\n{page_url}",
        f"\nYour shop:\n{shop_url}",
    ]
    if product:
        product_url = commerce_link_url(product)
        if site and product_url.startswith("/"):
            product_url = f"{site}{product_url}"
        price = getattr(product, "price", None)
        currency = getattr(product, "currency", "KES") or "KES"
        price_line = f" — {currency} {price:,.0f}" if price else ""
        lines.append(f"\n{product.name}{price_line}:\n{product_url}")

    lines.append("\n_Copy and paste to WhatsApp Status or forward to customers._")
    return "\n".join(lines), True, {"campaign_id": str(campaign.pk)}
