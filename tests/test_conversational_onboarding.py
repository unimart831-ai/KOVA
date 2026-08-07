"""Conversational onboarding — the 3-question Brain builder + First Business Report.

Verifies the upgraded onboarding screen: the conversational answers build the
Business Brain, onboarding completes, and the completion screen surfaces the
First Business Report. Backward compatibility with the minimal payload is kept.
"""

import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


def _patch_async(monkeypatch):
    monkeypatch.setattr("apps.messaging.emails.tasks.send_welcome_email.delay", lambda pk: None)
    monkeypatch.setattr("apps.messaging.emails.automation.bootstrap_email_automation", lambda user: None)
    monkeypatch.setattr("apps.core.utils.fire_task", lambda task, pk: None)


def _user_with_phone(username, email):
    u = User.objects.create_user(username=username, email=email, password="P1!")
    u.phone_number = "0712345678"
    u.save(update_fields=["phone_number"])
    return u


@pytest.mark.django_db
class TestConversationalOnboarding:
    def test_conversational_answers_build_brain(self, client, monkeypatch):
        u = _user_with_phone("conv", "conv@b.com")
        client.force_login(u)
        _patch_async(monkeypatch)

        resp = client.post(
            "/accounts/onboarding/start/",
            {
                "company_name": "Braids by Mary",
                "brand_voice": "I run a small salon specializing in braids for university students.",
                "why_started": "I wanted affordable, quality hair care for students.",
                "success_vision": "Double my bookings and open a second branch.",
                "business_model": "service",
                "example_1": "New week, new glow!",
            },
            follow=False,
        )

        assert resp.status_code == 302
        assert "onboarding/complete" in resp.url
        u.refresh_from_db()
        p = u.profile
        assert u.onboarding_completed is True
        assert p.business_model == "service"
        assert p.founder_story.startswith("I wanted affordable")
        assert p.success_vision.startswith("Double my bookings")

    def test_completion_screen_shows_first_business_report(self, client, monkeypatch):
        u = _user_with_phone("convrep", "convrep@b.com")
        client.force_login(u)
        _patch_async(monkeypatch)

        client.post(
            "/accounts/onboarding/start/",
            {
                "company_name": "Braids by Mary",
                "brand_voice": "A small salon specializing in braids for university students.",
                "why_started": "Affordable, quality hair care for students.",
                "success_vision": "Double bookings.",
                "business_model": "service",
            },
            follow=False,
        )

        resp = client.get("/accounts/onboarding/complete/")
        assert resp.status_code == 200
        assert b"Business Assessment" in resp.content

    def test_backward_compatible_minimal_payload(self, client, monkeypatch):
        """The old payload without conversational fields still completes."""
        u = _user_with_phone("convmin", "convmin@b.com")
        client.force_login(u)
        _patch_async(monkeypatch)

        resp = client.post(
            "/accounts/onboarding/start/",
            {
                "company_name": "Glow Salon",
                "brand_voice": "Warm, friendly salon in Westlands. Short captions.",
                "example_1": "New week, new glow!",
            },
            follow=False,
        )

        assert resp.status_code == 302
        assert "onboarding/complete" in resp.url
        u.refresh_from_db()
        assert u.onboarding_completed is True
        assert u.profile.brand_voice.startswith("Warm")
