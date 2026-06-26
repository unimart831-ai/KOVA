"""Tests for post approval helpers."""
from __future__ import annotations

import pytest

from apps.accounts.models import User
from apps.content.approval import (
    approve_pending_posts,
    reject_pending_posts,
    republish_post_for_user,
)
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


class TestRepublishPostForUser:
    def test_republish_approved_clears_errors(self, owner, social_account):
        post = Post.objects.create(
            user=owner,
            social_account=social_account,
            content_text="Approved post",
            status=Post.Status.APPROVED,
            publish_error="old error",
            ai_reasoning="QA GATE (80/100): weak CTA",
        )
        result = republish_post_for_user(
            owner, post, schedule_intent="quick:1hr",
        )
        assert result["success"] is True
        assert result["published_now"] is False
        post.refresh_from_db()
        assert post.status == Post.Status.APPROVED
        assert post.publish_error == ""
        assert post.ai_reasoning == ""
        assert post.scheduled_at is not None

    def test_republish_failed_post_now(self, owner, social_account, monkeypatch):
        post = Post.objects.create(
            user=owner,
            social_account=social_account,
            content_text="Failed post",
            status=Post.Status.FAILED,
            publish_error="Provider error",
        )
        calls = []
        monkeypatch.setattr(
            "apps.utils.fire_task",
            lambda task, *args: calls.append((task, args)),
        )
        result = republish_post_for_user(owner, post, schedule_intent="post_now")
        assert result["success"] is True
        assert result["published_now"] is True
        assert len(calls) == 1
        post.refresh_from_db()
        assert post.status == Post.Status.APPROVED
        assert post.publish_error == ""

    def test_republish_rejects_published(self, owner, social_account):
        post = Post.objects.create(
            user=owner,
            social_account=social_account,
            content_text="Live post",
            status=Post.Status.PUBLISHED,
        )
        result = republish_post_for_user(owner, post)
        assert result["success"] is False
        assert result["error"] == "invalid_status"
