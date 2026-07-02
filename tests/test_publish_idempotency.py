"""Idempotency guards for content.publish_post.

Celery delivers tasks at-least-once, so the same publish_post message can be
redelivered after the platform API already accepted the post. These tests lock
in the two guards that prevent a post appearing twice on a customer's timeline:

  1. platform_post_id already set  → the post is already live; abort.
  2. compare-and-swap claim         → only one worker transitions
                                       APPROVED/SCHEDULED → PUBLISHING.
"""

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model

from apps.content.models import Post
from apps.content.tasks import publish_post
from apps.platforms.models import SocialAccount

User = get_user_model()


@pytest.fixture
def user(db):
    u = User.objects.create_user(username="idempo", email="idempo@example.com", password="Passw0rd!")
    u.onboarding_completed = True
    u.save(update_fields=["onboarding_completed"])
    return u


@pytest.fixture
def account(user):
    return SocialAccount.objects.create(
        user=user,
        platform="instagram",
        platform_user_id="ig_idempo",
        username="idempo_ig",
        access_token="tok",
        is_active=True,
    )


def _make_post(user, account, **overrides):
    defaults = dict(
        user=user,
        social_account=account,
        platform="instagram",
        content_text="Hello world",
        status=Post.Status.APPROVED,
        media_urls=["https://cdn.example.com/x.jpg"],
        media_status="generated",
    )
    defaults.update(overrides)
    return Post.objects.create(**defaults)


@pytest.mark.django_db
def test_already_published_post_is_not_republished(user, account):
    """A redelivered task for a post that already has a platform_post_id must
    abort before touching the provider and reconcile status to PUBLISHED."""
    post = _make_post(
        user,
        account,
        status=Post.Status.APPROVED,
        platform_post_id="ig_existing_123",
    )

    with patch("apps.platforms.providers.get_provider") as mock_get_provider:
        result = publish_post(str(post.pk))

    assert result == {"error": "already_published", "duplicate": True}
    # Provider was never fetched — we returned before any publish attempt.
    mock_get_provider.assert_not_called()

    post.refresh_from_db()
    assert post.status == Post.Status.PUBLISHED
    assert post.platform_post_id == "ig_existing_123"


@pytest.mark.django_db
def test_non_publishable_status_is_skipped(user, account):
    """A post already PUBLISHED (e.g. duplicate delivery) is skipped by the
    status guard — never published a second time."""
    post = _make_post(user, account, status=Post.Status.PUBLISHED)

    with patch("apps.platforms.providers.get_provider") as mock_get_provider:
        result = publish_post(str(post.pk))

    assert "error" in result
    mock_get_provider.assert_not_called()


@pytest.mark.django_db
def test_compare_and_swap_claim_is_atomic(user, account):
    """The claim only transitions APPROVED/SCHEDULED → PUBLISHING once.

    Simulate the losing worker in a race: once a post is no longer in a
    claimable state, the conditional UPDATE matches zero rows so a duplicate
    delivery cannot proceed to publish.
    """
    post = _make_post(user, account, status=Post.Status.APPROVED)

    # Worker A claims the post first.
    claimed = Post.objects.filter(
        pk=post.pk,
        status__in=(Post.Status.APPROVED, Post.Status.SCHEDULED),
    ).update(status=Post.Status.PUBLISHING)
    assert claimed == 1

    # Worker B (duplicate delivery) attempts the same claim — zero rows.
    lost = Post.objects.filter(
        pk=post.pk,
        status__in=(Post.Status.APPROVED, Post.Status.SCHEDULED),
    ).update(status=Post.Status.PUBLISHING)
    assert lost == 0

    # And publish_post refuses the already-claimed (PUBLISHING) post.
    with patch("apps.platforms.providers.get_provider") as mock_get_provider:
        result = publish_post(str(post.pk))
    assert "error" in result
    mock_get_provider.assert_not_called()
