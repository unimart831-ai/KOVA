"""Phase 2 score sprint — nav IA, outage hold, Engage WS, Teams Pro."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User, UserProfile
from apps.content.models import Post
from apps.engage.models import Interaction
from apps.platforms.models import SocialAccount
from apps.platforms.outage import record_failure


@pytest.fixture
def pro_user(db):
    u = User.objects.create_user(
        username="p2pro",
        email="p2pro@kova.ai",
        password="TestPass123!",
    )
    UserProfile.objects.filter(user=u).update(plan="pro")
    u.onboarding_completed = True
    u.save(update_fields=["onboarding_completed"])
    return u


@pytest.fixture
def starter_user(db, user):
    UserProfile.objects.filter(user=user).update(plan="starter")
    user.onboarding_completed = True
    user.save(update_fields=["onboarding_completed"])
    return user


@pytest.mark.django_db
class TestPhase2SidebarIA:
    def test_whatsapp_channels_in_subnav_for_pro(self, client, pro_user):
        SocialAccount.objects.create(
            user=pro_user,
            platform="whatsapp",
            platform_user_id="wa1",
            username="wa",
            access_token="tok",
            is_active=True,
        )
        client.force_login(pro_user)
        resp = client.get(reverse("whatsapp:inbox"))
        assert resp.status_code == 200
        assert b"Channels" in resp.content
        assert reverse("whatsapp:channel_dashboard").encode() in resp.content

    def test_workspace_hidden_for_starter(self, client, starter_user):
        client.force_login(starter_user)
        resp = client.get(reverse("brief:home"))
        assert resp.status_code == 200
        assert b"Workspace" not in resp.content

    def test_workspace_visible_for_pro(self, client, pro_user):
        client.force_login(pro_user)
        resp = client.get(reverse("brief:home"))
        assert resp.status_code == 200
        assert b"Workspace" in resp.content

    def test_teams_link_for_pro_with_cap(self, client, pro_user):
        client.force_login(pro_user)
        resp = client.get(reverse("accounts:settings"))
        assert resp.status_code == 200
        assert b"Teams" in resp.content
        assert b"(5 max)" in resp.content


@pytest.mark.django_db
class TestComingSoonPlatformsUI:
    def test_coming_soon_collapsed_by_default(self, client, pro_user):
        client.force_login(pro_user)
        resp = client.get(reverse("platforms:list"))
        assert resp.status_code == 200
        assert b"More platforms on the way" in resp.content
        assert b"showComingSoon" in resp.content


@pytest.mark.django_db
class TestOutageQueueHold:
    def test_check_and_publish_skips_outage_platform(self, user):
        from apps.content.tasks import check_and_publish_due_posts

        account = SocialAccount.objects.create(
            user=user,
            platform="facebook",
            platform_user_id="fb1",
            username="fb",
            access_token="tok",
            is_active=True,
        )
        Post.objects.create(
            user=user,
            social_account=account,
            platform="facebook",
            status=Post.Status.SCHEDULED,
            scheduled_at=timezone.now() - timedelta(minutes=5),
            content="Test",
        )
        cache.clear()
        for _ in range(3):
            record_failure("facebook")

        with patch("apps.content.tasks.publish_post.delay") as mock_delay:
            check_and_publish_due_posts()
            mock_delay.assert_not_called()


@pytest.mark.django_db
class TestEngageRealtime:
    def test_notify_engage_new_sends_ws(self, user):
        from apps.engage.realtime import notify_engage_new

        account = SocialAccount.objects.create(
            user=user,
            platform="instagram",
            platform_user_id="ig1",
            username="ig",
            access_token="tok",
            is_active=True,
        )
        interaction = Interaction.objects.create(
            user=user,
            social_account=account,
            interaction_type=Interaction.InteractionType.COMMENT,
            author_name="Fan",
            content="Price?",
            platform_interaction_id="c1",
        )
        with patch("apps.notifications.realtime.send_user_event") as mock_send:
            notify_engage_new(interaction)
            mock_send.assert_called_once()
            args = mock_send.call_args[0]
            assert args[1] == "engage_new"


@pytest.mark.django_db
class TestStarterTodayCompact:
    def test_starter_today_has_compact_section(self, client, starter_user):
        client.force_login(starter_user)
        resp = client.get(reverse("brief:home"))
        assert resp.status_code == 200
        assert b"Daily brief &amp; insights" in resp.content
        assert b"showMoreToday" in resp.content
