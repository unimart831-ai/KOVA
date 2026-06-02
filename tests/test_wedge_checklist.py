"""Tests for wedge onboarding checklist."""
from __future__ import annotations

import pytest

from apps.accounts.wedge_checklist import build_wedge_checklist
from apps.leads.models import Lead
from apps.platforms.models import SocialAccount
from apps.products.models import Product


@pytest.mark.django_db
class TestWedgeChecklist:
    def test_marks_whatsapp_step_complete(self, user):
        user.onboarding_completed = True
        user.save(update_fields=["onboarding_completed"])

        SocialAccount.objects.create(
            user=user,
            platform="whatsapp",
            platform_user_id="wa1",
            username="biz",
            access_token="tok",
            is_active=True,
        )

        checklist = build_wedge_checklist(user, stats={
            "has_whatsapp": True,
            "has_instagram": False,
            "has_snap_product": False,
            "has_publish_with_link": False,
            "has_automation_or_lead": False,
        })

        assert checklist is not None
        wa_item = next(i for i in checklist["items"] if i["key"] == "wedge_whatsapp")
        assert wa_item["done"] is True
        assert checklist["completed"] == 1

    def test_hides_when_all_steps_done(self, user):
        user.onboarding_completed = True
        user.save(update_fields=["onboarding_completed"])

        Lead.objects.create(user=user, email="done@example.com")

        checklist = build_wedge_checklist(user, stats={
            "has_whatsapp": True,
            "has_instagram": True,
            "has_snap_product": True,
            "has_publish_with_link": True,
            "has_automation_or_lead": True,
        })

        assert checklist is None

    def test_snap_step_detects_product(self, user):
        user.onboarding_completed = True
        user.save(update_fields=["onboarding_completed"])

        Product.objects.create(user=user, name="Test item", price_kes=500)

        checklist = build_wedge_checklist(user, stats={
            "has_whatsapp": False,
            "has_instagram": False,
            "has_snap_product": True,
            "has_publish_with_link": False,
            "has_automation_or_lead": False,
        })

        snap_item = next(i for i in checklist["items"] if i["key"] == "wedge_snap")
        assert snap_item["done"] is True
