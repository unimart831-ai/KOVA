"""
Tests for:
  - apps.utils.greetings (first_name_of, greeting_name, business_or_name)
  - apps.utils.first_comments (compose_first_comment)
  - apps.memes.tasks._check_adapted_text (quality gate)
"""
import uuid
from unittest.mock import MagicMock

import pytest

from apps.utils.greetings import (
    business_or_name,
    first_name_of,
    greeting_name,
)
from apps.utils.first_comments import compose_first_comment
from apps.memes.tasks import _check_adapted_text


# ──────────────────────────────────────────────────────────────────────────
# Greetings
# ──────────────────────────────────────────────────────────────────────────
def _mock_user(*, first_name="", full_name="", email="", company=""):
    u = MagicMock()
    u.first_name = first_name
    u.full_name = full_name
    u.email = email
    u.profile = MagicMock()
    u.profile.company_name = company
    return u


def test_first_name_of_uses_explicit_first_name():
    u = _mock_user(first_name="Iranzi", full_name="Iranzi Innocent")
    assert first_name_of(u) == "Iranzi"


def test_first_name_of_falls_to_full_name_first_word():
    u = _mock_user(first_name="", full_name="Iranzi Innocent")
    assert first_name_of(u) == "Iranzi"


def test_first_name_of_strips_honorifics():
    u = _mock_user(full_name="Dr. Marie Uwimana")
    assert first_name_of(u) == "Marie"
    u2 = _mock_user(full_name="Mr Joseph K")
    assert first_name_of(u2) == "Joseph"


def test_first_name_of_empty_returns_empty():
    u = _mock_user(full_name="")
    assert first_name_of(u) == ""


def test_first_name_of_none_returns_empty():
    assert first_name_of(None) == ""


def test_greeting_name_uses_first_name_when_present():
    u = _mock_user(full_name="Iranzi Innocent", company="Briquettes Co")
    assert greeting_name(u) == "Iranzi"


def test_greeting_name_falls_back_to_company():
    u = _mock_user(full_name="", company="Briquettes Co", email="x@kova.test")
    assert greeting_name(u) == "Briquettes Co"


def test_greeting_name_falls_back_to_email_handle():
    u = _mock_user(full_name="", company="", email="iranzi297@gmail.com")
    # Trailing digits stripped, single word title-cased
    assert greeting_name(u) == "Iranzi"


def test_greeting_name_never_returns_there():
    """The whole point of this helper: 'there' must never appear."""
    cases = [
        _mock_user(),
        _mock_user(full_name="   "),
        _mock_user(email=""),
        _mock_user(email="@nodomain"),
    ]
    for u in cases:
        name = greeting_name(u)
        assert name and name.lower() != "there", (
            f"greeting_name returned {name!r} for {u} — should never be empty or 'there'"
        )


def test_business_or_name_prefers_company():
    u = _mock_user(full_name="Iranzi", company="Briquettes Co")
    assert business_or_name(u) == "Briquettes Co"


def test_business_or_name_falls_back_to_greeting():
    u = _mock_user(full_name="Iranzi", company="")
    assert business_or_name(u) == "Iranzi"


# ──────────────────────────────────────────────────────────────────────────
# First-comment composer
# ──────────────────────────────────────────────────────────────────────────
def _fake_post(post_id=None):
    p = MagicMock()
    p.id = post_id or uuid.uuid4()
    return p


def _fake_product(name="25kg pack", url="https://example.com/p/25kg", price="5,000 RWF"):
    pr = MagicMock()
    pr.name = name
    pr.product_url = url
    pr.display_price = price
    return pr


def _fake_profile(website="", company=""):
    pr = MagicMock()
    pr.website_url = website
    pr.company_name = company
    return pr


def test_first_comment_returns_empty_for_unsupported_platforms():
    p = _fake_post()
    assert compose_first_comment("twitter", p) == ""
    assert compose_first_comment("instagram", p) == ""
    assert compose_first_comment("", p) == ""


def test_first_comment_returns_empty_when_no_url():
    p = _fake_post()
    assert compose_first_comment("facebook", p) == ""
    assert compose_first_comment("linkedin", p) == ""


