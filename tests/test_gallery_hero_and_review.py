"""Tests for P0-1 gallery hero picker and P0-5 review approve/reject filtering."""

import pytest
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.agents.models import AgentAction
from apps.products.gallery_preferences import (
    build_gallery_scenes,
    set_hero_image,
    set_scene_included,
    set_variant_review_status,
)
from apps.products.models import Product
from apps.products.photoroom_review import summarize_review_state


def _studio_url(product_id, variant="studio_white", suffix="abc123"):
    return f"/media/studio_polish/{product_id}/{variant}_{suffix}.jpg"


def _ghost_url(product_id, suffix="def456"):
    return _studio_url(product_id, "ghost_mannequin", suffix)


@pytest.fixture
def product_with_scenes(db, user):
    pid = "11111111-1111-1111-1111-111111111111"
    product = Product.objects.create(
        id=pid,
        user=user,
        name="Gallery Test Dress",
        additional_images=[
            _studio_url(pid, "studio_white"),
            _ghost_url(pid),
            _studio_url(pid, "ai_scene_table", "ghi789"),
        ],
    )
    product.image = "product_images/original.jpg"
    product.save()
    return product


def _polish_action(user, product, url, variant, *, needs_review=False, review_status=""):
    out = {
        "variant": variant,
        "label": variant.replace("_", " ").title(),
        "url": url,
        "slide_role": "hero" if variant == "studio_white" else "desire",
        "phase": "scene",
    }
    if needs_review:
        out.update({
            "needs_review": True,
            "review_before_publish": True,
            "review_reason": variant,
            "review_status": review_status or "pending",
        })
    AgentAction.objects.create(
        user=user,
        agent_type="create",
        action_type="commerce.studio_polish",
        description="test polish",
        status=AgentAction.ActionStatus.COMPLETED,
        input_data={"product_id": str(product.pk)},
        output_data=out,
        completed_at=timezone.now(),
    )


import pytest


def test_set_hero_image_orders_carousel_first(db, product_with_scenes):
    product = product_with_scenes
    hero = _studio_url(str(product.pk), "ai_scene_table", "ghi789")
    set_hero_image(product, hero)
    product.refresh_from_db()

    assert product.all_image_urls[0] == hero
    assert product.shop_hero_image_url == hero


def test_exclude_scene_from_carousel_and_shop(db, product_with_scenes):
    product = product_with_scenes
    hidden = _studio_url(str(product.pk), "studio_white")
    set_scene_included(product, hidden, included=False)
    product.refresh_from_db()

    assert hidden not in product.all_image_urls
    assert hidden not in product.carousel_image_urls
    assert hidden not in product.shop_gallery_urls


def test_rejected_variant_excluded_from_gallery(db, user):
    pid = "22222222-2222-2222-2222-222222222222"
    ghost = _ghost_url(pid)
    product = Product.objects.create(
        id=pid,
        user=user,
        name="Review Test",
        additional_images=[_studio_url(pid), ghost],
    )
    _polish_action(user, product, _studio_url(pid), "studio_white")
    _polish_action(user, product, ghost, "ghost_mannequin", needs_review=True)

    assert ghost not in product.all_image_urls

    set_variant_review_status(product, ghost, "rejected")
    product.refresh_from_db()
    assert ghost not in product.all_image_urls


def test_pending_review_excluded_until_approved(db, user):
    pid = "33333333-3333-3333-3333-333333333333"
    ghost = _ghost_url(pid)
    product = Product.objects.create(
        id=pid,
        user=user,
        name="Pending Review",
        additional_images=[ghost],
    )
    _polish_action(user, product, ghost, "ghost_mannequin", needs_review=True)

    assert ghost not in product.all_image_urls

    set_variant_review_status(product, ghost, "approved")
    product.refresh_from_db()
    assert ghost in product.all_image_urls


