"""Tests for Listen & Launch cross-channel campaign builder."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from apps.accounts.models import User, UserProfile
from apps.campaigns.tasks import build_campaign_from_prompt, _create_status_updates_from_plan
from apps.platforms.models import SocialAccount


@pytest.fixture
def user(db):
    u = User.objects.create_user(username="launch", email="launch@kova.ai", password="x")
    UserProfile.objects.filter(user=u).update(company_name="Test Co")
    return u


@pytest.fixture
def platforms(user):
    SocialAccount.objects.create(
        user=user, platform="instagram", username="ig",
        platform_user_id="1", is_active=True,
    )
    SocialAccount.objects.create(
        user=user, platform="facebook", username="fb",
        platform_user_id="2", is_active=True,
    )


class TestListenAndLaunch:
    @patch("apps.content.tasks.generate_from_seed")
    @patch("apps.campaigns.tasks._generate_campaign_plan")
    def test_include_status_creates_status_content(self, mock_plan, _gen, user, platforms):
        mock_plan.return_value = {
            "name": "Launch Week",
            "description": "New menu launch",
            "objective": "engagement",
            "key_message": "Try our new menu!",
            "include_whatsapp_status": True,
            "status_updates": [
                {"text": "New menu drops today!", "category": "announcement", "day": 1},
            ],
            "seeds": [{"idea": "Menu teaser", "platforms": ["instagram"], "day": 1}],
        }

        result = build_campaign_from_prompt(
            user, "Launch menu with WhatsApp Status", include_status=True, auto_generate=False,
        )
        assert result["status_count"] == 1
        assert len(result["status_ids"]) == 1

    def test_create_status_fallback_from_key_message(self, user, platforms):
        from datetime import date

        from apps.campaigns.models import Campaign

        campaign = Campaign.objects.create(
            user=user,
            name="Test",
            description="Special offer this week",
            objective="engagement",
            start_date=date.today(),
            end_date=date.today(),
        )
        plan = {"key_message": "50% off today only", "description": "Special offer"}
        ids = _create_status_updates_from_plan(user, campaign, plan, 7)
        assert len(ids) >= 1