def test_first_comment_includes_product_url():
    p = _fake_post()
    text = compose_first_comment("facebook", p, product=_fake_product())
    assert "https://example.com/p/25kg" in text
    assert "25kg pack" in text


def test_first_comment_includes_website_url_when_no_product():
    p = _fake_post()
    profile = _fake_profile(website="https://briquettes.co", company="Briquettes Co")
    text = compose_first_comment("linkedin", p, profile=profile)
    assert "https://briquettes.co" in text


def test_first_comment_avoids_generic_phrases():
    """The whole point of this composer: no 'Learn More:' / 'Shop Now:' templates."""
    p = _fake_post()
    text = compose_first_comment("facebook", p, product=_fake_product())
    assert not text.startswith("Learn more:")
    assert not text.startswith("Shop Now:")
    assert ":" not in text.split("\n")[0] or len(text.split("\n")[0]) > 20  # not a bare label


def test_first_comment_facebook_vs_linkedin_use_different_templates():
    """FB and LinkedIn should each have their own voice — at least some posts differ."""
    p1 = _fake_post(post_id="11111111-1111-1111-1111-111111111111")
    product = _fake_product()
    fb = compose_first_comment("facebook", p1, product=product)
    li = compose_first_comment("linkedin", p1, product=product)
    # Different template libraries — text should differ
    assert fb != li


def test_first_comment_deterministic_per_post():
    """Same post -> same template every time (no surprise on regeneration)."""
    p = _fake_post(post_id="22222222-2222-2222-2222-222222222222")
    product = _fake_product()
    a = compose_first_comment("facebook", p, product=product)
    b = compose_first_comment("facebook", p, product=product)
    assert a == b


def test_first_comment_varies_across_different_posts():
    """Different posts should rotate through the template library."""
    product = _fake_product()
    results = set()
    for i in range(10):
        p = _fake_post(post_id=f"{i:08d}-1111-1111-1111-111111111111")
        results.add(compose_first_comment("facebook", p, product=product))
    # Should have hit at least 3 distinct templates across 10 posts
    assert len(results) >= 3


def test_first_comment_handles_missing_price_gracefully():
    """A product without a price should still produce a sensible comment."""
    p = _fake_post()
    no_price_product = _fake_product(price="")
    text = compose_first_comment("facebook", p, product=no_price_product)
    assert text
    # Should not contain awkward blanks like "for the X," with nothing after
    assert "  " not in text  # no double spaces from blank substitutions
    assert "{price}" not in text


# ──────────────────────────────────────────────────────────────────────────
# Meme adapted_text quality gate
# ──────────────────────────────────────────────────────────────────────────
def test_check_adapted_text_blocks_empty():
    r = _check_adapted_text("")
    assert not r["passed"]
    assert "empty" in r["reasons"][0]


def test_check_adapted_text_blocks_banned_phrase():
    r = _check_adapted_text(
        "In today's fast-paced world, you need our briquettes. Order now."
    )
    assert not r["passed"]
    assert any("banned phrase" in reason for reason in r["reasons"])


def test_check_adapted_text_blocks_ai_leak():
    r = _check_adapted_text("As an AI, I think this meme works for you.")
    assert not r["passed"]


def test_check_adapted_text_blocks_too_long():
    r = _check_adapted_text("x" * 3000)
    assert not r["passed"]
    assert any("2500" in reason for reason in r["reasons"])


def test_check_adapted_text_warns_on_too_short_but_passes():
    """Very short text gets a soft warning but isn't blocked unless it's <15 chars."""
    r = _check_adapted_text("Hi")  # 2 chars — should block
    assert not r["passed"]


def test_check_adapted_text_passes_clean_content():
    r = _check_adapted_text(
        "Real Kenyan businesses: stop buying expensive charcoal that lasts 2 hours. "
        "Our briquettes burn 4x longer and won't smoke up your kitchen."
    )
    assert r["passed"]
    assert not r["reasons"]


def test_check_adapted_text_checks_caption_too():
    """Banned phrase in caption (not main text) should still block."""
    r = _check_adapted_text(
        "Real briquettes for real households.",
        adapted_caption="On this special day, choose better fuel.",
    )
    assert not r["passed"]
