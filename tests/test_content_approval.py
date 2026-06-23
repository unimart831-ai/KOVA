"""Tests for post approval helpers."""
from __future__ import annotations

import pytest

from apps.accounts.models import User
from apps.content.approval import approve_pending_posts, reject_pending_posts
from apps.content.models import Post
from apps.platforms.models import SocialAccount


@pytest.fixture
def owner(db):
    return User.objects.create_user(
        username="owner", email="owner@kova.ai", password="x",
    )


@pytest.fixture
def social_account(owner):
    return SocialAccount.objects.create(
        user=owner, platform="instagram", username="shop",
        platform_user_id="ig1", is_active=True,
    )


def _pending_post(owner, social_account, text="Post one"):
    return Post.objects.create(
        user=owner,
        social_account=social_account,
        content_text=text,
        status=Post.Status.PENDING_APPROVAL,
    )


class TestRejectPendingPosts:
    def test_reject_first_by_index(self, owner, social_account):
        post = _pending_post(owner, social_account)
        result = reject_pending_posts(owner, indices=[1])
        assert result["rejected"] == 1
        post.refresh_from_db()
        assert post.status == Post.Status.REJECTED

    def test_reject_all(self, owner, social_account):
        p1 = _pending_post(owner, social_account, "One")
        p2 = _pending_post(owner, social_account, "Two")
        result = reject_pending_posts(owner, indices=None)
        assert result["rejected"] == 2
        p1.refresh_from_db()
        p2.refresh_from_db()
        assert p1.status == Post.Status.REJECTED
        assert p2.status == Post.Status.REJECTED

    def test_approve_still_works(self, owner, social_account):
        post = _pending_post(owner, social_account)
        result = approve_pending_posts(owner, indices=[1])
        assert result["approved"] == 1
        post.refresh_from_db()
        assert post.status == Post.Status.APPROVED
