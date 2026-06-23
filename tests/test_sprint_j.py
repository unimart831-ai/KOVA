"""Sprint J — revenue attribution, MONEY copy, nurture template, studio labels."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.models import User, UserProfile
from apps.accounts.onboarding_express import (
    BUSINESS_MODEL_PROFESSIONAL,
    apply_business_model_defaults,
)
from apps.briefs.asset_attribution import asset_type_label, top_asset_this_week
from apps.briefs.dashboard import _money_board_from_stats
from apps.briefs.revenue_summary import format_money_whatsapp_message, get_unified_revenue_summary
from apps.content.post_labels import post_showcase_label, summarize_showcase_types
from apps.content.models import ContentSeed, Post
from apps.leads.defaults import CONSULTATION_SEQUENCE_NAME, ensure_professional_nurture_sequences
from apps.leads.models import NurtureSequence
from apps.platforms.models import SocialAccount
from apps.products.models import BusinessAsset, CommercePayment, Product


@pytest.fixture
def pro_user(db):
    u = User.objects.create_user(username="proj", email="proj@kova.ai", password="x")
    UserProfile.objects.filter(user=u).update(
        business_model="professional", company_name="Acme Law",
    )
    return u


@pytest.mark.django_db
def test_top_asset_includes_type_label(pro_user):
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
        transaction_ref="j-1",
        checkout_request_id="ws_j_1",
        phone_number="254712345678",
        amount=Decimal("5000"),
        status=CommercePayment.Status.COMPLETED,
        completed_at=timezone.now(),
    )
    since = timezone.now() - timedelta(days=7)
    top = top_asset_this_week(pro_user, since, business_model="professional")
    assert top["title"] == "Tax win"
    assert top["asset_type"] == "case_study"
    assert top["type_label"] == "Case study"


@pytest.mark.django_db
def test_money_board_top_asset_card(pro_user):
    stats = {
        "business_model": "professional",
        "leads_week": 1,
        "needs_reply": 0,
        "needs_reply_wa": 0,
        "needs_reply_engage": 0,
        "hot_leads": 0,
        "ready_to_approve": 0,
        "top_asset_title": "Website redesign",
        "top_asset_type_label": "Portfolio",
        "top_asset_revenue": 0,
    }
    board = _money_board_from_stats(stats)
    assert board["top_asset"]["title"] == "Website redesign"
    assert "active" in board["top_asset"]["detail"]


@pytest.mark.django_db
def test_money_whatsapp_professional_copy(pro_user):
    summary = {
        "business_model": "professional",
        "total_kes": 0,
        "mpesa_kes": 0,
        "mpesa_count": 0,
        "booking_kes": 2000,
        "digital_kes": 0,
        "walkin_kes": 0,
        "leads_week": 3,
        "hot_leads": 1,
        "needs_reply": 0,
        "ready_to_approve": 2,
        "top_asset_title": "Case study: Jane Ltd",
        "top_asset_type_label": "Case study",
        "top_asset_revenue": 0,
    }
    msg = format_money_whatsapp_message(summary)
    assert "Pipeline & revenue" in msg
    assert "Hot consultation leads" in msg
    assert "Authority posts to approve" in msg
    assert "Consultations" in msg
    assert "case study" in msg.lower()


@pytest.mark.django_db
def test_ensure_professional_nurture_sequence(pro_user):
    ensure_professional_nurture_sequences(pro_user)
    seq = NurtureSequence.objects.get(user=pro_user, name=CONSULTATION_SEQUENCE_NAME)
    assert seq.trigger == NurtureSequence.Trigger.FROM_BOOKING_INTENT
    assert seq.steps.count() == 3


@pytest.mark.django_db
def test_onboarding_pro_creates_nurture(pro_user):
    profile = pro_user.profile
    profile.business_model = BUSINESS_MODEL_PROFESSIONAL
    profile.save(update_fields=["business_model"])
    apply_business_model_defaults(profile, pro_user)
    assert NurtureSequence.objects.filter(user=pro_user, name=CONSULTATION_SEQUENCE_NAME).exists()


@pytest.mark.django_db
def test_post_showcase_label_from_blueprint(pro_user):
    sa = SocialAccount.objects.create(
        user=pro_user, platform="linkedin", username="acme", platform_user_id="li3", is_active=True,
    )
    seed = ContentSeed.objects.create(
        user=pro_user,
        idea="Portfolio piece",
        blueprint={"asset_type": "portfolio"},
    )
    post = Post.objects.create(
        user=pro_user, social_account=sa, platform="linkedin", content_text="Work", seed=seed,
    )
    label = post_showcase_label(post)
    assert label["text"] == "Portfolio"
    summary = summarize_showcase_types([post])
    assert "portfolio" in summary.lower()


@pytest.mark.django_db
def test_asset_type_label():
    assert asset_type_label("case_study") == "Case study"
    assert asset_type_label("portfolio") == "Portfolio"
