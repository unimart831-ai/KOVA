"""Fast CI smoke tests for the WhatsApp-first core loop."""

from __future__ import annotations

import pytest
from django.urls import reverse

pytestmark = pytest.mark.smoke


class TestCriticalRoutes:
    def test_core_urls_resolve(self):
        names = [
            "brief:home",
            "products:snap",
            "bookings:list",
            "api:asset-list",
            "whatsapp:webhook",
        ]
        for name in names:
            assert reverse(name)


class TestBlueprintPipeline:
    def test_attach_blueprint_to_seed(self, db):
        from apps.accounts.models import User
        from apps.content.blueprint_pipeline import attach_blueprint_to_seed, blueprint_prompt_section
        from apps.content.models import ContentSeed
        from apps.products.models import BusinessAsset, Product

        user = User.objects.create_user(username="smoke", email="smoke@kova.ai", password="x")
        product = Product.objects.create(
            user=user,
            name="Haircut",
            offering_type=Product.OfferingType.SERVICE,
            price=1500,
            currency="KES",
        )
        asset = BusinessAsset.objects.create(
            user=user,
            asset_type=BusinessAsset.AssetType.SERVICE,
            title="Haircut",
            product=product,
            metadata={"price": "1500", "currency": "KES", "duration_minutes": 45},
        )
        seed = ContentSeed.objects.create(user=user, product=product, idea="Promote haircut")
        data = attach_blueprint_to_seed(seed, asset=asset, platforms=["instagram", "facebook"])
        assert data["objective"] == "book"
        assert "instagram" in {p["platform"] for p in data["platforms"]}
        seed.refresh_from_db()
        assert seed.blueprint["asset_id"] == str(asset.id)
        assert "CONTENT BLUEPRINT" in blueprint_prompt_section(seed.blueprint)


class TestServiceBookingSetup:
    def test_ensure_booking_link_for_service_business(self, db):
        from apps.accounts.models import User, UserProfile
        from apps.bookings.models import BookingLink
        from apps.bookings.service_setup import ensure_primary_booking_link, sync_service_asset_to_booking_link
        from apps.products.models import BusinessAsset

        user = User.objects.create_user(
            username="salon", email="salon@kova.ai", password="x", phone_number="0711222333",
        )
        UserProfile.objects.filter(user=user).update(
            company_name="Glow Salon", business_model="service",
        )
        link = ensure_primary_booking_link(user)
        assert link.slug
        assert link.working_hours

        asset = BusinessAsset.objects.create(
            user=user,
            asset_type=BusinessAsset.AssetType.SERVICE,
            title="Box braids",
            metadata={"price": "3500", "duration_minutes": 180},
        )
        sync_service_asset_to_booking_link(user, asset)
        link.refresh_from_db()
        assert any(s["name"] == "Box braids" for s in link.services)
        assert BookingLink.objects.filter(user=user).count() == 1
