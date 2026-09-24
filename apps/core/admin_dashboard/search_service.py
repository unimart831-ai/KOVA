"""Staff admin global search — DB keyword queries with optional LLM hint."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field

from django.conf import settings
from django.db.models import Q
from django.urls import reverse

logger = logging.getLogger(__name__)

PER_GROUP = 5
MIN_QUERY_LEN = 2


@dataclass
class SearchHit:
    title: str
    subtitle: str
    url: str


@dataclass
class SearchGroup:
    label: str
    hits: list[SearchHit] = field(default_factory=list)


def _clip(text: str, max_len: int = 80) -> str:
    text = (text or "").replace("\n", " ").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def _safe_subtitle(*parts: str) -> str:
    return _clip(" · ".join(p for p in parts if p))


def admin_global_search(query: str, limit_per_group: int = PER_GROUP) -> list[SearchGroup]:
    q = (query or "").strip()
    if len(q) < MIN_QUERY_LEN:
        return []

    groups: list[SearchGroup] = []
    uuid_filter = None
    try:
        uuid_filter = uuid.UUID(q)
    except ValueError:
        pass

    groups.append(_search_users(q, uuid_filter, limit_per_group))
    groups.append(_search_posts(q, uuid_filter, limit_per_group))
    groups.append(_search_leads(q, uuid_filter, limit_per_group))
    groups.append(_search_products(q, uuid_filter, limit_per_group))
    groups.append(_search_sales_inquiries(q, uuid_filter, limit_per_group))
    groups.append(_search_content_safety(q, uuid_filter, limit_per_group))

    return [g for g in groups if g.hits]


def run_admin_search(query: str) -> list[SearchGroup]:
    """Backward-compatible alias for :func:`admin_global_search`."""
    return admin_global_search(query)


def _search_users(q: str, uid: uuid.UUID | None, limit: int = PER_GROUP) -> SearchGroup:
    from apps.core.accounts.models import User

    filt = Q(email__icontains=q) | Q(full_name__icontains=q) | Q(username__icontains=q)
    filt |= Q(profile__company_name__icontains=q)
    if uid:
        filt |= Q(pk=uid)
    qs = (
        User.objects.filter(filt)
        .select_related("profile")
        .order_by("-date_joined")[:limit]
    )
    hits = []
    for u in qs:
        company, plan = "", ""
        try:
            company = u.profile.company_name
            plan = u.profile.plan
        except Exception:
            pass
        hits.append(
            SearchHit(
                title=u.full_name or u.email,
                subtitle=_safe_subtitle(u.email, company, plan),
                url=reverse("admin_dashboard:user_detail", kwargs={"pk": u.pk}),
            ),
        )
    return SearchGroup(label="Users", hits=hits)


def _search_posts(q: str, uid: uuid.UUID | None, limit: int = PER_GROUP) -> SearchGroup:
    from apps.create.content.models import Post

    filt = Q(content_text__icontains=q) | Q(platform__icontains=q)
    if uid:
        filt |= Q(pk=uid)
    qs = Post.objects.select_related("user").filter(filt).order_by("-created_at")[:limit]
    hits = [
        SearchHit(
            title=_clip(p.content_text, 60) or f"Post {p.pk}",
            subtitle=_safe_subtitle(str(p.pk)[:8], p.platform, p.user.email if p.user_id else ""),
            url=reverse("admin_dashboard:post_detail_admin", kwargs={"pk": p.pk}),
        )
        for p in qs
    ]
    return SearchGroup(label="Posts", hits=hits)


def _search_leads(q: str, uid: uuid.UUID | None, limit: int = PER_GROUP) -> SearchGroup:
    from apps.commerce.leads.models import Lead

    filt = Q(name__icontains=q) | Q(email__icontains=q) | Q(phone__icontains=q)
    if uid:
        filt |= Q(pk=uid)
    qs = Lead.objects.select_related("user").filter(filt).order_by("-first_seen_at")[:limit]
    hits = [
        SearchHit(
            title=lead.name or lead.email,
            subtitle=_safe_subtitle(lead.email, lead.status, lead.user.email if lead.user_id else ""),
            url=reverse("admin_dashboard:lead_list") + f"?q={lead.email}",
        )
        for lead in qs
    ]
    return SearchGroup(label="Leads", hits=hits)


def _search_products(q: str, uid: uuid.UUID | None, limit: int = PER_GROUP) -> SearchGroup:
    from apps.commerce.products.models import Product

    filt = Q(name__icontains=q) | Q(description__icontains=q)
    if uid:
        filt |= Q(pk=uid)
    qs = Product.objects.select_related("user").filter(filt).order_by("-updated_at")[:limit]
    hits = [
        SearchHit(
            title=p.name,
            subtitle=_safe_subtitle(p.user.email if p.user_id else "", p.offering_type),
            url=reverse("admin_dashboard:commerce_product_detail", kwargs={"pk": p.pk}),
        )
        for p in qs
    ]
    return SearchGroup(label="Products", hits=hits)


def _search_sales_inquiries(q: str, uid: uuid.UUID | None, limit: int = PER_GROUP) -> SearchGroup:
    from apps.core.billing.models import AgencySalesInquiry

    filt = (
        Q(name__icontains=q)
        | Q(email__icontains=q)
        | Q(company_name__icontains=q)
        | Q(phone__icontains=q)
        | Q(message__icontains=q)
    )
    if uid:
        filt |= Q(pk=uid)
    qs = AgencySalesInquiry.objects.filter(filt).order_by("-created_at")[:limit]
    hits = [
        SearchHit(
            title=inquiry.company_name or inquiry.name,
            subtitle=_safe_subtitle(inquiry.email, inquiry.status, inquiry.plan_interest),
            url=reverse("admin_dashboard:sales_inquiry_detail", kwargs={"pk": inquiry.pk}),
        )
        for inquiry in qs
    ]
    return SearchGroup(label="Agency Sales", hits=hits)


def _search_content_safety(q: str, uid: uuid.UUID | None, limit: int = PER_GROUP) -> SearchGroup:
    from apps.create.content.models import ContentSafetyIncident

    filt = Q(user__email__icontains=q) | Q(user__full_name__icontains=q)
    filt |= Q(source__icontains=q) | Q(categories__icontains=q)
    if uid:
        filt |= Q(pk=uid)
    qs = (
        ContentSafetyIncident.objects.select_related("user", "post")
        .filter(filt)
        .order_by("-created_at")[:limit]
    )
    hits = []
    for inc in qs:
        cats = ", ".join(inc.categories[:3]) if inc.categories else inc.source
        hits.append(
            SearchHit(
                title=f"Incident · {inc.get_review_status_display()}",
                subtitle=_safe_subtitle(inc.user.email, cats, f"severity {inc.severity}"),
                url=reverse("admin_dashboard:content_safety_incident_detail", kwargs={"pk": inc.pk}),
            ),
        )
    return SearchGroup(label="Content Safety", hits=hits)


def _search_marketplaces(q: str, limit: int = PER_GROUP) -> SearchGroup:
    return SearchGroup(label="Marketplaces", hits=[])



def _search_marketplace_sellers(q: str, limit: int = PER_GROUP) -> SearchGroup:
    return SearchGroup(label="Marketplace Sellers", hits=[])



def _search_partners(q: str, limit: int = PER_GROUP) -> SearchGroup:
    return SearchGroup(label="Partners", hits=[])



def _search_partner_applications(q: str, limit: int = PER_GROUP) -> SearchGroup:
    return SearchGroup(label="Partner Applications", hits=[])



def maybe_interpret_query(query: str, groups: list[SearchGroup]) -> str:
    """Optional one-line LLM summary of what the search likely meant."""
    if not getattr(settings, "OPENROUTER_API_KEY", ""):
        return ""
    if len(query) < 3:
        return ""

    summary_lines = []
    for g in groups[:6]:
        if g.hits:
            summary_lines.append(f"{g.label}: {g.hits[0].title}")

    try:
        from apps.create.agents.llm import generate

        model = getattr(settings, "CONTENT_SAFETY_MODEL", "google/gemini-2.0-flash-001")
        system = (
            "You help Kova staff search the admin dashboard. "
            "Reply with one short sentence (max 20 words) suggesting what they may want to open. "
            "Do not include passwords, API keys, or secrets."
        )
        prompt = (
            f"Search query: {query}\n"
            f"Top matches: {', '.join(summary_lines) or 'none yet'}\n"
            "One helpful sentence for the staff member:"
        )
        resp = generate(prompt, system=system, model=model, temperature=0.2, max_tokens=60, user=None)
        return (resp.content or "").strip()[:200]
    except Exception as exc:
        logger.debug("Admin search interpret skipped: %s", exc)
        return ""
