"""Tests for profile audit routes (platforms page depends on these URLs)."""

from __future__ import annotations

import pytest
from django.urls import reverse

from apps.core.platforms.models import SocialAccount


@pytest.mark.django_db
def test_platforms_list_renders_with_facebook_account(client, user):
    user.onboarding_completed = True
    user.phone_number = "0712345678"
    user.save(update_fields=["onboarding_completed", "phone_number"])
    SocialAccount.objects.create(
        user=user,
        platform="facebook",
        username="demo_page",
        is_active=True,
    )
    client.force_login(user)
    resp = client.get(reverse("platforms:list"))
    assert resp.status_code == 200
    assert b"Profile audit runs tonight" in resp.content or b"demo_page" in resp.content


@pytest.mark.django_db
def test_profile_audit_list_requires_login(client):
    resp = client.get(reverse("profile_audit:list"))
    assert resp.status_code == 302


@pytest.mark.django_db
def test_profile_audit_list_and_detail(client, user):
    user.onboarding_completed = True
    user.phone_number = "0712345678"
    user.save(update_fields=["onboarding_completed", "phone_number"])
    account = SocialAccount.objects.create(
        user=user,
        platform="instagram",
        username="shop_ig",
        is_active=True,
    )
    client.force_login(user)
    list_resp = client.get(reverse("profile_audit:list"))
    assert list_resp.status_code == 200
    assert b"shop_ig" in list_resp.content

    detail_resp = client.get(reverse("profile_audit:detail", kwargs={"account_id": account.pk}))
    assert detail_resp.status_code == 200
    assert b"shop_ig" in detail_resp.content
