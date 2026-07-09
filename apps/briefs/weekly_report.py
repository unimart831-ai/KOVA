"""Weekly SMM scorecard for WhatsApp WEEKLY command + Celery beat."""

from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils import timezone

logger = logging.getLogger(__name__)


def build_weekly_smm_summary(user, *, days: int = 7) -> dict:
    from apps.analytics.revenue import get_revenue_headline_insight, get_revenue_stat_card
    from apps.analytics.reports import gather_report_data
    from apps.content.models import Post

    report = gather_report_data(user, days=days)
    revenue_card = get_revenue_stat_card(user)
    headline = get_revenue_headline_insight(user, days=days)

    top_post = (
        Post.objects.filter(
            user=user,
            status=Post.Status.PUBLISHED,
            published_at__gte=timezone.now() - timedelta(days=days),
        )
        .select_related("metrics", "social_account")
        .order_by("-metrics__engagement_rate")
        .first()
    )

    top_line = ""
    if top_post:
        rate = getattr(getattr(top_post, "metrics", None), "engagement_rate", None)
        plat = top_post.social_account.get_platform_display() if top_post.social_account else top_post.platform
        top_line = f"\"{(top_post.content_text or '')[:50]}…\" ({plat}"
        if rate is not None:
            top_line += f", {rate:.1%} engagement"
        top_line += ")"

    return {
        "published": report.get("posts_published", 0),
        "impressions": report.get("total_impressions", 0),
        "engagement": report.get("total_engagement", 0),
        "leads": report.get("leads_count", 0),
        "revenue_wow": revenue_card,
        "revenue_headline": headline,
        "top_post_line": top_line,
        "report": report,
    }


def format_weekly_smm_whatsapp(user) -> tuple[str, str, bool, dict]:
    summary = build_weekly_smm_summary(user)
    wow = summary.get("revenue_wow") or {}
    delta = wow.get("delta_pct")
    delta_txt = ""
    if delta is not None:
        sign = "+" if delta > 0 else ""
        delta_txt = f" ({sign}{delta:.0f}% vs prior week)"

    headline = summary.get("revenue_headline") or {}
    rev_line = headline.get("headline") or "Keep publishing — attribution warming up."

    body = (
        f"📊 *Weekly scorecard*\n"
        f"• Published: {summary['published']}\n"
        f"• Reach: {summary['impressions']:,}\n"
        f"• Engagement: {summary['engagement']:,}\n"
        f"• Leads: {summary['leads']}"
        f"{delta_txt}\n\n"
        f"💰 {rev_line}\n"
    )
    if summary.get("top_post_line"):
        body += f"\n🏆 Top post: {summary['top_post_line']}\n"
    body += "\nReply PLAN for next week · POST AGAIN to recycle a winner."
    return body, "weekly", True, summary


@shared_task(name="briefs.send_weekly_smm_whatsapp", ignore_result=True)
def send_weekly_smm_whatsapp_all():
    """Monday-morning style weekly report on owner WhatsApp."""
    from apps.briefs.owner_alerts import send_owner_alert

    User = get_user_model()
    sent = 0
    for user in User.objects.filter(is_active=True, brief_whatsapp_enabled=True).exclude(phone_number=""):
        try:
            body, _, ok, _ = format_weekly_smm_whatsapp(user)
            if ok and send_owner_alert(user, body):
                sent += 1
        except Exception:
            logger.exception("Weekly SMM WhatsApp failed for user %s", user.pk)
    logger.info("Weekly SMM WhatsApp sent to %d owners", sent)
    return {"sent": sent}
