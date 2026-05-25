"""Tests for Photoroom seller brand template (Phase D)."""

from apps.products.photoroom_brand_template import (
    apply_brand_template,
    build_photoroom_brand_template,
    stable_ai_seed,
)
from apps.products.photoroom_plus import PLUS_VARIANT_CATALOG


class _Profile:
    def __init__(self, **kwargs):
        self.industry = kwargs.get("industry", "ecommerce")
        self.brand_colors = kwargs.get("brand_colors", ["#3366CC", "#1A1A2E"])
        self.visual_style = kwargs.get("visual_style", "corporate")
        self.brand_voice = kwargs.get("brand_voice", "")
        self.company_name = kwargs.get("company_name", "Acme Shop")
        self.photoroom_brand_template = kwargs.get("photoroom_brand_template", {})


def test_stable_seed_is_deterministic():
    assert stable_ai_seed("user-42") == stable_ai_seed("user-42")
    assert stable_ai_seed("user-42") != stable_ai_seed("user-99")


def test_saas_gets_floating_shadow():
    profile = _Profile(industry="saas", brand_colors=["#000000", "#00FFAA"])
    template = build_photoroom_brand_template(profile, "user-1")
    assert template.enabled is True
    assert template.shadow_mode == "ai.floating"
    assert template.padding == "0.10"


def test_profile_override_shadow():
    profile = _Profile(
        photoroom_brand_template={"shadow_mode": "ai.hard", "padding": "0.15"},
    )
    template = build_photoroom_brand_template(profile, "user-2")
    assert template.shadow_mode == "ai.hard"
    assert template.padding == "0.15"
    assert template.source == "profile_override"


def test_apply_brand_template_to_ai_lifestyle():
    profile = _Profile(company_name="Glow Co")
    template = build_photoroom_brand_template(profile, "user-3")
    spec = PLUS_VARIANT_CATALOG["ai_lifestyle"]
    resolved = {
        "padding": "0.12",
        "shadow.mode": "ai.soft",
        "background.prompt": "A product on a desk",
        "background.seed": "999",
    }
    out = apply_brand_template(resolved, template, spec)
    assert out["padding"] == template.padding
    assert out["shadow.mode"] == template.shadow_mode
    assert out["background.seed"] == str(template.ai_background_seed)
    assert "Consistent brand look" in out["background.prompt"]
    assert "Glow Co" in out["background.prompt"]


def test_apply_brand_template_studio_white_keeps_white_bg():
    profile = _Profile()
    template = build_photoroom_brand_template(profile, "user-4")
    spec = PLUS_VARIANT_CATALOG["studio_white"]
    resolved = {
        "padding": "0.12",
        "shadow.mode": "ai.soft",
        "background.color": "FFFFFF",
    }
    out = apply_brand_template(resolved, template, spec)
    assert out["background.color"] == "FFFFFF"
    assert out["shadow.mode"] == template.shadow_mode


def test_outline_uses_brand_accent():
    profile = _Profile(brand_colors=["#FFFFFF", "#FF5733"])
    template = build_photoroom_brand_template(profile, "user-5")
    spec = PLUS_VARIANT_CATALOG["outline"]
    resolved = {"outline.color": "000000", "padding": "0.12", "shadow.mode": "ai.soft"}
    out = apply_brand_template(resolved, template, spec)
    assert out["outline.color"] == "FF5733"
