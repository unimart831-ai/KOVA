"""Tests for Commerce Autopilot helpers."""

import pytest

from apps.content.models import Post
from apps.products.commerce_autopilot import (
    apply_ai_detected_product_fields,
    commerce_autopilot_active,
    initial_commerce_post_status,
    is_placeholder_product_name,
    placeholder_name_for_offering,
    should_auto_publish_commerce,
)
from apps.products.models import Product


@pytest.mark.django_db
class TestCommerceAutopilotHelpers:
    def test_commerce_autopilot_respects_emergency_pause(self, user):
        user.profile.commerce_autopilot = True
        user.profile.emergency_pause = True
        user.profile.save()
        assert commerce_autopilot_active(user) is False

    def test_should_auto_publish_commerce(self, user):
        user.profile.commerce_autopilot = False
        user.profile.auto_approve_posts = False
        user.profile.save()
        assert should_auto_publish_commerce(user) is False

        user.profile.commerce_autopilot = True
        user.profile.save()
        assert should_auto_publish_commerce(user) is True

    def test_placeholder_name_for_offering(self):
        assert placeholder_name_for_offering("service") == "New service"
        assert placeholder_name_for_offering("product") == "New product"

    def test_is_placeholder_product_name(self):
        assert is_placeholder_product_name("New product") is True
        assert is_placeholder_product_name("Handmade Bag") is False
        assert is_placeholder_product_name("Product 3") is True

    def test_apply_ai_detected_name_only(self, user):
        product = Product.objects.create(
            user=user,
            name="New product",
            price=1000,
            source=Product.Source.SNAP,
        )
        apply_ai_detected_product_fields(
            product,
            {"detected_name": "Leather Tote", "detected_price": 4500},
        )
        product.refresh_from_db()
        assert product.name == "Leather Tote"
        assert product.price == 1000

    def test_initial_commerce_post_status(self, user):
        user.profile.commerce_autopilot = True
        user.profile.save()
        assert initial_commerce_post_status(user) == Post.Status.APPROVED

        user.profile.commerce_autopilot = False
        user.profile.save()
        assert initial_commerce_post_status(user) == Post.Status.PENDING_APPROVAL
