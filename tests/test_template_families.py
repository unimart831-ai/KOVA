"""Tests for canonical Template Families registry and selectors."""

from __future__ import annotations

import pytest

from apps.create.content.template_families import (
    OBJECTIVE_TO_FAMILY,
    TEMPLATE_FAMILIES,
    VALID_FAMILY_KEYS,
    apply_family_to_blueprint,
    family_prompt_section,
    family_to_legacy_carousel,
    get_family,
    resolve_template_family,
)
from apps.create.media.carousel_strategy import (
    CAROUSEL_TEMPLATES,
    INTENT_TO_TEMPLATE,
    select_carousel_template,
)


def test_exactly_twelve_families():
    assert len(TEMPLATE_FAMILIES) == 12
    assert VALID_FAMILY_KEYS == frozenset(TEMPLATE_FAMILIES)


def test_expected_family_keys_present():
    expected = {
        "product_spotlight",
        "launch",
        "offer",
        "educational",
        "faq",
        "testimonial",
        "before_after",
        "case_study",
        "thought_leadership",
        "booking_cta",
        "behind_the_brand",
        "seasonal",
    }
    assert set(TEMPLATE_FAMILIES) == expected


@pytest.mark.parametrize(
    "objective,family",
    [
        ("sales", "offer"),
        ("leads", "educational"),
        ("awareness", "launch"),
        ("bookings", "booking_cta"),
        ("authority", "thought_leadership"),
        ("proof", "case_study"),
    ],
)
def test_objective_to_family_mapping(objective, family):
    assert OBJECTIVE_TO_FAMILY[objective] == family
    assert resolve_template_family(objective=objective) == family


def test_legacy_carousel_defaults_preserved():
    assert select_carousel_template(objective="sales") == "offer"
    assert select_carousel_template(business_model="service", objective="") == "faq"
    assert select_carousel_template(business_model="professional", objective="") == "educational"
    assert select_carousel_template(objective="bookings") == "faq"  # booking_cta → faq carousel
    assert select_carousel_template(objective="awareness") == "product_launch"


def test_legacy_carousel_templates_built():
    for key in (
        "offer",
        "faq",
        "educational",
        "case_study",
        "testimonial",
        "product_launch",
        "before_after",
        "industry_insight",
    ):
        assert key in CAROUSEL_TEMPLATES
        assert "slide_roles" in CAROUSEL_TEMPLATES[key]


def test_intent_to_template_uses_legacy_carousel_keys():
    assert INTENT_TO_TEMPLATE["sales"] == "offer"
    assert INTENT_TO_TEMPLATE["bookings"] == family_to_legacy_carousel("booking_cta")


def test_get_family_resolves_legacy_keys():
    assert get_family("product_launch").key == "launch"
    assert get_family("transformation").key == "before_after"
    assert get_family("industry_insight").key == "thought_leadership"


def test_apply_family_writes_metadata():
    bp = apply_family_to_blueprint({"metadata": {}}, "offer", context={"service": "Facial"})
    assert bp["template_family"] == "offer"
    assert bp["metadata"]["template_family"] == "offer"
    assert bp["metadata"]["service_template"] == "offer"
    assert family_prompt_section(bp).startswith("### TEMPLATE FAMILY:")


@pytest.mark.django_db
def test_seed_and_campaign_persist_family(user):
    from apps.create.content.campaigns import ensure_campaign_for_seed
    from apps.create.content.models import ContentSeed

    seed = ContentSeed.objects.create(
        user=user,
        idea="Flash sale this weekend",
        template_family="offer",
    )
    campaign = ensure_campaign_for_seed(seed, title="Flash sale", objective="sales")
    campaign.refresh_from_db()
    seed.refresh_from_db()
    assert campaign.template_family == "offer"
    assert seed.template_family == "offer"


@pytest.mark.django_db
def test_carousel_strategy_attaches_family(user):
    from apps.create.content.models import ContentSeed
    from apps.create.media.carousel_strategy import build_carousel_strategy

    seed = ContentSeed.objects.create(
        user=user,
        idea="Weekend promo",
        template_family="offer",
        blueprint={"objective": "sales"},
    )
    strategy = build_carousel_strategy(seed)
    assert strategy.template_family == "offer"
    assert strategy.template_key == "offer"
    assert strategy.type == "Promotion & Offers"
    assert len(strategy.slides) >= 5
