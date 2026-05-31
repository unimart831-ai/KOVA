"""Shopify integration, agency white-label, and referral program tests."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.test import Client, override_settings
from django.urls import reverse

from apps.analytics.models import ShopifyStore
from apps.partners.models import Partner, PartnerApplication, PayoutRequest, ReferralClick
from apps.products.shopify_import import upsert_shopify_product
from apps.teams.models import Brand, Team, TeamMember


@pytest.fixture
def pro_user(db):
    from apps.accounts.models import User, UserProfile

    u = User.objects.create_user(
        username="shopifyuser",
        email="shopify@example.com",
        password="TestPass123!",
    )
    UserProfile.objects.filter(user=u).update(plan="pro")
    u.refresh_from_db()
    return u


@pytest.fixture
def shopify_store(pro_user):
    return ShopifyStore.objects.create(
        user=pro_user,
        shop_domain="test.myshopify.com",
        access_token="shpat_test_token",
        is_active=True,
    )


@pytest.fixture
def growth_partner(db, user):
    return Partner.objects.create(user=user, referral_code="KOVA-TEST-LINK")


@pytest.mark.django_db
class TestShopifyProductUpsert:
    def test_upsert_creates_product(self, shopify_store):
        item = {
            "id": 12345,
            "title": "Test Hoodie",
            "body_html": "<p>Soft cotton</p>",
            "handle": "test-hoodie",
            "status": "active",
            "variants": [{"price": "2500.00", "inventory_quantity": 10}],
            "images": [{"src": "https://cdn.shopify.com/hoodie.jpg"}],
        }
        pid, action = upsert_shopify_product(shopify_store, item)
        assert action == "created"
        assert pid is not None

        pid2, action2 = upsert_shopify_product(shopify_store, item)
        assert action2 == "updated"
        assert pid2 == pid

    @patch("apps.products.shopify_import.requests.get")
    def test_fetch_pagination(self, mock_get, shopify_store):
        from apps.products.shopify_import import fetch_shopify_products

        first = MagicMock()
        first.raise_for_status = MagicMock()
        first.json.return_value = {"products": [{"id": 1, "title": "A", "status": "active", "variants": []}]}
        first.headers = {"Link": '<https://test.myshopify.com/admin/api/next?page=2>; rel="next"'}

        second = MagicMock()
        second.raise_for_status = MagicMock()
        second.json.return_value = {"products": [{"id": 2, "title": "B", "status": "active", "variants": []}]}
        second.headers = {}

        mock_get.side_effect = [first, second]
        products, err = fetch_shopify_products(shopify_store)
        assert err is None
        assert len(products) == 2
        assert mock_get.call_count == 2


@pytest.mark.django_db
class TestReferralRedirect:
    def test_referral_redirect_logs_click_and_sets_cookie(self, growth_partner):
        client = Client()
        url = reverse("referral_redirect", kwargs={"referral_code": growth_partner.referral_code})
        resp = client.get(url)
        assert resp.status_code == 302
        assert ReferralClick.objects.filter(referral_code=growth_partner.referral_code).exists()
        assert resp.cookies.get("kova_ref").value == growth_partner.referral_code
        assert "utm_source=partner" in resp.url


@pytest.mark.django_db
class TestPayoutRequest:
    def test_partner_payout_minimum(self, growth_partner, auth_client):
        growth_partner.pending_payout_kes = Decimal("1000.00")
        growth_partner.save()
        growth_partner.user.set_password("TestPass123!")
        growth_partner.user.save()

        client = Client()
        client.force_login(growth_partner.user)
        resp = client.post(
            reverse("partners:payout_request"),
            {"mpesa_number": "254712345678", "amount_kes": "100"},
        )
        assert resp.status_code == 302
        assert PayoutRequest.objects.count() == 0

        resp = client.post(
            reverse("partners:payout_request"),
            {"mpesa_number": "254712345678", "amount_kes": "500"},
        )
        assert resp.status_code == 302
        assert PayoutRequest.objects.filter(partner=growth_partner, amount_kes=500).exists()


@pytest.mark.django_db
class TestCampusRepApproval:
    def test_campus_application_type(self, user):
        app = PartnerApplication.objects.create(
            user=user,
            full_name="Campus Rep",
            email=user.email,
            audience_description="Students at USIU",
            application_type=PartnerApplication.ApplicationType.CAMPUS_REP,
        )
        partner = Partner.objects.create(
            user=user,
            application=app,
            referral_code="KOVA-CAMPUS-TEST",
            application_type=app.application_type,
            commission_rate=Decimal("0.20"),
        )
        assert partner.application_type == "campus_rep"
        assert partner.commission_rate == Decimal("0.20")


@pytest.mark.django_db
class TestAgencyClientScope:
    def test_client_brand_scope_filters_posts(self, db):
        from apps.accounts.models import User, UserProfile
        from apps.content.models import Post
        from apps.teams.permissions import filter_posts_by_brand_scope, get_client_brand_scope

        owner = User.objects.create_user(username="agency", email="agency@example.com", password="x")
        client = User.objects.create_user(username="client", email="client@example.com", password="x")
        UserProfile.objects.filter(user=owner).update(plan="agency")

        team = Team.objects.create(name="Agency Co", slug="agency-co", owner=owner)
        brand_a = Brand.objects.create(team=team, name="Client A", slug="client-a")
        brand_b = Brand.objects.create(team=team, name="Client B", slug="client-b")
        TeamMember.objects.create(team=team, user=owner, role=TeamMember.Role.OWNER)
        TeamMember.objects.create(
            team=team, user=client, role=TeamMember.Role.CLIENT, brand=brand_a,
        )

        Post.objects.create(user=owner, brand=brand_a, content_text="Post A")
        Post.objects.create(user=owner, brand=brand_b, content_text="Post B")

        assert get_client_brand_scope(client) == brand_a.id
        scoped = filter_posts_by_brand_scope(
            Post.objects.filter(user_id__in=[owner.id]), client,
        )
        assert scoped.count() == 1
        assert scoped.first().content_text == "Post A"


@override_settings(SHOPIFY_API_KEY="test_key", SHOPIFY_API_SECRET="test_secret")
@pytest.mark.django_db
class TestShopifyOAuthConfigured:
    def test_shopify_configured_flag(self):
        from apps.analytics.shopify_oauth import shopify_configured

        assert shopify_configured() is True
