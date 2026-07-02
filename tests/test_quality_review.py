"""AI Quality Review Board — the content-quality moat.

Verifies the board scores every post across production + business-impact
dimensions, gates on the publish threshold + safety floors, and produces a
"why this will succeed" explanation with confidence. Deterministic (no LLM).
"""

import pytest
from django.contrib.auth import get_user_model

from apps.content.models import Post
from apps.content.quality_review import review_post

User = get_user_model()


@pytest.fixture
def owner(db):
    u = User.objects.create_user(username="qa", email="qa@example.com", password="Passw0rd!")
    p = u.profile
    p.target_audience = "university students who need affordable waterproof sneakers for campus"
    p.customer_problems = "wet feet on rainy campus mornings"
    p.buy_triggers = "affordable and durable"
    p.goals = ["drive_sales"]
    p.dna_preferences = {"promoted": [{"combo": {"pillar": "Offers"}}]}
    p.save()
    return u


def _post(user, text, **kw):
    defaults = dict(
        user=user,
        platform="facebook",
        post_format="text",
        content_text=text,
        status=Post.Status.PENDING_APPROVAL,
    )
    defaults.update(kw)
    return Post.objects.create(**defaults)


@pytest.mark.django_db
class TestQualityReviewBoard:
    def test_scorecard_has_all_eight_dimensions(self, owner):
        post = _post(owner, "A simple update about our shop and what we offer today.")
        review = review_post(post)
        for dim in ("visual", "brand", "platform", "cta", "compliance", "customer", "sales", "strategy"):
            assert dim in review.dimensions
            assert "score" in review.dimensions[dim]
            assert "label" in review.dimensions[dim]

    def test_strong_post_scores_high_and_passes(self, owner):
        post = _post(
            owner,
            "Students, these affordable waterproof sneakers keep your feet dry on rainy "
            "campus mornings. Reply SHOE to order today with free delivery!",
            cta_type="whatsapp",
            cta_url="https://wa.me/254700000000",
            content_dna={"pillar": "Offers"},
            predicted_engagement_score=82,
        )
        review = review_post(post)
        assert review.dimensions["customer"]["score"] >= 75
        assert review.dimensions["sales"]["score"] >= 75
        assert review.dimensions["strategy"]["score"] >= 75
        assert review.confidence == 82  # reuses predicted score
        assert review.why  # explanation present
        assert review.passed is True

    def test_weak_post_flags_conversion_risk(self, owner):
        post = _post(owner, "New arrivals available now.")
        review = review_post(post)
        assert review.dimensions["sales"]["score"] < 75
        assert review.risks  # risks surfaced
        assert review.passed is False  # thin content shouldn't auto-pass

    def test_customer_reviewer_rewards_audience_match(self, owner):
        on_brand = _post(
            owner,
            "Affordable waterproof sneakers built for students walking across a rainy campus all day.",
        )
        off_brand = _post(owner, "Check out our latest corporate quarterly synergy report.")
        assert (
            review_post(on_brand).dimensions["customer"]["score"]
            > review_post(off_brand).dimensions["customer"]["score"]
        )

    def test_confidence_derived_when_no_prediction(self, owner):
        post = _post(owner, "A friendly, on-brand update for our followers about the week ahead.")
        review = review_post(post)
        assert 35 <= review.confidence <= 95

    def test_safety_floor_blocks_bad_content(self, owner):
        post = _post(owner, "[insert product name] — tag 3 friends to win a free prize now!!!")
        review = review_post(post)
        assert review.passed is False
        assert any("Blocked" in r or "afety" in r or "ompliance" in r for r in review.risks)


@pytest.mark.django_db
class TestScorecardRender:
    def test_detail_page_shows_scorecard(self, client, owner):
        from django.urls import reverse

        owner.phone_number = "0712345678"
        owner.onboarding_completed = True
        owner.save(update_fields=["phone_number", "onboarding_completed"])
        client.force_login(owner)
        post = _post(
            owner,
            "Affordable waterproof sneakers for students on a rainy campus. Reply SHOE to order today!",
            cta_type="whatsapp",
            cta_url="https://wa.me/254700000000",
        )
        resp = client.get(reverse("content:post_detail", args=[post.id]))
        assert resp.status_code == 200
        assert b"AI Quality Review Board" in resp.content
