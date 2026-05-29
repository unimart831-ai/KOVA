"""Tests for Moment Mode pack pipeline."""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.calendar_intel.models import CustomEvent, HolidayDraft
from apps.calendar_intel.moment_pack_pipeline import build_moment_pack_status
from apps.content.models import Post
from apps.platforms.models import SocialAccount


@pytest.fixture
def user(db):
    return User.objects.create_user(username="moment", email="m@kova.ai", password="x")


@pytest.fixture
def draft(user):
    event = CustomEvent.objects.create(
        user=user,
        name="Founders Day",
        date=timezone.localdate() + timedelta(days=5),
    )
    return HolidayDraft.objects.create(
        user=user,
        custom_event=event,
        target_date=event.date,
        relevance_score=80,
        status=HolidayDraft.Status.DRAFTS_READY,
    )


class TestMomentPackPipeline:
    def test_ready_pack_status(self, user, draft):
        sa = SocialAccount.objects.create(
            user=user, platform="instagram", username="ig",
            platform_user_id="1", is_active=True,
        )
        post = Post.objects.create(
            user=user,
            social_account=sa,
            content_text="Celebrate Founders Day with us!",
            status=Post.Status.PENDING_APPROVAL,
        )
        draft.posts_generated.add(post)

        data = build_moment_pack_status(draft, user)
        assert data["status"] == "ready"
        assert data["terminal"] is True
        assert data["moment_name"] == "Founders Day"
        assert data["post_count"] == 1
        assert data["pending_count"] == 1

    def test_wrong_user_fails(self, user, draft):
        other = User.objects.create_user(username="other", email="o@kova.ai", password="x")
        data = build_moment_pack_status(draft, other)
        assert data["status"] == "failed"
