"""Tests for Daily Brief operations report."""

import pytest
from django.utils import timezone

from apps.create.agents.models import AgentAction
from apps.create.briefs.operations_report import build_operations_report, enrich_overnight_work


@pytest.mark.django_db
class TestOperationsReport:
    def test_empty_report(self, user):
        report = build_operations_report(user, hours=24)
        assert report["window_hours"] == 24
        assert report["categories"] == []
        assert report["has_activity"] is False

    def test_snap_actions_grouped(self, user):
        AgentAction.objects.create(
            user=user,
            agent_type="create",
            action_type="snap.vision",
            description="Snap to Sell vision analysis: Test Widget",
            status=AgentAction.ActionStatus.COMPLETED,
        )
        AgentAction.objects.create(
            user=user,
            agent_type="create",
            action_type="snap.reel",
            description="Auto-reel from Snap to Sell: Test Widget",
            status=AgentAction.ActionStatus.COMPLETED,
        )
        report = build_operations_report(user, hours=24)
        assert report["has_activity"] is True
        products = next(c for c in report["categories"] if c["id"] == "products")
        assert products["count"] >= 2
        labels = {i["label"] for i in products["items"]}
        assert "Snap to Sell" in labels
        assert "Motion reel" in labels

    def test_restock_action_grouped(self, user):
        AgentAction.objects.create(
            user=user,
            agent_type="analyst",
            action_type="receipt_to_restock",
            description="Receipt to Restock: 5 items, 3 updated",
            status=AgentAction.ActionStatus.COMPLETED,
        )
        report = build_operations_report(user, hours=24)
        inventory = next(c for c in report["categories"] if c["id"] == "inventory")
        assert inventory["count"] >= 1

    def test_enrich_overnight_work(self, user):
        AgentAction.objects.create(
            user=user,
            agent_type="create",
            action_type="snap.carousel",
            description="Carousel",
            status=AgentAction.ActionStatus.COMPLETED,
        )
        base = enrich_overnight_work(user, {"total_actions": 1})
        assert base["carousels_built"] == 1
