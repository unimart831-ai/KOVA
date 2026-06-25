"""Tests for canonical commerce URLs and shop / Kova Page unification."""

import pytest
from django.urls import reverse

from apps.links.models import KovaLink, KovaPage
from apps.products.commerce_canonical import (
    build_unified_shop_footer,
    canonical_shop_path,
    canonical_shop_url,
    commerce_shop_redirect_path,
    user_has_commerce_shop,
)
from apps.products.models import Product


@pytest.fixture
def product(user):
    return Product.objects.create(
        user=user,
        name="Shop Item",
        price=1000,
        currency="KES",
        is_active=True,
        commerce_slug="shop-item",
    )


@pytest.fixture
def kova_page(user):
    return KovaPage.objects.create(
        user=user,
        title="My Brand",
        slug="my-brand",
        bio="We sell great things.",
        is_published=True,
    )


@pytest.mark.django_db
class TestCanonicalShop:
    def test_user_has_commerce_shop(self, user, product):
        assert user_has_commerce_shop(user) is True

    def test_canonical_path_uses_page_slug(self, user):
        user.profile.page_slug = "nairobi-bags"
        user.profile.save(update_fields=["page_slug"])
        assert canonical_shop_path(user.profile) == "/shop/nairobi-bags/"

    def test_kova_redirect_when_shop_live(self, user, product, kova_page):
        path = commerce_shop_redirect_path(kova_page)
        assert path is not None
        assert path.startswith("/shop/")


@pytest.mark.django_db
class TestKovaPageRedirect:
    def test_public_page_redirects_to_shop(self, client, user, product, kova_page):
        resp = client.get(reverse("public_page", kwargs={"slug": kova_page.slug}))
        assert resp.status_code == 301
        assert "/shop/" in resp.url

    def test_legacy_param_shows_kova_page(self, client, user, product, kova_page):
        url = reverse("public_page", kwargs={"slug": kova_page.slug}) + "?legacy=1"
        resp = client.get(url)
        assert resp.status_code == 200
        assert b"My Brand" in resp.content


@pytest.mark.django_db
class TestUnifiedShopFooter:
    def test_merges_kova_links(self, user, product, kova_page):
        KovaLink.objects.create(
            page=kova_page,
            title="Our Blog",
            url="https://example.com/blog",
            link_type=KovaLink.LinkType.URL,
            is_active=True,
        )
        footer = build_unified_shop_footer(user.profile, user)
        assert footer["has_kova_extras"] is True
        assert len(footer["kova_links"]) == 1
        assert footer["canonical_shop_url"].endswith("/")
