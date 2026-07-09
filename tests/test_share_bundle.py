"""Tests for Quick Share bundle workflows."""

from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.content.models import ContentSeed, Post
from apps.content.share_bundle import (
    apply_custom_order,
    campaign_rollout_minutes_for_post,
    create_share_bundle,
    parse_uploaded_files,
)


@pytest.fixture
def share_user(db, django_user_model):
    user = django_user_model.objects.create_user(
        username="sharetest",
        email="share@kova.ai",
        password="testpass123",
    )
    return user


@pytest.fixture
def ig_account(share_user):
    from apps.platforms.models import SocialAccount

    return SocialAccount.objects.create(
        user=share_user,
        platform="instagram",
        username="sharetest",
        is_active=True,
    )


def test_parse_uploaded_files_rejects_mixed_media():
    files = [
        SimpleUploadedFile("a.jpg", b"fake-image", content_type="image/jpeg"),
        SimpleUploadedFile("b.mp4", b"fake-video", content_type="video/mp4"),
    ]
    with pytest.raises(ValueError, match="Mix reels and photos"):
        parse_uploaded_files(files)


def test_apply_custom_order_reorders_items():
    items = parse_uploaded_files([
        SimpleUploadedFile("first.mp4", b"v1", content_type="video/mp4"),
        SimpleUploadedFile("second.mp4", b"v2", content_type="video/mp4"),
    ])
    reordered = apply_custom_order(items, ["2", "1"])
    assert reordered[0].filename == "second.mp4"
    assert reordered[0].order == 0


@pytest.mark.django_db
def test_create_share_bundle_multi_reel_with_order(share_user, ig_account, monkeypatch):
    monkeypatch.setattr(
        "apps.content.share_bundle._schedule_share_posts",
        lambda *a, **k: None,
    )
    items = parse_uploaded_files([
        SimpleUploadedFile("clip1.mp4", b"video-one-bytes", content_type="video/mp4"),
        SimpleUploadedFile("clip2.mp4", b"video-two-bytes-xx", content_type="video/mp4"),
    ])
    result = create_share_bundle(
        share_user,
        [ig_account],
        items,
        caption="Conference day 1",
        schedule_mode="manual",
    )
    assert result.posts_created == 2
    seed = ContentSeed.objects.get(pk=result.seed_id)
    assert seed.blueprint.get("share_kind") == "reel"
    posts = list(Post.objects.filter(seed=seed))
    posts.sort(key=lambda p: (p.content_dna or {}).get("publish_sequence_index", 0))
    assert len(posts) == 2
    assert posts[0].content_dna["publish_sequence_index"] == 0
    assert posts[1].content_dna["publish_sequence_index"] == 1
    assert posts[0].post_format == Post.PostFormat.REEL
    assert posts[0].visual_metadata.get("user_uploaded_reel") is True


@pytest.mark.django_db
def test_create_share_bundle_photo_carousel(share_user, ig_account, monkeypatch):
    monkeypatch.setattr(
        "apps.content.share_bundle._attach_image_to_post",
        lambda post, item, order=0: f"https://cdn.test/{item.order}.jpg",
    )
    monkeypatch.setattr(
        "apps.content.share_bundle._schedule_share_posts",
        lambda *a, **k: None,
    )
    items = parse_uploaded_files([
        SimpleUploadedFile("p1.jpg", b"img1", content_type="image/jpeg"),
        SimpleUploadedFile("p2.jpg", b"img2", content_type="image/jpeg"),
    ])
    result = create_share_bundle(
        share_user,
        [ig_account],
        items,
        caption="Event photos",
        photo_mode="carousel",
        schedule_mode="manual",
    )
    assert result.posts_created == 1
    post = Post.objects.get(seed_id=result.seed_id)
    assert post.post_format == Post.PostFormat.CAROUSEL
    assert len(post.carousel_slides) == 2


def test_campaign_rollout_minutes_respects_sequence():
    post = Post(
        platform="facebook",
        content_dna={"publish_sequence_index": 2, "share_bundle": True},
    )
    ig = Post(
        platform="instagram",
        content_dna={"publish_sequence_index": 2, "share_bundle": True},
    )
    assert campaign_rollout_minutes_for_post(ig) < campaign_rollout_minutes_for_post(post)
