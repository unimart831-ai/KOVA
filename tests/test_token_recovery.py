"""Tests for Facebook/Instagram token recovery."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

from apps.platforms.models import SocialAccount
from apps.platforms.token_recovery import try_recover_meta_token


@pytest.fixture
def facebook_account(django_user_model):
    user = django_user_model.objects.create_user(
        email="fbrecovery@test.com",
        username="fbrecovery",
        password="testpass123",
    )
    return SocialAccount.objects.create(
        user=user,
        platform="facebook",
        platform_user_id="fb123",
        username="testpage",
        access_token="old-user-token",
        is_active=False,
        metadata={
            "pages": [{"id": "page1", "name": "Test Page", "access_token": "stale-page-token"}],
            "selected_page_id": "page1",
            "consecutive_errors": 3,
        },
    )


@patch("apps.platforms.providers.instagram_facebook.refresh_facebook_page_tokens")
@patch("apps.platforms.providers.registry.get_provider")
def test_try_recover_meta_token_reactivates_account(
    mock_get_provider, mock_refresh_pages, facebook_account,
):
    provider = MagicMock()
    mock_get_provider.return_value = provider
    expires_at = timezone.now() + timedelta(days=60)
    provider.refresh_access_token.return_value = {
        "access_token": "new-user-token",
        "expires_at": expires_at,
    }
    mock_refresh_pages.return_value = [
        {"id": "page1", "name": "Test Page", "access_token": "fresh-page-token"},
    ]

    assert try_recover_meta_token(facebook_account) is True

    facebook_account.refresh_from_db()
    assert facebook_account.is_active is True
    assert facebook_account.access_token == "new-user-token"
    assert facebook_account.metadata["consecutive_errors"] == 0
    assert facebook_account.metadata["pages"][0]["access_token"] == "fresh-page-token"
    assert facebook_account.last_error == ""
