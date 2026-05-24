"""Tests for visual credit metering and Photoroom studio polish."""

import pytest

from apps.agents.models import AgentAction
from apps.billing.visual_credits import (
    STUDIO_POLISH_ACTION,
    check_visual_credit_limit,
    get_platform_photoroom_usage,
    get_visual_credit_usage,
    record_studio_polish,
)
from apps.products.photoroom import pick_background_color_hex


@pytest.mark.django_db
class TestVisualCredits:
    def test_starter_limit_is_fifteen(self, user):
        usage = get_visual_credit_usage(user)
        assert usage["max"] == 15
        assert usage["remaining"] == 15
        assert not usage["at_limit"]

    def test_blocks_at_cap(self, user):
        for i in range(15):
            record_studio_polish(user, product_id=f"p{i}", provider="photoroom")

        usage = get_visual_credit_usage(user)
        assert usage["at_limit"]
        allowed, msg = check_visual_credit_limit(user)
        assert not allowed
        assert "15" in msg

    def test_record_creates_agent_action(self, user):
        record_studio_polish(user, product_id="abc", provider="photoroom", output_data={"url": "x"})
        assert AgentAction.objects.filter(user=user, action_type=STUDIO_POLISH_ACTION).count() == 1

    def test_platform_pool_tracks_usage(self, user):
        record_studio_polish(user, product_id="abc", provider="photoroom")
        pool = get_platform_photoroom_usage()
        assert pool["used"] >= 1
        assert pool["pool"] == 5000
        assert pool["usable"] == 4500


class TestStudioBackground:
    def test_beauty_product_gets_light_blue(self):
        class P:
            name = "Neutrogeno Hand Cream"
            tags = ["beauty", "skincare"]

        assert pick_background_color_hex(P()) == "E8F4FC"

    def test_luxury_product_gets_dark(self):
        class P:
            name = "Gold Luxury Watch"
            tags = ["premium"]

        assert pick_background_color_hex(P()) == "1A1A2E"

    def test_default_is_white(self):
        class P:
            name = "Generic Widget"
            tags = []

        assert pick_background_color_hex(P()) == "FFFFFF"
