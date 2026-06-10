"""Phase 4 score sprint — Messenger webhook, Create nav, Celery ops, CSP."""

from __future__ import annotations

import hashlib
import hmac
import json
from unittest.mock import patch

import pytest
from django.test import Client, override_settings
from django.urls import reverse

from apps.accounts.models import User, UserProfile
from apps.engage.models import Interaction
from apps.platforms.models import SocialAccount


@pytest.fixture
def pro_user(db):
    u = User.objects.create_user(
        username="p4pro",
        email="p4pro@kova.ai",
        password="TestPass123!",
    )
    UserProfile.objects.filter(user=u).update(plan="pro")
    u.onboarding_completed = True
    u.save(update_fields=["onboarding_completed"])
    return u


@pytest.fixture
def fb_account(pro_user):
    return SocialAccount.objects.create(
        user=pro_user,
        platform="facebook",
        platform_user_id="fb-user-1",
        username="mybiz",
        access_token="page-token",
        is_active=True,
        metadata={
            "selected_page_id": "123456789",
            "pages": [{"id": "123456789", "name": "My Biz", "access_token": "page-token"}],
        },
    )


def _sign_payload(payload: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


@pytest.mark.django_db
class TestMessengerWebhook:
    @override_settings(WHATSAPP_VERIFY_TOKEN="verify-me")
    def test_get_verification_challenge(self, client):
        resp = client.get(
            reverse("engage:messenger_webhook"),
            {
                "hub.mode": "subscribe",
                "hub.verify_token": "verify-me",
                "hub.challenge": "challenge-abc",
            },
        )
        assert resp.status_code == 200
        assert resp.content.decode() == "challenge-abc"

    @override_settings(
        DEBUG=False,
        FACEBOOK_APP_SECRET="testsecret",
        WHATSAPP_VERIFY_TOKEN="verify-me",
    )
    def test_post_creates_interaction_and_ws(self, client, fb_account):
        payload = {
            "object": "page",
            "entry": [{
                "id": "123456789",
                "messaging": [{
                    "sender": {"id": "987654321"},
                    "recipient": {"id": "123456789"},
                    "timestamp": 1234567890,
                    "message": {
                        "mid": "m_test123",
                        "text": "How much for delivery?",
                    },
                }],
            }],
        }
        body = json.dumps(payload).encode()
        signature = _sign_payload(body, "testsecret")

        with patch("apps.engage.realtime.notify_engage_new") as mock_ws:
            resp = client.post(
                reverse("engage:messenger_webhook"),
                data=body,
                content_type="application/json",
                HTTP_X_HUB_SIGNATURE_256=signature,
            )

        assert resp.status_code == 200
        interaction = Interaction.objects.get(platform_interaction_id="m_test123")
        assert interaction.platform == "facebook"
        assert interaction.interaction_type == Interaction.InteractionType.DM
        assert "delivery" in interaction.content
        mock_ws.assert_called_once()

    @override_settings(DEBUG=False, FACEBOOK_APP_SECRET="testsecret")
    def test_post_rejects_missing_signature(self, client):
        resp = client.post(
            reverse("engage:messenger_webhook"),
            data=b'{"object":"page","entry":[]}',
            content_type="application/json",
        )
        assert resp.status_code == 403


@pytest.mark.django_db
class TestCreateNavMerge:
    def test_sidebar_shows_create_not_separate_studio_queue(self, client, pro_user):
        client.force_login(pro_user)
        resp = client.get(reverse("content:studio"))
        assert resp.status_code == 200
        content = resp.content.decode()
        assert "Create" in content
        assert "Studio" in content
        assert "Queue" in content

    def test_create_redirects_to_studio(self, client, pro_user):
        client.force_login(pro_user)
        resp = client.get(reverse("content:create"))
        assert resp.status_code == 302
        assert reverse("content:studio") in resp.url

    def test_queue_page_has_create_tabs(self, client, pro_user):
        client.force_login(pro_user)
        resp = client.get(reverse("content:queue"))
        assert resp.status_code == 200
        assert b"subnav-tabs" in resp.content


@pytest.mark.django_db
class TestCeleryOpsPanel:
    def test_staff_can_view_celery_health(self, client, staff_user):
        client.force_login(staff_user)
        resp = client.get(reverse("admin_dashboard:ops_celery"))
        assert resp.status_code == 200
        assert b"Daily briefs" in resp.content
        assert b"Publish due posts" in resp.content
        assert b"Engage cycle" in resp.content
        assert b"WhatsApp follow-up" in resp.content
        assert b"Money board digest" in resp.content

    def test_non_staff_denied(self, client, pro_user):
        client.force_login(pro_user)
        resp = client.get(reverse("admin_dashboard:ops_celery"))
        assert resp.status_code in (302, 403)
