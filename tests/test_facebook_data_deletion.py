"""Tests for Meta Facebook data deletion callback and public pages."""

import base64
import hashlib
import hmac
import json

import pytest
from django.core.cache import cache
from django.test import Client, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.platforms.facebook_data_deletion import (
    delete_facebook_user_data,
    parse_signed_request,
    store_deletion_status,
)
from apps.platforms.models import SocialAccount


def _make_signed_request(payload: dict, app_secret: str) -> str:
    payload_b64 = (
        base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode())
        .decode()
        .rstrip("=")
    )
    sig = hmac.new(
        app_secret.encode(),
        payload_b64.encode(),
        hashlib.sha256,
    ).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).decode().rstrip("=")
    return f"{sig_b64}.{payload_b64}"


@pytest.fixture
def fb_user(db):
    user = User.objects.create_user(
        username="fbdeluser",
        email="fbdel@example.com",
        password="testpass123",
    )
    SocialAccount.objects.create(
        user=user,
        platform="facebook",
        platform_user_id="99887766",
        username="testpage",
        access_token="secret-token",
        metadata={"facebook_user_id": "99887766", "pages": [{"id": "p1"}]},
    )
    return user


@pytest.mark.django_db
class TestParseSignedRequest:
    def test_valid_request(self, settings):
        settings.FACEBOOK_APP_SECRET = "test-secret"
        signed = _make_signed_request({"user_id": "123"}, "test-secret")
        data = parse_signed_request(signed, "test-secret")
        assert data["user_id"] == "123"

    def test_invalid_signature(self):
        signed = _make_signed_request({"user_id": "123"}, "secret-a")
        with pytest.raises(Exception):
            parse_signed_request(signed, "secret-b")


@pytest.mark.django_db
class TestDeleteFacebookUserData:
    def test_scrubs_facebook_account(self, fb_user):
        counts = delete_facebook_user_data("99887766")
        assert counts["facebook_accounts"] == 1
        account = SocialAccount.objects.get(platform="facebook", user=fb_user)
        assert account.access_token == ""
        assert account.is_active is False
        assert "pages" not in (account.metadata or {})


@pytest.mark.django_db
class TestFacebookDataDeletionViews:
    def test_instructions_page(self, client):
        url = reverse("facebook_data_deletion")
        resp = client.get(url)
        assert resp.status_code == 200
        assert b"Remove the app in Facebook" in resp.content

    @override_settings(FACEBOOK_APP_SECRET="test-secret")
    def test_callback_returns_json(self, client, fb_user):
        signed = _make_signed_request({"user_id": "99887766"}, "test-secret")
        url = reverse("platforms:facebook_data_deletion_callback")
        resp = client.post(url, {"signed_request": signed})
        assert resp.status_code == 200
        data = resp.json()
        assert "confirmation_code" in data
        assert "url" in data
        assert data["confirmation_code"] in data["url"]

        account = SocialAccount.objects.get(platform="facebook", user=fb_user)
        assert account.access_token == ""

    @override_settings(FACEBOOK_APP_SECRET="test-secret")
    def test_status_page_after_callback(self, client, fb_user):
        signed = _make_signed_request({"user_id": "99887766"}, "test-secret")
        callback_url = reverse("platforms:facebook_data_deletion_callback")
        resp = client.post(callback_url, {"signed_request": signed})
        code = resp.json()["confirmation_code"]
        status_url = reverse("facebook_data_deletion_status", kwargs={"confirmation_code": code})
        status_resp = client.get(status_url)
        assert status_resp.status_code == 200
        assert b"Request completed" in status_resp.content

    def test_callback_rejects_bad_signature(self, client):
        with override_settings(FACEBOOK_APP_SECRET="test-secret"):
            url = reverse("platforms:facebook_data_deletion_callback")
            resp = client.post(url, {"signed_request": "bad.payload"})
            assert resp.status_code == 400

    def test_privacy_alias_redirects(self, client):
        resp = client.get(reverse("privacy_data_deletion"))
        assert resp.status_code == 302
        assert reverse("facebook_data_deletion") in resp["Location"]


@pytest.mark.django_db
def test_store_and_load_status():
    cache.clear()
    store_deletion_status(
        "abc123",
        facebook_user_id="99",
        counts={"facebook_accounts": 1},
    )
    from apps.platforms.facebook_data_deletion import get_deletion_status

    record = get_deletion_status("abc123")
    assert record["status"] == "completed"
    assert record["facebook_user_id"] == "99"
