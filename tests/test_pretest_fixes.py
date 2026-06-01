"""UNIMART partner slug resolution and Facebook page selection."""
from __future__ import annotations

import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.partners.models import MarketplacePartner, Partner
from apps.partners.unimart_partner import CANONICAL_UNIMART_SLUG, resolve_unimart_partner
from apps.platforms.models import SocialAccount


@pytest.mark.django_db
class TestUnimartPartnerResolver:
    def test_prefers_canonical_slug(self, user):
        legacy = Partner.objects.create(user=user, referral_code="KOVA-UNIMART-LEG")
        MarketplacePartner.objects.create(
            name="UNIMART legacy",
            slug="unimart",
            partner=legacy,
        )
        canonical_partner = Partner.objects.create(user=user, referral_code="KOVA-UNIMART-CAN")
        canonical = MarketplacePartner.objects.create(
            name="UNIMART Africa",
            slug=CANONICAL_UNIMART_SLUG,
            partner=canonical_partner,
        )
        assert resolve_unimart_partner() == canonical

    def test_falls_back_to_legacy_unimart(self, user):
        legacy = Partner.objects.create(user=user, referral_code="KOVA-UNIMART-ONLY")
        mp = MarketplacePartner.objects.create(
            name="UNIMART",
            slug="unimart",
            partner=legacy,
        )
        assert resolve_unimart_partner() == mp


@pytest.mark.django_db
class TestFacebookSelectPage:
    def test_user_can_switch_active_page(self, client, user):
        account = SocialAccount.objects.create(
            user=user,
            platform="facebook",
            platform_user_id="fb-user-1",
            username="testpage",
            access_token="token",
            is_active=True,
            metadata={
                "pages": [
                    {"id": "page1", "name": "Page One", "access_token": "t1"},
                    {"id": "page2", "name": "Page Two", "access_token": "t2"},
                ],
                "selected_page_id": "page1",
            },
        )
        client.force_login(user)
        url = reverse("platforms:facebook_select_page", kwargs={"pk": account.pk})
        resp = client.post(url, {"page_id": "page2"})
        assert resp.status_code == 302
        account.refresh_from_db()
        assert account.metadata["selected_page_id"] == "page2"
