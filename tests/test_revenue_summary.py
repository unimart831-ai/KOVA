"""Tests for unified revenue summary."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.models import User, UserProfile
from apps.briefs.revenue_summary import (
    format_money_whatsapp_message,
    get_unified_revenue_summary,
    recommend_next_revenue_action,
)
from apps.products.models import CommercePayment, Product


@pytest.fixture
def owner(db):
    u = User.objects.create_user(username="rev", email="rev@kova.ai", password="x")
    UserProfile.objects.filter(user=u).update(business_model="product", company_name="Rev Shop")
    return u


def test_unified_summary_includes_mpesa(owner):
    product = Product.objects.create(user=owner, name="Shirt", price=2000)
    CommercePayment.objects.create(
        user=owner,
        product=product,
        transaction_ref="rev-test-1",
        checkout_request_id="ws_rev_test_1",
        phone_number="254712345678",
        amount=Decimal("2000"),
        status=CommercePayment.Status.COMPLETED,
        completed_at=timezone.now(),
    )
    summary = get_unified_revenue_summary(owner)
    assert summary["mpesa_kes"] == 2000.0
    assert summary["total_kes"] >= 2000.0
    msg = format_money_whatsapp_message(summary)
    assert "Money this week" in msg
    assert "M-Pesa" in msg


def test_recommend_reply_when_inbox_busy():
    ops = {"needs_reply": 3, "ready_to_approve": 0, "hot_leads": 0}
    nba = recommend_next_revenue_action(owner=None, ops=ops, total_kes=1000)
    assert nba["key"] == "reply"
