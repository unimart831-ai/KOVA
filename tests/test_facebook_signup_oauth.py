"""Tests for Facebook signup/login via platform OAuth."""

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.facebook_oauth import (
    FacebookOAuthError,
    resolve_user_from_facebook_result,
    start_facebook_platform_oauth,
)
from apps.accounts.models import User
from apps.platforms.providers.base import OAuthResult


@pytest.fixture
def fb_result():
    return OAuthResult(
        platform_user_id="123456",
        username="jane",
        display_name="Jane Doe",
        avatar_url="https://example.com/pic.jpg",
        access_token="token",
        refresh_token="",
        token_expires_at=None,
        token_scope="email,public_profile",
        metadata={
            "email": "jane@example.com",
            "pages": [{"id": "page1", "name": "Jane Page", "access_token": "page_token"}],
            "selected_page_id": "page1",
        },
    )


@pytest.mark.django_db
class TestResolveUserFromFacebook:
    def test_signup_creates_user(self, fb_result):
        user, created = resolve_user_from_facebook_result(fb_result, mode="signup")
        assert created is True
        assert user.email == "jane@example.com"
        assert User.objects.filter(email="jane@example.com").exists()

    def test_signup_links_existing_email(self, fb_result):
        existing = User.objects.create_user(
            username="existing",
            email="jane@example.com",
            password="Pass1234!",
        )
        user, created = resolve_user_from_facebook_result(fb_result, mode="signup")
        assert created is False
        assert user.pk == existing.pk

    def test_login_requires_existing_user(self, fb_result):
        with pytest.raises(FacebookOAuthError):
            resolve_user_from_facebook_result(fb_result, mode="login")

    def test_login_finds_existing_user(self, fb_result):
        existing = User.objects.create_user(
            username="existing",
            email="jane@example.com",
            password="Pass1234!",
        )
        user, created = resolve_user_from_facebook_result(fb_result, mode="login")
        assert created is False
        assert user.pk == existing.pk

    def test_missing_email_raises(self):
        result = OAuthResult(
            platform_user_id="1",
            username="x",
            display_name="X",
            avatar_url="",
            access_token="t",
            refresh_token="",
            token_expires_at=None,
            token_scope="",
            metadata={},
        )
        with pytest.raises(FacebookOAuthError):
            resolve_user_from_facebook_result(result, mode="signup")


@pytest.mark.django_db
class TestFacebookSignupConnectView:
    def test_signup_connect_stores_mode_and_redirects(self, settings):
        settings.FACEBOOK_APP_ID = "app123"
        settings.FACEBOOK_APP_SECRET = "secret456"
        client = Client()
        resp = client.get(reverse("accounts:facebook_signup_connect"))
        assert resp.status_code == 302
        assert "facebook.com" in resp["Location"]
        assert client.session.get("oauth_facebook_mode") == "signup"
        assert client.session.get("oauth_state_facebook")

    def test_signup_connect_disabled_without_credentials(self, settings):
        settings.FACEBOOK_APP_ID = ""
        settings.FACEBOOK_APP_SECRET = ""
        client = Client()
        resp = client.get(reverse("accounts:facebook_signup_connect"), follow=False)
        assert resp.status_code == 302
        assert resp["Location"].endswith("/accounts/signup/")


@pytest.mark.django_db
def test_start_facebook_platform_oauth_login_mode(settings):
    settings.FACEBOOK_APP_ID = "app123"
    settings.FACEBOOK_APP_SECRET = "secret456"
    client = Client()
    request = client.get("/").wsgi_request
    request.session = client.session
    resp = start_facebook_platform_oauth(request, mode="login")
    assert resp.status_code == 302
    assert request.session.get("oauth_facebook_mode") == "login"
