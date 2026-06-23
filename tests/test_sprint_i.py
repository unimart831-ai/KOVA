"""Sprint I — professional polish: asset picker, board copy, first comment, nurture."""

from __future__ import annotations

import pytest

from apps.accounts.models import User, UserProfile
from apps.bookings.models import BookingLink
from apps.briefs.dashboard import _money_board_from_stats
from apps.content.models import ContentSeed, Post
from apps.content.professional_cta import (
    apply_professional_cta_to_post,
    compose_professional_first_comment,
)
from apps.engage.models import Interaction
from apps.leads.bridges import create_lead_from_engage_intent
from apps.leads.models import Lead, LeadEnrollment, NurtureSequence, NurtureStep
from apps.platforms.models import SocialAccount
from apps.products.models import BusinessAsset, Product
from apps.products.professional_assets import apply_professional_asset_from_post


@pytest.fixture
def pro_user(db):
    u = User.objects.create_user(username="pro_i", email="pro_i@kova.ai", password="x")
    UserProfile.objects.filter(user=u).update(
        business_model="professional",
        company_name="Acme Law",
        page_slug="acme-law",
        autopilot_auto_enroll_leads=True,
    )
    BookingLink.objects.create(
        user=u, slug="acme-law", label="Consult", services=[], working_hours={"mon": []},
    )
    return u


@pytest.mark.django_db
def test_professional_money_board_copy():
    stats = {
        "business_model": "professional",
        "leads_week": 1,
        "needs_reply": 0,
        "needs_reply_wa": 0,
        "needs_reply_engage": 0,
        "hot_leads": 2,
        "ready_to_approve": 1,
    }
    board = _money_board_from_stats(stats)
    assert board["hot_leads"]["label"] == "Hot consultation leads"
    assert board["ready_to_approve"]["label"] == "Authority posts to approve"


@pytest.mark.django_db
def test_apply_professional_asset_from_post(pro_user):
    product = Product.objects.create(user=pro_user, name="Redesign", price=0)
    asset = apply_professional_asset_from_post(
        product,
        {
            "asset_type": "case_study",
            "asset_client": "Jane Ltd",
            "asset_pain": "Slow site",
            "asset_outcome": "2x leads",
        },
    )
    assert asset.asset_type == BusinessAsset.AssetType.CASE_STUDY
    assert asset.metadata["client"] == "Jane Ltd"
    assert asset.metadata["pain"] == "Slow site"


@pytest.mark.django_db
def test_professional_first_comment_on_cta(pro_user):
    sa = SocialAccount.objects.create(
        user=pro_user, platform="linkedin", username="acme", platform_user_id="li2", is_active=True,
    )
    post = Post.objects.create(
        user=pro_user, social_account=sa, platform="linkedin", content_text="Case study post",
    )
    seed = ContentSeed.objects.create(user=pro_user, idea="Case")
    assert apply_professional_cta_to_post(post, pro_user, seed) is True
    post.refresh_from_db()
    assert post.first_comment
    assert "http" in post.first_comment.lower() or post.cta_url in post.first_comment
    fc = compose_professional_first_comment("linkedin", post, url=post.cta_url)
    assert fc and post.cta_url in fc


@pytest.mark.django_db
def test_booking_intent_enrolls_nurture_sequence(pro_user):
    seq = NurtureSequence.objects.create(
        user=pro_user,
        name="Booking follow-up",
        trigger=NurtureSequence.Trigger.FROM_BOOKING_INTENT,
        is_active=True,
    )
    NurtureStep.objects.create(
        sequence=seq, order=0, delay_hours=1, action_type="send_email",
        email_subject="Book", email_body="Hi",
    )

    interaction = Interaction.objects.create(
        user=pro_user,
        platform="instagram",
        interaction_type="comment",
        status="new",
        content="Can I book a consultation?",
        author_username="client2",
        author_name="Client",
        ai_intent="booking",
    )
    lead = create_lead_from_engage_intent(interaction)
    assert lead is not None
    assert LeadEnrollment.objects.filter(lead=lead, sequence=seq).exists()
    assert lead.metadata.get("engage_intent") == "booking"
