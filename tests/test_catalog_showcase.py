"""Tests for catalog showcase (multi-product carousel + reel)."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import UserProfile
from apps.platforms.models import SocialAccount
from apps.products.catalog_showcase import (
    select_products_for_showcase,
    weekly_showcase_due,
)
from apps.products.models import Product


@pytest.fixture
def ig(user):
    return SocialAccount.objects.create(
        user=user,
        platform="instagram",
        platform_user_id="ig1",
        username="shop",
        is_active=True,
    )


@pytest.mark.django_db
class TestCatalogShowcaseSelection:
    def test_excludes_out_of_stock_physical(self, user):
        Product.objects.create(
            user=user,
            name="Available",
            price=100,
            stock_status=Product.StockStatus.IN_STOCK,
        )
        Product.objects.create(
            user=user,
            name="Gone",
            price=50,
            stock_status=Product.StockStatus.OUT_OF_STOCK,
        )
        selected = select_products_for_showcase(user)
        names = {p.name for p in selected}
        assert "Available" in names
        assert "Gone" not in names

    def test_includes_services_without_stock(self, user):
        Product.objects.create(
            user=user,
            name="Consult",
            price=5000,
            offering_type=Product.OfferingType.SERVICE,
            stock_status=Product.StockStatus.UNLIMITED,
        )
        selected = select_products_for_showcase(user)
        assert len(selected) == 1
        assert selected[0].name == "Consult"

    def test_rotation_when_many_products(self, user):
        for i in range(12):
            Product.objects.create(
                user=user,
                name=f"Item {i}",
                price=100 + i,
                stock_status=Product.StockStatus.IN_STOCK,
            )
        batch_a = select_products_for_showcase(user)
        assert len(batch_a) == 8


@pytest.mark.django_db
class TestWeeklyShowcaseDue:
    def test_due_when_never_run(self, user):
        profile = UserProfile.objects.get(user=user)
        profile.catalog_showcase_weekly = True
        profile.catalog_showcase_last_at = None
        profile.save()
        assert weekly_showcase_due(profile) is True

    def test_not_due_within_seven_days(self, user):
        profile = UserProfile.objects.get(user=user)
        profile.catalog_showcase_weekly = True
        profile.catalog_showcase_last_at = timezone.now() - timedelta(days=2)
        profile.save()
        assert weekly_showcase_due(profile) is False

    def test_due_after_seven_days(self, user):
        profile = UserProfile.objects.get(user=user)
        profile.catalog_showcase_weekly = True
        profile.catalog_showcase_last_at = timezone.now() - timedelta(days=8)
        profile.save()
        assert weekly_showcase_due(profile) is True

    def test_disabled_when_opted_out(self, user):
        profile = UserProfile.objects.get(user=user)
        profile.catalog_showcase_weekly = False
        profile.catalog_showcase_last_at = None
        profile.save()
        assert weekly_showcase_due(profile) is False
