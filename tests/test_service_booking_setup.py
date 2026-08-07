"""Tests for service-business booking auto-setup."""

from __future__ import annotations

import pytest

from apps.core.accounts.models import User, UserProfile
from apps.core.accounts.onboarding_express import apply_business_model_defaults, record_business_model
from apps.commerce.bookings.models import BookingLink
from apps.commerce.bookings.service_setup import sync_product_service_to_booking
from apps.commerce.products.business_assets import sync_asset_from_product
from apps.commerce.products.models import Product


@pytest.fixture
def service_user(db):
    user = User.objects.create_user(username="svc", email="svc@kova.ai", password="x")
    profile = user.profile
    record_business_model(profile, "service")
    return user


class TestServiceOnboardingBooking:
    def test_apply_defaults_creates_booking_link(self, service_user):
        apply_business_model_defaults(service_user.profile, service_user)
        assert BookingLink.objects.filter(user=service_user, is_active=True).exists()

    def test_service_product_syncs_to_booking(self, service_user):
        product = Product.objects.create(
            user=service_user,
            name="Manicure",
            offering_type=Product.OfferingType.SERVICE,
            price=1200,
            currency="KES",
        )
        sync_asset_from_product(product)
        link = sync_product_service_to_booking(service_user, product)
        assert link is not None
        assert any(s["name"] == "Manicure" for s in link.services)
