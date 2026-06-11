"""Tests for TEST_BUSINESSES pilot dashboard, metrics, and pilot_status command."""

from __future__ import annotations

from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import PilotMetricsSnapshot, User, UserProfile
from apps.accounts.pilot_metrics import compute_pilot_metrics, compute_pilot_readiness
from apps.accounts.tasks import snapshot_pilot_metrics
from apps.accounts.test_businesses import TEST_BUSINESS_REGISTRY, TEST_BUSINESS_SLUGS
from apps.leads.models import Lead
from apps.platforms.models import SocialAccount
from apps.products.models import Product


@pytest.mark.django_db
class TestPilotMetrics:
    def test_registry_has_14_slugs(self):
        assert len(TEST_BUSINESS_REGISTRY) == 14
        assert len(TEST_BUSINESS_SLUGS) == 14

    def test_compute_metrics_for_seeded_business(self):
        meta = TEST_BUSINESS_REGISTRY[0]  # mara
        user = User.objects.create_user(
            username=meta["slug"],
            email=meta["email"],
            password="TestPass123!",
            full_name="Mara Test",
        )
        user.onboarding_completed = True
        user.save(update_fields=["onboarding_completed"])
        UserProfile.objects.filter(user=user).update(plan="agency", company_name=meta["company_name"])

        SocialAccount.objects.create(
            user=user,
            platform="whatsapp",
            platform_user_id="wa-pilot",
            username="mara",
            access_token="tok",
            is_active=True,
        )
        Product.objects.create(user=user, name="Test Skirt", price_kes=2500)
        Lead.objects.create(user=user, email="lead@example.com")

        payload = compute_pilot_metrics()
        mara = next(b for b in payload["businesses"] if b["slug"] == "mara")

        assert mara["user_id"] == str(user.pk)
        assert mara["wedge"]["completed"] >= 2
        assert mara["leads_week"] >= 1
        assert payload["aggregate"]["seeded_test_businesses"] >= 1

    def test_persist_snapshot(self):
        payload = compute_pilot_metrics(persist_snapshot=True)
        snap = PilotMetricsSnapshot.objects.get(snapshot_date=timezone.now().date())
        assert snap.aggregate["total_test_businesses"] == 14
        assert len(snap.businesses) == 14
        assert snap.captured_at is not None

    def test_snapshot_task(self):
        result = snapshot_pilot_metrics()
        assert result["active_test_businesses"] >= 0
        assert PilotMetricsSnapshot.objects.exists()

    def test_readiness_not_seeded(self):
        meta = TEST_BUSINESS_REGISTRY[11]  # kawaida
        row = compute_pilot_readiness(meta, user=None)
        assert row["readiness"] == "not_seeded"
        assert row["seeded"] is False


@pytest.mark.django_db
class TestPilotDashboardViews:
    def test_pilot_overview_requires_staff(self, client, user):
        resp = client.get(reverse("admin_dashboard:pilot_overview"))
        assert resp.status_code in (302, 403)

    def test_pilot_overview_renders_for_staff(self, client, staff_user):
        client.force_login(staff_user)
        resp = client.get(reverse("admin_dashboard:pilot_overview"))
        assert resp.status_code == 200
        assert b"Pilot Dashboard" in resp.content or b"Per-business pilot cards" in resp.content
        assert b"Wedge checklist" in resp.content
        assert b"Active pilots" in resp.content

    def test_pilot_refresh_post(self, client, staff_user):
        client.force_login(staff_user)
        resp = client.post(reverse("admin_dashboard:pilot_overview"))
        assert resp.status_code == 302
        assert resp.url.endswith("/dashboard/pilot/")

    def test_overview_includes_pilot_summary(self, client, staff_user):
        client.force_login(staff_user)
        resp = client.get(reverse("admin_dashboard:overview"))
        assert resp.status_code == 200
        assert b"Test Business Pilot" in resp.content


@pytest.mark.django_db
class TestPilotStatusCommand:
    def test_pilot_status_lists_all_slugs(self):
        out = StringIO()
        call_command("pilot_status", stdout=out)
        output = out.getvalue()
        for slug in TEST_BUSINESS_SLUGS:
            assert slug in output
        assert "not_seeded" in output

    def test_pilot_status_wave1_filter(self):
        out = StringIO()
        call_command("pilot_status", "--wave1", stdout=out)
        output = out.getvalue()
        assert "kawaida" in output
        assert "mara" in output
        assert "nyama" in output
        assert "pixelcraft" not in output

    def test_pilot_status_json(self):
        out = StringIO()
        call_command("pilot_status", "--json", stdout=out)
        import json
        rows = json.loads(out.getvalue())
        assert len(rows) == 14
