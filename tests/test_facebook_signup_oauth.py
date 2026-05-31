"""Tests for Facebook signup/login via platform OAuth."""

from unittest.mock import patch

import pytest
from django.contrib.messages import get_messages
from django.test import Client
from django.urls import reverse

from apps.accounts.facebook_oauth import (
    FacebookOAuthError,
    make_facebook_oauth_state,
    resolve_user_from_facebook_result,
    sign_facebook_oauth_state,
    start_facebook_platform_oauth,
    validate_facebook_callback_state,
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
class TestFacebookOAuthState:
    def test_signed_state_roundtrip(self):
        nonce, signed = make_facebook_oauth_state("signup")
        assert nonce
        assert signed

    def test_validate_signed_state_without_session_nonce(self, rf):
        _, signed = make_facebook_oauth_state("login")
        request = rf.get("/platforms/callback/facebook/", {"state": signed})
        request.session = {}
        mode, err = validate_facebook_callback_state(request, signed)
        assert err is None
        assert mode == "login"


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
class TestFacebookLoginRoute:
    def test_login_route_redirects_to_meta_not_allauth_page(self, settings):
        settings.FACEBOOK_APP_ID = "app123"
        settings.FACEBOOK_APP_SECRET = "secret456"
        client = Client()
        resp = client.get(reverse("accounts:facebook_login_connect"))
        assert resp.status_code == 302
        assert "facebook.com" in resp["Location"]


@pytest.mark.django_db
class TestFacebookOAuthCallback:
    def _signed_state_from_session(self, client, mode: str = "signup") -> str:
        client.get(reverse("accounts:facebook_signup_connect"))
        nonce = client.session["oauth_state_facebook"]
        return sign_facebook_oauth_state(nonce, mode)

    @patch("apps.platforms.views.get_provider")
    def test_callback_success_signup_redirects_onboarding(self, mock_get_provider, settings, fb_result):
        settings.FACEBOOK_APP_ID = "app123"
        settings.FACEBOOK_APP_SECRET = "secret456"
        client = Client()
        signed_state = self._signed_state_from_session(client)

        mock_provider = mock_get_provider.return_value
        mock_provider.handle_callback.return_value = fb_result

        url = reverse("platforms:oauth_callback", kwargs={"platform": "facebook"})
        resp = client.get(url, {"code": "authcode", "state": signed_state})
        assert resp.status_code == 302
        assert "/accounts/onboarding/" in resp["Location"] or "phone" in resp["Location"]
        assert client.session.get("_auth_user_id")

    @patch("apps.platforms.views.get_provider")
    def test_callback_missing_email_shows_message_and_signup(
        self, mock_get_provider, settings,
    ):
        settings.FACEBOOK_APP_ID = "app123"
        settings.FACEBOOK_APP_SECRET = "secret456"
        client = Client()
        signed_state = self._signed_state_from_session(client)

        no_email = OAuthResult(
            platform_user_id="1",
            username="x",
            display_name="X",
            avatar_url="",
            access_token="t",
            refresh_token="",
            token_expires_at=None,
            token_scope="",
            metadata={"pages": []},
        )
        mock_provider = mock_get_provider.return_value
        mock_provider.handle_callback.return_value = no_email

        url = reverse("platforms:oauth_callback", kwargs={"platform": "facebook"})
        resp = client.get(url, {"code": "authcode", "state": signed_state}, follow=True)
        assert resp.status_code == 200
        assert resp.request["PATH_INFO"].endswith("/accounts/signup/")
        msgs = [str(m) for m in get_messages(resp.wsgi_request)]
        assert any("email" in m.lower() for m in msgs)
        assert not client.session.get("_auth_user_id")

    @patch("apps.platforms.views.get_provider")
    def test_callback_invalid_state_redirects_signup_with_message(
        self, mock_get_provider, settings,
    ):
        settings.FACEBOOK_APP_ID = "app123"
        settings.FACEBOOK_APP_SECRET = "secret456"
        client = Client()
        client.get(reverse("accounts:facebook_signup_connect"))

        url = reverse("platforms:oauth_callback", kwargs={"platform": "facebook"})
        resp = client.get(url, {"code": "authcode", "state": "bad-state"}, follow=True)
        assert resp.status_code == 200
        assert resp.request["PATH_INFO"].endswith("/accounts/signup/")
        msgs = [str(m) for m in get_messages(resp.wsgi_request)]
        assert any("state" in m.lower() or "oauth" in m.lower() for m in msgs)


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
