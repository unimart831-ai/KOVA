"""Tests for Quick Share bundle workflows."""

from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.content.models import ContentSeed, Post
from apps.content.share_bundle import (
    apply_custom_order,
    campaign_rollout_minutes_for_post,
    create_share_bundle,
    infer_share_context,
    is_share_bundle_seed,
    is_meaningless_share_label,
    parse_uploaded_files,
    resolve_automated_share_options,
    summarize_share_bundle,
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


def test_infer_share_context_rejects_numeric_filename():
    items = parse_uploaded_files([
        SimpleUploadedFile("738389.jpg", b"img", content_type="image/jpeg"),
    ])
    ctx = infer_share_context(items)
    assert "738389" not in ctx
    assert "Shared" in ctx


def test_is_meaningless_share_label():
    from apps.content.share_bundle import is_meaningless_share_label

    assert is_meaningless_share_label("738389") is True
    assert is_meaningless_share_label("IMG_738389") is True
    assert is_meaningless_share_label("Nairobi Tech Week") is False


def test_human_share_title_from_numeric_seed(share_user, ig_account, monkeypatch):
    from apps.content.share_bundle import human_share_title

    monkeypatch.setattr(
        "apps.content.share_bundle._schedule_share_posts",
        lambda *a, **k: None,
    )
    items = parse_uploaded_files([
        SimpleUploadedFile("738389.jpg", b"1", content_type="image/jpeg"),
        SimpleUploadedFile("738390.jpg", b"2", content_type="image/jpeg"),
    ])
    result = create_share_bundle(
        share_user, [ig_account], items, schedule_mode="manual",
    )
    seed = ContentSeed.objects.get(pk=result.seed_id)
    posts = list(Post.objects.filter(seed=seed))
    title = human_share_title(seed, posts, user=share_user)
    assert "738389" not in title
    assert "carousel" in title.lower() or "photo" in title.lower() or "2" in title


def test_infer_share_context_from_filename():
    items = parse_uploaded_files([
        SimpleUploadedFile("nairobi_tech_week.jpg", b"img", content_type="image/jpeg"),
    ])
    ctx = infer_share_context(items)
    assert "Nairobi" in ctx or "nairobi" in ctx.lower()


def test_resolve_automated_share_options_hands_free(share_user, monkeypatch):
    monkeypatch.setattr(
        "apps.products.commerce_autopilot.should_auto_publish_commerce",
        lambda u: True,
    )
    items = parse_uploaded_files([
        SimpleUploadedFile("clip.mp4", b"v", content_type="video/mp4"),
    ])
    opts = resolve_automated_share_options(share_user, items)
    assert opts["schedule_mode"] == "autopilot"
    assert opts["generate_caption"] is True
    assert opts["photo_mode"] == "auto"


def test_is_share_bundle_seed():
    from apps.content.models import ContentSeed

    seed = ContentSeed(blueprint={"share_bundle": True})
    assert is_share_bundle_seed(seed) is True
    assert is_share_bundle_seed(ContentSeed(blueprint={})) is False


def test_summarize_share_bundle(share_user, ig_account, monkeypatch):
    monkeypatch.setattr(
        "apps.content.share_bundle.generate_share_caption",
        lambda *a, **k: "Caption",
    )
    items = parse_uploaded_files([
        SimpleUploadedFile("a.jpg", b"1", content_type="image/jpeg"),
    ])
    result = create_share_bundle(
        share_user, [ig_account], items, caption="Event", schedule_mode="manual",
    )
    seed = ContentSeed.objects.get(pk=result.seed_id)
    posts = list(Post.objects.filter(seed=seed))
    summary = summarize_share_bundle(seed, posts)
    assert summary["share_kind"] == "photo"
    assert summary["post_count"] == 1
    assert summary["needs_attention"] is True
