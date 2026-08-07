"""Tests for SMM WhatsApp commands."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from apps.create.briefs.smm_commands import (
    PROMO_PRESETS,
    dispatch_smm_command,
    handle_add_product,
    handle_plan,
    handle_promo_preset,
    handle_quiet_week,
)


@pytest.mark.django_db
def test_dispatch_plan(user):
    text, key, ok, meta = dispatch_smm_command(user, "PLAN")
    assert ok is True
    assert key == "plan"
    assert "7-day plan" in text.lower()


@pytest.mark.django_db
def test_handle_add_product(user):
    with patch("apps.commerce.products.owner_snap_whatsapp._product_limit_message", return_value=None):
        text, key, ok, meta = handle_add_product(user, "ADD Test item 1500")
    assert ok is True
    assert "Test item" in text
    assert meta.get("product_id")


@pytest.mark.django_db
def test_handle_promo_preset(user):
    with patch("apps.core.billing.enforcement.check_seed_limit", return_value=(True, "")):
        with patch("apps.create.briefs.actions.proposals_url_for_asset", return_value="https://example.com/p"):
            text, key, ok, meta = handle_promo_preset(user, "PROMO launch", preset=None)
    assert ok is True
    assert meta.get("preset") == "launch"


@pytest.mark.django_db
def test_quiet_week_toggle(user):
    profile = user.profile
    text, key, ok, _ = handle_quiet_week(user, enable=True)
    assert ok is True
    profile.refresh_from_db()
    assert profile.dna_preferences.get("quiet_week_until")

    text2, key2, ok2, _ = handle_quiet_week(user, enable=False)
    assert ok2 is True
    profile.refresh_from_db()
    assert "quiet_week_until" not in (profile.dna_preferences or {})


def test_promo_presets_cover_sale():
    assert "sale" in PROMO_PRESETS
    assert "launch" in PROMO_PRESETS
