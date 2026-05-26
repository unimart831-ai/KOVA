from __future__ import annotations

from datetime import date

import pytest
from django.urls import reverse

from apps.briefs.models import DailyBrief


@pytest.mark.django_db
class TestSegmentSpecificSurfaces:
    @staticmethod
    def _activate_user(user):
        user.onboarding_completed = True
        user.phone_number = "0712345678"
        user.save(update_fields=["onboarding_completed", "phone_number"])

    @staticmethod
    def _seed_brief(user, summary="Summary.\n\nYour move today: Launch a campaign."):
        DailyBrief.objects.create(
            user=user,
            date=date.today(),
            summary=summary,
            posts_pending=1,
            kova_score=61,
            kova_score_delta=2,
            performance_summary={"decisions_needed": []},
            overnight_work={"summary": "1 post drafted overnight"},
        )

    def test_command_home_adapts_for_expert_mode(self, client, user):
        self._activate_user(user)
        profile = user.profile
        profile.industry = "creator"
        profile.save(update_fields=["industry"])
        self._seed_brief(user)

        client.force_login(user)
        resp = client.get(reverse("command:home"))

        assert resp.status_code == 200
        assert b"Expert mode" in resp.content
        assert b"Operate your growth engine from one workspace" in resp.content
        assert b"visibility sprint" in resp.content

    def test_brief_home_adapts_for_digital_mode(self, client, user):
        self._activate_user(user)
        profile = user.profile
        profile.industry = "saas"
        profile.key_offerings = ["Course", "Template pack"]
        profile.save(update_fields=["industry", "key_offerings"])
        self._seed_brief(user)

        client.force_login(user)
        resp = client.get(reverse("brief:home"))

        assert resp.status_code == 200
        assert b"Digital mode" in resp.content
        assert b"Turn content into access and signups" in resp.content
        assert b"Launch from Workspace" in resp.content

    def test_offer_surface_adapts_for_service_mode(self, client, user):
        self._activate_user(user)
        profile = user.profile
        profile.industry = "consulting"
        profile.save(update_fields=["industry"])

        client.force_login(user)
        resp = client.get(reverse("products:list"))

        assert resp.status_code == 200
        assert b"Turn services into bookable offers" in resp.content
        assert b"Create Booking Page" in resp.content
