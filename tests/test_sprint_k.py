"""Sprint K — asset breakdown, standup/digest copy, showcase manager, consult funnel."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User, UserProfile
from apps.briefs.asset_attribution import asset_type_breakdown
from apps.briefs.revenue_summary import format_money_board_digest, format_standup_money_line
from apps.briefs.standup import format_standup_whatsapp_message
from apps.leads.models import Lead, LeadActivity
from apps.leads.professional_funnel import process_professional_consult_lead
from apps.products.models import BusinessAsset, CommercePayment, Product


@pytest.fixture
def pro_user(db):
    u = User.objects.create_user(username="prok", email="prok@kova.ai", password="x")
    UserProfile.objects.filter(user=u).update(
        business_model="professional",
        company_name="Acme Law",
        autopilot_auto_enroll_leads=False,
    )
    return u


@pytest.fixture
def svc_user(db):
    u = User.objects.create_user(username="svck", email="svck@kova.ai", password="x")
    UserProfile.objects.filter(user=u).update(business_model="service", company_name="Salon")
    return u


@pytest.mark.django_db
def test_asset_type_breakdown_groups_revenue(pro_user):
    product = Product.objects.create(user=pro_user, name="Tax win", price=5000)
    BusinessAsset.objects.create(
        user=pro_user,
        product=product,
        asset_type=BusinessAsset.AssetType.CASE_STUDY,
        title="Tax win",
    )
    CommercePayment.objects.create(
        user=pro_user,
        product=product,
        transaction_ref="k-1",
        checkout_request_id="ws_k_1",
        phone_number="254712345678",
        amount=Decimal("5000"),
        status=CommercePayment.Status.COMPLETED,
        completed_at=timezone.now(),
    )
    since = timezone.now() - timedelta(days=7)
    rows = asset_type_breakdown(pro_user, since)
    case = next(r for r in rows if r["asset_type"] == "case_study")
    assert case["revenue"] == 5000.0
    assert case["type_label"] == "Case study"


@pytest.mark.django_db
def test_standup_money_line_includes_top_asset_type(pro_user):
    summary = {
        "business_model": "professional",
        "total_kes": 0,
        "mpesa_kes": 0,
        "booking_kes": 0,
        "top_asset_title": "Website redesign",
        "top_asset_type_label": "Portfolio",
        "top_asset_revenue": 0,
    }
    line = format_standup_money_line(summary)
    assert "top portfolio" in line
    assert "Website redesign" in line


@pytest.mark.django_db
def test_money_board_digest_copy_per_business_model(pro_user, svc_user):
    stats_pro = {
        "business_model": "professional",
        "needs_reply": 1,
        "hot_leads": 2,
        "ready_to_approve": 1,
        "top_asset_title": "Case A",
        "top_asset_type_label": "Case study",
    }
    subj, body = format_money_board_digest(pro_user, stats_pro)
    assert "consultation" in subj.lower()
    assert "hot consultation lead" in body
    assert "authority post" in body
    assert "case study" in body.lower()

    stats_svc = {
        "business_model": "service",
        "needs_reply": 0,
        "hot_leads": 1,
        "ready_to_approve": 0,
    }
    subj_svc, body_svc = format_money_board_digest(svc_user, stats_svc)
    assert "booking" in subj_svc.lower()
    assert "hot booking lead" in body_svc


@pytest.mark.django_db
def test_standup_whatsapp_professional_book_hint(pro_user):
    from apps.briefs.models import DailyBrief

    brief = DailyBrief.objects.create(
        user=pro_user,
        date=date.today(),
        summary="Today",
        kova_score=70,
        posts_pending=0,
    )
    msg = format_standup_whatsapp_message(pro_user, brief)
    assert "Reply BOOK for your consultation link" in msg


@pytest.mark.django_db
def test_process_professional_consult_lead_tags_pipeline(pro_user):
    class _Ix:
        ai_intent = "booking"

    lead = Lead.objects.create(
        user=pro_user,
        name="Client",
        phone="254700000001",
        source=Lead.Source.SOCIAL_COMMENT,
        temperature=Lead.Temperature.WARM,
    )
    process_professional_consult_lead(lead, pro_user, interaction=_Ix())
    lead.refresh_from_db()
    assert lead.metadata["pipeline"] == "professional_consult"
    assert lead.metadata["consult_funnel_stage"] == "booking_intent"
    assert lead.temperature == Lead.Temperature.HOT
    assert LeadActivity.objects.filter(lead=lead, activity_type=LeadActivity.ActivityType.NOTE_ADDED).exists()


@pytest.mark.django_db
def test_process_professional_consult_skips_non_professional(svc_user):
    lead = Lead.objects.create(
        user=svc_user,
        name="Client",
        phone="254700000003",
        source=Lead.Source.SOCIAL_COMMENT,
    )
    process_professional_consult_lead(lead, svc_user, interaction=type("Ix", (), {"ai_intent": "booking"})())
    lead.refresh_from_db()
    assert lead.metadata.get("pipeline") != "professional_consult"


@pytest.mark.django_db
def test_showcase_assets_page_and_create(client, pro_user):
    client.force_login(pro_user)
    url = reverse("products:showcase")
    resp = client.get(url)
    assert resp.status_code == 200
    assert b"Add showcase piece" in resp.content

    resp = client.post(url, {
        "action": "create",
        "asset_type": "portfolio",
        "title": "Brand refresh",
        "client": "Co Ltd",
    })
    assert resp.status_code == 302
    assert BusinessAsset.objects.filter(user=pro_user, title="Brand refresh").exists()
