"""Tests for public shop social link helpers."""

import pytest

from apps.platforms.models import SocialAccount
from apps.products.commerce_social import (
    get_public_social_links,
    normalize_whatsapp_number,
    platform_public_url,
    resolve_shop_whatsapp,
)


@pytest.mark.django_db
class TestCommerceSocialHelpers:
    def test_normalize_whatsapp_number(self):
        assert normalize_whatsapp_number("+254 712 345 678") == "254712345678"
        assert normalize_whatsapp_number("0712345678") == "254712345678"

    def test_resolve_shop_whatsapp_falls_back_to_signup_phone(self, user):
        user.phone_number = "0712345678"
        user.save(update_fields=["phone_number"])
        user.profile.cta_whatsapp = ""
        user.profile.save(update_fields=["cta_whatsapp"])
        assert resolve_shop_whatsapp(user.profile, user) == "254712345678"

    def test_resolve_shop_whatsapp_prefers_profile_cta(self, user):
        user.profile.cta_whatsapp = "254700111222"
        user.profile.save()
        assert resolve_shop_whatsapp(user.profile, user) == "254700111222"

    def test_platform_public_url_instagram(self):
        url = platform_public_url("instagram", "@myshop")
        assert url == "https://www.instagram.com/myshop/"

    def test_get_public_social_links_only_connected(self, user):
        user.profile.cta_whatsapp = "254712345678"
        user.profile.save()
        SocialAccount.objects.create(
            user=user,
            platform=SocialAccount.Platform.INSTAGRAM,
            platform_user_id="ig-1",
            username="myshop",
            is_active=True,
        )
        SocialAccount.objects.create(
            user=user,
            platform=SocialAccount.Platform.TIKTOK,
            platform_user_id="tt-1",
            username="myshop",
            is_active=False,
        )

        links = get_public_social_links(user, user.profile, wa_text="Hello")
        platforms = [link["platform"] for link in links]
        assert platforms[0] == "whatsapp"
        assert "instagram" in platforms
        assert "tiktok" not in platforms
        assert links[0]["url"].startswith("https://wa.me/254712345678")

    def test_public_shop_index_renders_social_nav(self, client, user):
        user.profile.page_slug = "social-shop"
        user.profile.company_name = "Social Shop"
        user.profile.cta_whatsapp = "254712345678"
        user.profile.save()
        SocialAccount.objects.create(
            user=user,
            platform=SocialAccount.Platform.INSTAGRAM,
            platform_user_id="ig-2",
            username="socialshop",
            is_active=True,
        )
        from apps.products.models import Product

        Product.objects.create(
            user=user,
            name="Social Item",
            price=500,
            commerce_slug="social-item",
            stock_status=Product.StockStatus.IN_STOCK,
        )

        from django.urls import reverse

        response = client.get(reverse("public_shop", kwargs={"page_slug": "social-shop"}))
        content = response.content.decode()
        assert response.status_code == 200
        assert "shop-top-nav" in content
        assert "shop-mobile-nav" in content
        assert "instagram.com/socialshop" in content
