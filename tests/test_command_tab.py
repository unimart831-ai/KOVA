from __future__ import annotations

from datetime import date

import pytest
from django.urls import reverse

from apps.briefs.models import DailyBrief


@pytest.mark.django_db
class TestCommandTab:
    @staticmethod
    def _activate_user(user):
        user.onboarding_completed = True
        user.phone_number = "0712345678"
        user.save(update_fields=["onboarding_completed", "phone_number"])

    def test_command_overview_renders_hero_surface(self, client, user):
        self._activate_user(user)

        DailyBrief.objects.create(
            user=user,
            date=date.today(),
            summary="Summary.\n\nYour move today: Approve posts.",
            posts_pending=2,
            kova_score=65,
            kova_score_delta=3,
            performance_summary={"decisions_needed": []},
            overnight_work={"summary": "2 posts drafted overnight"},
        )

        client.force_login(user)
        resp = client.get(reverse("command:home"))

        assert resp.status_code == 200
        assert b"Command" in resp.content
        assert b"Morning Standup" in resp.content
        assert b"Listen &amp; Launch" in resp.content
        assert b"Hero Mode" in resp.content

    @pytest.mark.parametrize(
        ("url_name", "expected"),
        [
            ("command:standup", b"Decision queue"),
            ("command:moments", b"Approve a moment pack"),
            ("command:listen", b"What do you want to launch?"),
        ],
    )
    def test_command_subpages_render(self, client, user, url_name, expected):
        self._activate_user(user)
        client.force_login(user)

        resp = client.get(reverse(url_name))

        assert resp.status_code == 200
        assert expected in resp.content

    def test_prompt_launch_stays_in_listen(self, client, user, monkeypatch):
        self._activate_user(user)
        client.force_login(user)

        calls = []

        def fake_fire_task(*args):
            calls.append(args)

        monkeypatch.setattr("apps.command.views.fire_task", fake_fire_task)

        resp = client.post(
            reverse("command:listen"),
            {
                "action": "prompt",
                "prompt": "Launch our June offer this week",
                "duration_days": "7",
                "include_whatsapp_status": "on",
                "next": reverse("command:listen") + "#composer",
            },
            follow=False,
        )

        assert resp.status_code == 302
        assert resp["Location"].endswith("/command/listen/#composer")
        assert len(calls) == 1

    def test_layout_uses_social_first_navigation_groups(self, client, user):
        self._activate_user(user)
        client.force_login(user)

        resp = client.get(reverse("command:home"))

        assert resp.status_code == 200
        assert b'nav-section">Sell<' in resp.content
        assert b'nav-section">Catch<' in resp.content
        assert b'nav-section">Close<' in resp.content
        assert b'nav-section">Grow<' in resp.content
        assert b'nav-section">Settings<' in resp.content
        assert b'aria-label="Today"' in resp.content
        assert b'aria-label="Sell"' in resp.content
        assert b'aria-label="Catch"' in resp.content
        assert b'aria-label="Close"' in resp.content
        assert b'aria-label="Platforms"' in resp.content
        assert b'>Platforms<' in resp.content
