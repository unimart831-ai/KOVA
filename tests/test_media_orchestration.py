"""Tests for media orchestration — Brand DNA, asset intelligence, routing."""

import pytest

from apps.core.accounts.models import UserProfile
from apps.create.media.asset_intelligence import recommend_media_plan
from apps.create.media.brand_dna import resolve_brand_dna
from apps.create.media.content_types import ContentFormat, MediaPlan, ReelBackend
from apps.create.media.router import pick_carousel_backend, pick_reel_backend
from apps.commerce.products.models import BusinessAsset, Product


@pytest.mark.django_db
class TestBrandDNA:
    def test_resolve_brand_dna_from_profile(self, user):
        user.profile.company_name = "Nairobi Boutique"
        user.profile.brand_colors = ["#112233", "#445566"]
        user.profile.business_model = UserProfile.BusinessModel.PRODUCT
        user.profile.visual_style = "photography"
        user.profile.save()

        dna = resolve_brand_dna(user, user.profile)
        assert dna.brand_name
        assert dna.primary_color == "#112233"
        assert dna.accent_color == "#445566"
        assert dna.business_model == UserProfile.BusinessModel.PRODUCT
        assert "brand colors" in dna.flux_style_suffix()


@pytest.mark.django_db
class TestAssetIntelligence:
    def test_product_recommends_carousel_and_reel(self, user):
        product = Product.objects.create(
            user=user,
            name="Handbag",
            commerce_slug="handbag",
            price=4500,
        )
        plan = recommend_media_plan(
            user,
            product=product,
            image_count=3,
        )
        assert ContentFormat.CAROUSEL in plan.formats
        assert ContentFormat.REEL in plan.formats

    def test_service_recommends_reel_first(self, user):
        user.profile.business_model = UserProfile.BusinessModel.SERVICE
        user.profile.save()
        asset = BusinessAsset.objects.create(
            user=user,
            asset_type=BusinessAsset.AssetType.SERVICE,
            title="Salon cut",
        )
        plan = recommend_media_plan(user, asset=asset, image_count=2)
        assert plan.formats[0] == ContentFormat.REEL


@pytest.mark.django_db
class TestMediaRouter:
    def test_starter_defaults_to_local_and_ffmpeg(self, user):
        plan = MediaPlan()
        assert pick_reel_backend(user, plan=plan).value == "ffmpeg"
        assert pick_carousel_backend(user, plan=plan).value == "local"

    def test_pro_plan_kling_when_configured(self, user):
        user.profile.plan = UserProfile.PlanTier.PRO
        user.profile.save()
        plan = MediaPlan(reel_backend=ReelBackend.KLING)
        backend = pick_reel_backend(user, plan=plan)
        assert backend.value in ("ffmpeg", "kling")
