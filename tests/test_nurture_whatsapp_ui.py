"""Nurture sequence UI — WhatsApp step creation."""
from __future__ import annotations

import pytest
from django.urls import reverse

from apps.accounts.models import User, UserProfile
from apps.leads.models import NurtureSequence, NurtureStep


@pytest.fixture
def pro_user(db):
    u = User.objects.create_user(
        username="nurturepro",
        email="nurturepro@kova.ai",
        password="TestPass123!",
    )
    UserProfile.objects.filter(user=u).update(plan="pro", company_name="Pro Biz")
    u.onboarding_completed = True
    u.save(update_fields=["onboarding_completed"])
    return u


@pytest.fixture
def growth_user(db):
    u = User.objects.create_user(
        username="nurturegrowth",
        email="nurturegrowth@kova.ai",
        password="TestPass123!",
    )
    UserProfile.objects.filter(user=u).update(plan="growth", company_name="Growth Biz")
    u.onboarding_completed = True
    u.save(update_fields=["onboarding_completed"])
    return u


@pytest.mark.django_db
class TestNurtureWhatsAppUI:
    def test_pro_user_can_create_whatsapp_step(self, client, pro_user):
        client.force_login(pro_user)
        url = reverse("leads:nurture_create")
        resp = client.post(url, {
            "name": "WA follow-up",
            "trigger": "all_new",
            "step_count": 1,
            "step_0_delay": 1,
            "step_0_action": "send_whatsapp",
            "step_0_body": "Karibu! Reply if you need help.",
        })
        assert resp.status_code == 302
        seq = NurtureSequence.objects.get(user=pro_user, name="WA follow-up")
        step = seq.steps.get()
        assert step.action_type == NurtureStep.ActionType.SEND_WHATSAPP
        assert "Karibu" in step.email_body

    def test_growth_user_blocked_from_whatsapp_step(self, client, growth_user):
        client.force_login(growth_user)
        url = reverse("leads:nurture_create")
        resp = client.post(url, {
            "name": "Blocked WA",
            "trigger": "all_new",
            "step_count": 1,
            "step_0_delay": 1,
            "step_0_action": "send_whatsapp",
            "step_0_body": "Should not save",
        })
        assert resp.status_code == 302
        assert not NurtureSequence.objects.filter(user=growth_user, name="Blocked WA").exists()

    def test_form_shows_whatsapp_option_for_pro(self, client, pro_user):
        client.force_login(pro_user)
        resp = client.get(reverse("leads:nurture_create"))
        assert resp.status_code == 200
        assert b"send_whatsapp" in resp.content

    def test_form_hides_whatsapp_option_for_growth(self, client, growth_user):
        client.force_login(growth_user)
        resp = client.get(reverse("leads:nurture_create"))
        assert resp.status_code == 200
        assert b"send_whatsapp" not in resp.content
