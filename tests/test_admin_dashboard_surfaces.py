from __future__ import annotations

from datetime import date

import pytest
from django.urls import reverse

from apps.analytics.models import PageView
from apps.briefs.models import DailyBrief
from apps.products.models import Product


@pytest.mark.django_db
class TestAdminDashboardSurfaces:
    @staticmethod
    def _activate_user(user):
        user.onboarding_completed = True
        user.phone_number = "0712345678"
        user.save(update_fields=["onboarding_completed", "phone_number"])

    def test_commerce_catalog_shows_mode_and_fulfillment_for_service_offer(self, client, staff_user, user):
        self._activate_user(user)
        profile = user.profile
        profile.industry = "consulting"
        profile.save(update_fields=["industry"])

        Product.objects.create(
            user=user,
            name="Strategy Session",
            offering_type=Product.OfferingType.SERVICE,
            fulfillment_url="https://cal.example.com/strategy",
        )

        client.force_login(staff_user)
        resp = client.get(reverse("admin_dashboard:commerce_catalog"))

        assert resp.status_code == 200
        assert b"Offer" in resp.content
        assert b"Service mode" in resp.content
        assert b"External booking ready" in resp.content

    def test_user_detail_profile_shows_offer_and_workspace_controls(self, client, staff_user, user):
        self._activate_user(user)
        profile = user.profile
        profile.industry = "saas"
        profile.key_offerings = ["Template Vault"]
        profile.save(update_fields=["industry", "key_offerings"])

        Product.objects.create(
            user=user,
            name="Template Vault",
            offering_type=Product.OfferingType.DIGITAL,
            fulfillment_url="https://example.com/access",
        )
        DailyBrief.objects.create(
            user=user,
            date=date.today(),
            summary="Summary",
            kova_score=70,
            kova_score_delta=1,
            performance_summary={"decisions_needed": []},
            overnight_work={"summary": "1 launch queued"},
        )

        client.force_login(staff_user)
        resp = client.get(reverse("admin_dashboard:user_detail", kwargs={"pk": user.pk}))

        assert resp.status_code == 200
        assert b"Digital mode" in resp.content
        assert b"Fulfillment Readiness" in resp.content
        assert b"Today & Workspace" in resp.content or b"Today &amp; Workspace" in resp.content

    def test_user_health_uses_booking_path_signal_for_service_users(self, client, staff_user, user):
        self._activate_user(user)
        profile = user.profile
        profile.industry = "consulting"
        profile.subscription_status = "trialing"
        profile.save(update_fields=["industry", "subscription_status"])

        Product.objects.create(
            user=user,
            name="Consulting Call",
            offering_type=Product.OfferingType.SERVICE,
        )

        client.force_login(staff_user)
        resp = client.get(reverse("admin_dashboard:user_health"))

        assert resp.status_code == 200
        assert b"Service mode" in resp.content
        assert b"No booking path" in resp.content
        assert b"booking-ready" in resp.content

    def test_surface_usage_uses_today_workspace_and_snap2sell_labels(self, client, staff_user, user):
        self._activate_user(user)
        PageView.objects.create(user=user, section="brief", path="/brief/")
        PageView.objects.create(user=user, section="command", path="/command/")
        PageView.objects.create(user=user, section="products", path="/products/")

        client.force_login(staff_user)
        resp = client.get(reverse("admin_dashboard:feature_usage"))

        assert resp.status_code == 200
        assert b"Surface Usage" in resp.content
        assert b"Today" in resp.content
        assert b"Workspace" in resp.content
        assert b"Snap2sell" in resp.content

    def test_overview_includes_platform_operations_hub(self, client, staff_user):
        client.force_login(staff_user)
        resp = client.get(reverse("admin_dashboard:overview"))

        assert resp.status_code == 200
        assert b"Platform Operations" in resp.content
        assert b"Plans & Billing" in resp.content
        assert b"Content Safety" in resp.content
        assert b"Marketplace Partners" in resp.content