@override_settings(PHOTOROOM_REVIEW_ALTERATIONS=True)
def test_summarize_review_state_skips_approved_and_rejected(db, user):
    pid = "44444444-4444-4444-4444-444444444444"
    product = Product.objects.create(
        id=pid,
        user=user,
        name="Summary Test",
        additional_images=[_ghost_url(pid)],
    )
    _polish_action(user, product, _ghost_url(pid), "ghost_mannequin", needs_review=True)
    actions = list(AgentAction.objects.filter(input_data__product_id=str(product.pk)))
    state = summarize_review_state(actions)
    assert state["review_pending_count"] == 1

    set_variant_review_status(product, _ghost_url(pid), "approved")
    actions = list(AgentAction.objects.filter(input_data__product_id=str(product.pk)))
    state = summarize_review_state(actions)
    assert state["review_pending_count"] == 0


def test_build_gallery_scenes_marks_hero_and_review(db, user, product_with_scenes):
    product = product_with_scenes
    _polish_action(user, product, _studio_url(str(product.pk)), "studio_white")
    _polish_action(
        user, product, _ghost_url(str(product.pk)), "ghost_mannequin", needs_review=True,
    )
    scenes = build_gallery_scenes(product)
    assert any(s["is_original"] for s in scenes)
    assert any(s["needs_review"] for s in scenes)
    assert any(s["is_hero"] for s in scenes)


def test_set_gallery_hero_view(auth_client, product_with_scenes):
    product = product_with_scenes
    hero = _studio_url(str(product.pk), "ai_scene_table", "ghi789")
    url = reverse("products:set_gallery_hero", kwargs={"product_id": product.pk})
    response = auth_client.post(url, {"image_url": hero})
    assert response.status_code == 302
    product.refresh_from_db()
    assert product.gallery_preferences.get("hero_image_url") == hero


def test_toggle_gallery_scene_view(auth_client, product_with_scenes):
    product = product_with_scenes
    hidden = _studio_url(str(product.pk), "studio_white")
    url = reverse("products:toggle_gallery_scene", kwargs={"product_id": product.pk})
    response = auth_client.post(url, {"image_url": hidden, "included": "0"})
    assert response.status_code == 302
    product.refresh_from_db()
    assert hidden in (product.gallery_preferences.get("excluded_urls") or [])


@override_settings(PHOTOROOM_REVIEW_ALTERATIONS=True)
def test_review_variant_approve_view(auth_client, user):
    pid = "55555555-5555-5555-5555-555555555555"
    ghost = _ghost_url(pid)
    product = Product.objects.create(
        id=pid,
        user=user,
        name="Approve View",
        additional_images=[ghost],
    )
    _polish_action(user, product, ghost, "ghost_mannequin", needs_review=True)

    url = reverse("products:review_variant", kwargs={"product_id": product.pk})
    response = auth_client.post(url, {"image_url": ghost, "decision": "approve"})
    assert response.status_code == 302
    product.refresh_from_db()
    assert ghost in product.all_image_urls


@override_settings(PHOTOROOM_REVIEW_ALTERATIONS=True)
def test_snap_pipeline_gates_carousel_on_pending_review(db, user):
    from apps.products.snap_pipeline import build_snap_pipeline_status

    pid = "66666666-6666-6666-6666-666666666666"
    ghost = _ghost_url(pid)
    product = Product.objects.create(
        id=pid,
        user=user,
        name="Pipeline Gate",
        additional_images=[_studio_url(pid), ghost],
    )
    product.image = "product_images/orig.jpg"
    product.save()
    _polish_action(user, product, _studio_url(pid), "studio_white")
    _polish_action(user, product, ghost, "ghost_mannequin", needs_review=True)

    AgentAction.objects.create(
        user=user,
        agent_type="create",
        action_type="snap.vision",
        description="vision",
        status=AgentAction.ActionStatus.COMPLETED,
        input_data={"product_id": str(product.pk)},
        output_data={},
        completed_at=timezone.now(),
    )

    status = build_snap_pipeline_status(product, user)
    carousel_step = next(s for s in status["steps"] if s["id"] == "carousel")
    assert carousel_step["status"] == "pending"
    assert "review" in carousel_step["detail"].lower()
