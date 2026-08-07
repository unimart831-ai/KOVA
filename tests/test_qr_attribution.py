"""Tests for the QR / walk-in attribution app (Phase 2 W5-6).

Covers:
  * Model invariants (token auto-gen + uniqueness)
  * Public scan landing (cookie set, scan recorded, all 5 templates render)
  * User-side CRUD (list, create, detail, soft-delete)
  * Cashier UI (public read, POST recording, visitor_id → scan linkage)
  * Revenue rollup (walk-ins merge into get_revenue_summary)
  * Access control (other user can't see your QR)
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.accounts.models import User, UserProfile
from apps.commerce.qr_attribution.models import QRCode, QRScan, WalkInEvent


# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture
def owner(db):
    u = User.objects.create_user(
        username="salonowner",
        email="owner@kova.ai",
        password="OwnerPass123!",
        full_name="Salon Owner",
    )
    UserProfile.objects.filter(user=u).update(
        plan="growth", company_name="Test Salon",
    )
    u.onboarding_completed = True
    u.phone_number = "+254712345678"
    u.save(update_fields=["onboarding_completed", "phone_number"])
    return u


@pytest.fixture
def other_owner(db):
    u = User.objects.create_user(
        username="otherowner",
        email="other@kova.ai",
        password="OtherPass123!",
        full_name="Other Owner",
    )
    u.onboarding_completed = True
    u.phone_number = "+254798765432"
    u.save(update_fields=["onboarding_completed", "phone_number"])
    return u


@pytest.fixture
def owner_client(client, owner):
    client.login(email="owner@kova.ai", password="OwnerPass123!")
    return client


@pytest.fixture
def discount_qr(owner):
    return QRCode.objects.create(
        user=owner,
        label="Jamhuri flyer",
        landing_template=QRCode.LandingTemplate.DISCOUNT,
        landing_payload={"discount_pct": 15, "terms": "One per customer"},
    )


# ── Model invariants ───────────────────────────────────────────────────────


class TestQRCodeModel:
    def test_token_auto_generated_on_save(self, owner):
        qr = QRCode.objects.create(user=owner, label="Auto token")
        assert qr.token
        assert len(qr.token) == 10

    def test_tokens_are_unique(self, owner):
        a = QRCode.objects.create(user=owner, label="A")
        b = QRCode.objects.create(user=owner, label="B")
        assert a.token != b.token

    def test_str_includes_label_and_token(self, discount_qr):
        s = str(discount_qr)
        assert "Jamhuri flyer" in s
        assert discount_qr.token in s


# ── Public scan landing ────────────────────────────────────────────────────


class TestScanLanding:
    def test_landing_renders_and_records_scan(self, client, discount_qr):
        url = reverse("qr_attribution:scan_landing", kwargs={"token": discount_qr.token})
        resp = client.get(url)
        assert resp.status_code == 200
        assert discount_qr.scans.count() == 1

    def test_landing_sets_visitor_cookie(self, client, discount_qr):
        url = reverse("qr_attribution:scan_landing", kwargs={"token": discount_qr.token})
        resp = client.get(url)
        assert "kova_visitor_id" in resp.cookies
        assert resp.cookies["kova_visitor_id"].value

    def test_landing_404_for_inactive_qr(self, client, discount_qr):
        discount_qr.is_active = False
        discount_qr.save(update_fields=["is_active"])
        url = reverse("qr_attribution:scan_landing", kwargs={"token": discount_qr.token})
        assert client.get(url).status_code == 404

    @pytest.mark.parametrize("template,payload", [
        ("discount", {"discount_pct": 10, "terms": "T&Cs"}),
        ("menu", {"menu_image_url": "https://x/m.jpg", "today_special": "Pilau"}),
        ("booking", {"booking_link": "https://cal.com/x", "contact_whatsapp": "254712345678"}),
        ("follow", {"instagram_handle": "kova", "facebook_url": "https://fb.com/kova"}),
        ("custom", {"headline": "Hi", "body": "Hello", "cta_text": "Go", "cta_url": "https://x"}),
    ])
    def test_all_five_landing_templates_render(self, client, owner, template, payload):
        qr = QRCode.objects.create(
            user=owner, label=f"{template} test",
            landing_template=template, landing_payload=payload,
        )
        url = reverse("qr_attribution:scan_landing", kwargs={"token": qr.token})
        assert client.get(url).status_code == 200


# ── User-side QR management ────────────────────────────────────────────────


class TestQRListView:
    def test_requires_login(self, client):
        resp = client.get(reverse("qr_attribution:list"))
        assert resp.status_code in (302, 401)

    def test_shows_user_qrs_only(self, owner_client, owner, other_owner, discount_qr):
        QRCode.objects.create(user=other_owner, label="Other's QR")
        resp = owner_client.get(reverse("qr_attribution:list"))
        assert resp.status_code == 200
        assert b"Jamhuri flyer" in resp.content
        assert b"Other's QR" not in resp.content


class TestQRCreateView:
    def test_get_renders_form(self, owner_client):
        resp = owner_client.get(reverse("qr_attribution:create"))
        assert resp.status_code == 200

    def test_post_creates_discount_qr(self, owner_client, owner):
        resp = owner_client.post(reverse("qr_attribution:create"), {
            "label": "Door sticker",
            "landing_template": "discount",
            "discount_pct": "20",
            "terms": "Braids only",
        })
        assert resp.status_code == 302
        qr = QRCode.objects.get(user=owner, label="Door sticker")
        assert qr.landing_payload["discount_pct"] == 20
        assert qr.landing_payload["terms"] == "Braids only"

    def test_post_without_label_errors(self, owner_client):
        resp = owner_client.post(reverse("qr_attribution:create"), {
            "label": "",
            "landing_template": "discount",
        })
        # Redirect back to create with a flash message
        assert resp.status_code == 302
        assert QRCode.objects.filter(label="").count() == 0


class TestQRDetailView:
    def test_owner_can_view(self, owner_client, discount_qr):
        url = reverse("qr_attribution:detail", kwargs={"pk": discount_qr.pk})
        resp = owner_client.get(url)
        assert resp.status_code == 200
        assert discount_qr.label.encode() in resp.content

    def test_other_user_cannot_view(self, client, other_owner, discount_qr):
        client.login(email="other@kova.ai", password="OtherPass123!")
        url = reverse("qr_attribution:detail", kwargs={"pk": discount_qr.pk})
        assert client.get(url).status_code == 404


class TestQREditView:
    def test_owner_can_edit(self, owner_client, discount_qr):
        url = reverse("qr_attribution:edit", kwargs={"pk": discount_qr.pk})
        resp = owner_client.get(url)
        assert resp.status_code == 200
        assert discount_qr.label.encode() in resp.content

    def test_post_updates_label(self, owner_client, discount_qr):
        url = reverse("qr_attribution:edit", kwargs={"pk": discount_qr.pk})
        resp = owner_client.post(url, {
            "label": "Updated flyer",
            "landing_template": "discount",
            "discount_pct": "20",
        })
        assert resp.status_code == 302
        discount_qr.refresh_from_db()
        assert discount_qr.label == "Updated flyer"
        assert discount_qr.landing_payload["discount_pct"] == 20


class TestQRDeleteView:
    def test_soft_delete_marks_inactive(self, owner_client, discount_qr):
        url = reverse("qr_attribution:delete", kwargs={"pk": discount_qr.pk})
        owner_client.post(url)
        discount_qr.refresh_from_db()
        assert discount_qr.is_active is False

    def test_scans_preserved_after_archive(self, owner_client, discount_qr):
        QRScan.objects.create(qr_code=discount_qr, visitor_id="v1")
        url = reverse("qr_attribution:delete", kwargs={"pk": discount_qr.pk})
        owner_client.post(url)
        assert discount_qr.scans.count() == 1


# ── Cashier UI ─────────────────────────────────────────────────────────────


class TestCashierUI:
    def test_cashier_view_is_public(self, client, owner):
        url = reverse("qr_attribution:cashier_view", kwargs={"slug": owner.username})
        resp = client.get(url)
        assert resp.status_code == 200
        assert b"Where did you hear" in resp.content

    def test_cashier_record_creates_walkin(self, client, owner):
        url = reverse("qr_attribution:cashier_record", kwargs={"slug": owner.username})
        resp = client.post(url, {"source": "instagram", "revenue": "3500"})
        assert resp.status_code in (200, 302)
        w = WalkInEvent.objects.get(user=owner)
        assert w.attribution_source == "instagram"
        assert w.revenue == Decimal("3500.00")

    def test_cashier_record_xhr_returns_json(self, client, owner):
        url = reverse("qr_attribution:cashier_record", kwargs={"slug": owner.username})
        resp = client.post(url, {"source": "facebook"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_visitor_cookie_links_walkin_to_scan(self, client, owner, discount_qr):
        # 1. Customer scans the QR — cookie gets set
        scan_url = reverse("qr_attribution:scan_landing", kwargs={"token": discount_qr.token})
        client.get(scan_url)
        # 2. Within 30 min, cashier records a walk-in from the same browser
        record_url = reverse("qr_attribution:cashier_record", kwargs={"slug": owner.username})
        client.post(record_url, {"source": "flyer"})
        w = WalkInEvent.objects.get(user=owner)
        assert w.scan is not None
        assert w.qr_code == discount_qr

    def test_old_scan_does_not_link(self, client, owner, discount_qr):
        old_scan = QRScan.objects.create(
            qr_code=discount_qr, visitor_id="oldvis",
        )
        QRScan.objects.filter(pk=old_scan.pk).update(
            scanned_at=timezone.now() - timedelta(hours=2),
        )
        client.cookies["kova_visitor_id"] = "oldvis"
        url = reverse("qr_attribution:cashier_record", kwargs={"slug": owner.username})
        client.post(url, {"source": "instagram"})
        w = WalkInEvent.objects.get(user=owner)
        assert w.scan is None


# ── Revenue rollup ─────────────────────────────────────────────────────────


class TestRevenueRollup:
    def test_walkin_revenue_appears_in_summary(self, owner):
        WalkInEvent.objects.create(
            user=owner, attribution_source="instagram", revenue=Decimal("5000"),
        )
        WalkInEvent.objects.create(
            user=owner, attribution_source="flyer", revenue=Decimal("1500"),
        )
        from apps.insight.analytics.revenue import get_revenue_summary
        summary = get_revenue_summary(owner, days=30)
        assert summary["totals"]["walkin_revenue"] == Decimal("6500")
        assert summary["totals"]["walkin_count"] == 2
        assert summary["totals"]["total_revenue"] == Decimal("6500")

    def test_walkin_revenue_merges_into_platform_revenue(self, owner):
        WalkInEvent.objects.create(
            user=owner, attribution_source="instagram", revenue=Decimal("4000"),
        )
        from apps.insight.analytics.revenue import get_revenue_summary
        summary = get_revenue_summary(owner, days=30)
        ig_row = next(
            (r for r in summary["platform_revenue"]
             if r.get("social_account__platform") == "instagram"), None,
        )
        assert ig_row is not None
        assert ig_row["revenue"] == Decimal("4000")

    def test_offline_source_not_in_platform_revenue(self, owner):
        WalkInEvent.objects.create(
            user=owner, attribution_source="word_of_mouth", revenue=Decimal("2000"),
        )
        from apps.insight.analytics.revenue import get_revenue_summary
        summary = get_revenue_summary(owner, days=30)
        # Doesn't pollute platform_revenue — but DOES show in walkin_by_source
        assert all(
            r.get("social_account__platform") != "word_of_mouth"
            for r in summary["platform_revenue"]
        )
        sources = {r["attribution_source"] for r in summary["walkin_by_source"]}
        assert "word_of_mouth" in sources
