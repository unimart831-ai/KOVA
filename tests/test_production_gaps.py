"""Production-gap tests — proposals pipeline, renewal credits, WA drafts, storefront."""

import pytest
from django.urls import reverse

from apps.billing.campaign_renewal import (
    apply_addon_purchase_bonus,
    maybe_grandfather_to_kova,
    sync_campaign_bonus_totals,
)
from apps.billing.models import CAMPAIGN_ADDON_PACKS
from apps.content.models import ContentSeed
from apps.products.models import BusinessAsset


@pytest.mark.django_db
class TestBriefProposals:
    def test_brief_action_creates_asset_not_seed(self, client, user):
        client.force_login(user)
        user.onboarding_completed = True
        user.phone_number = "254712345678"
        user.save(update_fields=["onboarding_completed", "phone_number"])
        user.profile.subscription_status = "active"
        user.profile.plan = "kova"
        user.profile.save(update_fields=["subscription_status", "plan"])
        url = reverse("brief:action")
        response = client.post(url, {
            "idea": "Weekend salon promo",
            "context": "Fill Saturday slots",
            "action_type": "suggestion",
        })

        assert response.status_code == 302, response.content
        assert "proposals" in response.url, response.url
        assert ContentSeed.objects.filter(user=user).count() == 0
        asset = BusinessAsset.objects.filter(user=user).order_by("-created_at").first()
        assert asset is not None
        assert (asset.metadata or {}).get("brief_idea") is True

    def test_ensure_brief_idea_asset_service_type(self, user):
        from apps.briefs.actions import ensure_brief_idea_asset

        user.profile.business_model = "service"
        user.profile.save(update_fields=["business_model"])

        asset = ensure_brief_idea_asset(user, "Spa day bundle", context="Mother's day")
        assert asset.asset_type == BusinessAsset.AssetType.SERVICE


@pytest.mark.django_db
class TestCampaignRenewal:
    def test_burst_addon_expires_at_month_end(self, user):
        profile = user.profile
        pack = CAMPAIGN_ADDON_PACKS["burst"]
        apply_addon_purchase_bonus(profile, pack)
        profile.refresh_from_db()

        assert profile.burst_campaign_bonus == 5
        assert profile.burst_campaign_expires_at is not None
        assert profile.seed_monthly_bonus == 5

    def test_recurring_addon_stacks(self, user):
        profile = user.profile
        boost = CAMPAIGN_ADDON_PACKS["boost"]
        apply_addon_purchase_bonus(profile, boost)
        apply_addon_purchase_bonus(profile, boost)
        profile.refresh_from_db()

        assert profile.recurring_campaign_bonus == 20
        assert profile.seed_monthly_bonus == 20

    def test_grandfather_growth_to_kova(self, user):
        profile = user.profile
        profile.plan = "growth"
        profile.subscription_status = "active"
        profile.save(update_fields=["plan", "subscription_status"])

        assert maybe_grandfather_to_kova(profile, on_renewal=True) is True
        profile.refresh_from_db()
        assert profile.plan == "kova"
        assert profile.recurring_campaign_bonus >= 10

    def test_sync_clears_expired_burst(self, user):
        from django.utils import timezone
        from datetime import timedelta

        profile = user.profile
        profile.recurring_campaign_bonus = 10
        profile.burst_campaign_bonus = 5
        profile.burst_campaign_expires_at = timezone.now() - timedelta(hours=1)
        profile.seed_monthly_bonus = 15
        profile.save()

        result = sync_campaign_bonus_totals(profile, reason="test")
        profile.refresh_from_db()

        assert result["burst"] == 0
        assert profile.seed_monthly_bonus == 10


@pytest.mark.django_db
class TestStorefrontBusinessLayout:
    def test_service_layout_sections(self, user):
        from apps.products.storefront import resolve_business_layout, resolve_storefront

        user.profile.business_model = "service"
        user.profile.save(update_fields=["business_model"])

        layout = resolve_business_layout(user.profile)
        assert layout["business_model"] == "service"
        assert "services" in layout["section_order"]

        storefront = resolve_storefront(user.profile, user, [], [])
        assert storefront["catalog_label"] == "Our services"

    def test_portfolio_items_query(self, user):
        from apps.products.professional_assets import create_portfolio_item
        from apps.products.storefront import portfolio_items_for_shop

        create_portfolio_item(user, title="Brand refresh", client="Acme")
        items = portfolio_items_for_shop(user)
        assert len(items) == 1


@pytest.mark.django_db
class TestWhatsAppDraftActions:
    def test_pending_draft_count(self, user):
        from apps.platforms.models import SocialAccount
        from apps.whatsapp.draft_actions import pending_draft_count, reject_draft
        from apps.whatsapp.models import WhatsAppConversation, WhatsAppMessage

        account = SocialAccount.objects.create(
            user=user,
            platform="whatsapp",
            platform_user_id="biz123",
            access_token="tok",
            is_active=True,
        )
        convo = WhatsAppConversation.objects.create(
            social_account=account,
            contact_wa_id="254700000001",
            contact_name="Jane",
        )
        WhatsAppMessage.objects.create(
            conversation=convo,
            direction=WhatsAppMessage.Direction.OUTBOUND,
            message_type=WhatsAppMessage.MessageType.TEXT,
            content="Thanks for your interest!",
            status=WhatsAppMessage.MessageStatus.PENDING,
            is_ai_generated=True,
        )

        assert pending_draft_count(user) == 1
        ok, msg = reject_draft(user)
        assert ok is True
        assert pending_draft_count(user) == 0
