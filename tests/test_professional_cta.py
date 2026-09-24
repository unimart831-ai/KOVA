"""Tests for professional CTA and snap modes."""

from __future__ import annotations

import pytest

from apps.core.accounts.models import User, UserProfile
from apps.create.content.professional_cta import apply_professional_cta_to_post, should_apply_professional_cta
from apps.create.content.models import ContentSeed, Post
from apps.core.platforms.models import SocialAccount


@pytest.fixture
def pro_user(db):
    u = User.objects.create_user(username="pro2", email="pro2@kova.ai", password="x")
    UserProfile.objects.filter(user=u).update(
        business_model="professional",
        company_name="Acme Law",
        page_slug="acme-law",
    )
    return u


@pytest.mark.django_db
def test_should_apply_professional_cta(pro_user):
    seed = ContentSeed.objects.create(user=pro_user, idea="x")
    assert should_apply_professional_cta(pro_user, seed, "facebook") is True
    assert should_apply_professional_cta(pro_user, seed, "linkedin") is True
    assert should_apply_professional_cta(pro_user, seed, "tiktok") is False


@pytest.mark.django_db
def test_apply_cta_sets_link(pro_user):
    sa = SocialAccount.objects.create(
        user=pro_user, platform="facebook", username="acme", platform_user_id="fb1", is_active=True,
    )
    post = Post.objects.create(
        user=pro_user, social_account=sa, platform="facebook", content_text="Thought leadership post",
    )
    seed = ContentSeed.objects.create(
        user=pro_user,
        idea="Case study",
        blueprint={"asset_type": "case_study", "metadata": {"suggested_cta": "Book a call →"}},
    )
    assert apply_professional_cta_to_post(post, pro_user, seed) is True
    post.refresh_from_db()
    assert post.cta_type == "link"
    assert post.cta_url
    assert "Book" in post.cta_text
    assert post.first_comment
    assert post.cta_url in post.first_comment or "http" in post.first_comment.lower()
