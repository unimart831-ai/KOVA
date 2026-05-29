"""Tests for Photoroom API helpers (uncertainty, sandbox, smart crop planning)."""

from unittest.mock import MagicMock, patch

from apps.products.photoroom_api import (
    PhotoroomEditResult,
    beautify_mode_for_category,
    check_sandbox_quota,
    merge_uncertainty,
    parse_uncertainty_score,
    uncertainty_is_high,
)
from apps.products.photoroom_preflight import PhotoQualityReport, build_repair_plan
from apps.products.photoroom_plus import PLUS_VARIANT_CATALOG, select_plus_variants
from apps.products.photoroom_virtual_models import build_virtual_model_params


def test_parse_uncertainty_score_valid():
    headers = {"x-uncertainty-score": "0.42"}
    assert parse_uncertainty_score(headers) == 0.42


def test_parse_uncertainty_score_unavailable():
    assert parse_uncertainty_score({"x-uncertainty-score": "-1"}) is None


def test_beautify_mode_by_category():
    assert beautify_mode_for_category("food") == "ai.food"
    assert beautify_mode_for_category("electronics") == "ai.car"
    assert beautify_mode_for_category("general") == "ai.auto"


def test_build_repair_plan_includes_smart_crop_for_tight():
    report = PhotoQualityReport(crop="very_tight")
    plan = build_repair_plan(report, plan_tier="starter")
    assert "smart_crop" in plan
    assert plan.index("smart_crop") < plan.index("uncrop") if "uncrop" in plan else True


def test_high_uncertainty_skips_apparel_variants():
    class P:
        name = "Dress"
        tags = ["women"]
        offering_type = "product"

    specs = select_plus_variants(
        P(), {}, plan_tier="agency", max_count=12, uncertainty_score=0.85,
    )
    ids = {s.id for s in specs}
    assert "ghost_mannequin" not in ids
    assert "virtual_model" not in ids


def test_virtual_model_params_use_api_presets():
    params = build_virtual_model_params("female_confident", "urban_street")
    assert params["virtualModel.model.preset.name"] == "avery"
    assert params["virtualModel.scene.preset.name"] == "street"
    assert params["virtualModel.pose"] == "standing"
    assert params["removeBackground"] == "false"


def test_background_blur_variant_doc_aligned():
    spec = PLUS_VARIANT_CATALOG["background_blur"]
    assert spec.params["removeBackground"] == "false"
    assert spec.params["background.blur.mode"] in ("bokeh", "gaussian")


@patch("apps.products.photoroom_api.get_sandbox_usage")
@patch("django.conf.settings.PHOTOROOM_SANDBOX", True, create=True)
def test_sandbox_quota_blocks_at_daily_limit(mock_usage):
    mock_usage.return_value = {
        "daily": 100,
        "daily_limit": 100,
        "monthly": 50,
        "monthly_limit": 1000,
    }
    allowed, msg = check_sandbox_quota()
    assert allowed is False
    assert "daily" in (msg or "").lower()


def test_photoroom_edit_parses_uncertainty():
    from apps.products.photoroom_plus import photoroom_edit

    mock_resp = MagicMock()
    mock_resp.content = b"\xff\xd8\xff" + b"x" * 100
    mock_resp.headers = {"x-uncertainty-score": "0.25"}
    mock_resp.raise_for_status = MagicMock()

    with patch("apps.products.photoroom_plus._api_key_headers", return_value=("key", {})):
        with patch("apps.products.photoroom_api.check_sandbox_quota", return_value=(True, None)):
            with patch("apps.products.photoroom_api.record_sandbox_call"):
                with patch("apps.products.photoroom_plus._load_image_bytes", return_value=(b"img", "a.jpg")):
                    with patch("requests.post", return_value=mock_resp):
                        result = photoroom_edit("/media/x.jpg", {"removeBackground": "true"})
    assert isinstance(result, PhotoroomEditResult)
    assert result.ok
    assert result.uncertainty_score == 0.25


def test_merge_uncertainty_keeps_max():
    assert merge_uncertainty(0.3, 0.7) == 0.7
    assert uncertainty_is_high(0.7) is True
    assert uncertainty_is_high(0.3) is False
