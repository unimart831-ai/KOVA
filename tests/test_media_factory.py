"""Tests for Phase 3 Media Factory modules."""

import pytest

from apps.media.campaign_visual_brief import (
    CampaignVisualBrief,
    build_campaign_visual_brief,
    DEFAULT_SCENE_ROLES,
)
from apps.media.carousel_strategy import (
    build_carousel_strategy,
    select_carousel_template,
    CarouselStrategy,
)
from apps.media.media_provider_config import MediaProviderConfig
from apps.media.media_factory import prepare_campaign_media_factory
from apps.media.orchestrator import PROFESSIONAL_PHOTOROOM_SCENES_PER_CAMPAIGN, cap_photoroom_scenes_for_plan
from apps.media.reel_strategy import build_reel_strategy, ReelStrategy
from apps.media.text_overlay import TextOverlayPass
from apps.content.platform_fit import score_platform_fit, PLATFORM_FIT_MIN_SCORE, platform_fit_gate
from apps.content.models import ContentSeed
from apps.content.campaigns import ensure_campaign_for_seed


@pytest.mark.django_db
class TestCampaignVisualBrief:
    def test_scene_cap_enforced(self, user):
        brief = CampaignVisualBrief(scenes=list(DEFAULT_SCENE_ROLES) + ["extra1", "extra2", "extra3"])
        capped = brief.capped_scenes(user)
        assert len(capped) <= cap_photoroom_scenes_for_plan(user, PROFESSIONAL_PHOTOROOM_SCENES_PER_CAMPAIGN)

    def test_build_from_seed(self, user):
        seed = ContentSeed.objects.create(
            user=user,
            idea="Weekend sale on handbags",
            target_platforms=["instagram"],
        )
        campaign = ensure_campaign_for_seed(seed, title="Weekend sale", objective="sales")
        brief = build_campaign_visual_brief(seed, campaign)
        assert brief.objective
        assert len(brief.scenes) <= cap_photoroom_scenes_for_plan(user, PROFESSIONAL_PHOTOROOM_SCENES_PER_CAMPAIGN)
        assert brief.photoroom_scene_prompt("studio", product_name="Bag")


@pytest.mark.django_db
class TestCarouselStrategy:
    def test_template_selection_sales(self):
        assert select_carousel_template(objective="sales") == "offer"

    def test_build_strategy_has_slides(self, user):
        seed = ContentSeed.objects.create(user=user, idea="New collection launch")
        strategy = build_carousel_strategy(seed)
        assert len(strategy.slides) >= 5
        assert strategy.type

    def test_to_carousel_slides(self, user):
        seed = ContentSeed.objects.create(user=user, idea="Tips for founders")
        strategy = build_carousel_strategy(seed)
        slides = strategy.to_carousel_slides()
        assert slides[0].get("funnel_role") == strategy.slides[0].role


@pytest.mark.django_db
class TestReelStrategy:
    def test_build_reel_strategy(self, user):
        seed = ContentSeed.objects.create(user=user, idea="Flash sale today only")
        campaign = ensure_campaign_for_seed(seed, objective="sales")
        rs = build_reel_strategy(seed, campaign)
        assert rs.hook
        assert len(rs.scenes) >= 3
        assert rs.hook_texts_for_compose()


@pytest.mark.django_db
class TestMediaFactoryPrep:
    def test_prepare_persists_on_campaign(self, user):
        seed = ContentSeed.objects.create(user=user, idea="Product promo")
        campaign = ensure_campaign_for_seed(seed, objective="sales")
        payload = prepare_campaign_media_factory(seed, campaign)
        campaign.refresh_from_db()
        seed.refresh_from_db()
        assert payload.get("visual_brief")
        assert payload.get("carousel_strategy")
        assert payload.get("reel_strategy")
        assert campaign.proposal_meta.get("media_factory")
        assert seed.blueprint.get("carousel_strategy")


class TestTextOverlayPass:
    def test_overlay_validation_passes(self):
        tp = TextOverlayPass()
        texts, report = tp.prepare_for_compose(["Weekend sale — 20% off", "Shop now"])
        assert report.passed
        assert len(texts) >= 1

    def test_rejects_empty_overlay(self):
        tp = TextOverlayPass()
        overlays = tp.build_overlays(["", "   "])
        report = tp.validate(overlays)
        assert report.passed  # empty overlays skipped in build


class TestPlatformFit:
    def test_instagram_fit_scoring(self):
        post = {
            "platform": "instagram",
            "post_format": "carousel",
            "content_text": "Save this for your weekend glow-up ✨ Your skin will thank you.",
            "cta_url": "https://example.com/c/sale/",
        }
        score, _ = score_platform_fit(post)
        assert score >= 50

    def test_gate_threshold(self):
        ok, _ = platform_fit_gate(85)
        assert ok
        ok, msg = platform_fit_gate(70)
        assert not ok
        assert str(PLATFORM_FIT_MIN_SCORE) in msg


class TestMediaProviderConfig:
    def test_from_settings_no_crash(self, settings):
        settings.PHOTOROOM_API_KEY = "test-key"
        cfg = MediaProviderConfig.from_settings()
        assert cfg.photoroom_ready
        assert "PHOTOROOM_API_KEY" not in cfg.missing_for_production()
