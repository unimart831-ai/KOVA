"""Phase 1 — Business Brain + First Business Report.

These lock in the two backend services that make onboarding feel like hiring an
employee: structured understanding (the Brain) and the "Kova already gets my
business" assessment (the First Business Report). All assertions use the
deterministic, no-LLM path (use_llm=False) so CI needs no network.
"""

import pytest
from django.contrib.auth import get_user_model

from apps.accounts.business_brain import (
    brain_completeness,
    build_brain_snapshot,
    extract_and_apply_brain,
)
from apps.accounts.first_business_report import build_first_business_report

User = get_user_model()


@pytest.fixture
def user(db):
    u = User.objects.create_user(username="brain", email="brain@example.com", password="Passw0rd!")
    return u


@pytest.mark.django_db
class TestBusinessBrain:
    def test_conversational_answers_populate_dna(self, user):
        profile = user.profile
        updated = extract_and_apply_brain(
            profile,
            what="I run a small salon specializing in braids for university students",
            why="I wanted affordable, quality hair care for students",
            success="Double my bookings and open a second branch",
            business_model="service",
            use_llm=False,
        )
        profile.refresh_from_db()

        assert profile.business_model == "service"
        assert "founder_story" in updated
        assert profile.founder_story.startswith("I wanted affordable")
        assert profile.success_vision.startswith("Double my bookings")
        # Fallback seeds audience + universally useful salesperson questions.
        assert profile.target_audience
        assert profile.common_questions

    def test_never_overwrites_existing_fields(self, user):
        profile = user.profile
        profile.founder_story = "My original story"
        profile.save(update_fields=["founder_story"])

        extract_and_apply_brain(
            profile,
            why="A different story",
            business_model="product",
            use_llm=False,
        )
        profile.refresh_from_db()
        assert profile.founder_story == "My original story"
        assert profile.business_model == "product"

    def test_snapshot_has_six_layers(self, user):
        snapshot = build_brain_snapshot(user.profile)
        for layer in ("business", "brand", "customer", "growth", "market", "learning"):
            assert layer in snapshot
        assert "completeness" in snapshot

    def test_completeness_increases_as_brain_fills(self, user):
        profile = user.profile
        empty = brain_completeness(profile)
        profile.brand_voice = "Friendly and confident"
        profile.target_audience = "University students who love affordable style"
        profile.founder_story = "Started to help students look great affordably"
        profile.customer_problems = "Expensive salons with long waits"
        profile.save()
        filled = brain_completeness(profile)
        assert filled > empty


@pytest.mark.django_db
class TestFirstBusinessReport:
    def test_report_shape_and_plan(self, user):
        profile = user.profile
        profile.company_name = "Braids by Mary"
        profile.business_model = "service"
        profile.brand_voice = "Warm, confident, community-first"
        profile.tone_attributes = ["warm", "confident"]
        profile.founder_story = "Affordable quality braids for students"
        profile.target_audience = "University students"
        profile.customer_problems = "Expensive, slow salons"
        profile.buy_triggers = "Affordable and fast"
        profile.key_offerings = ["Braids", "Wash & style"]
        profile.content_pillars = ["Transformations", "Tips", "Offers"]
        profile.goals = ["book_appointments", "generate_leads"]
        profile.success_vision = "Open a second branch"
        profile.save()

        report = build_first_business_report(user, use_llm=False)

        assert 0 <= report["marketing_score"] <= 100
        assert report["marketing_score"] > 50  # well-filled brain scores well
        assert report["grade"]
        assert report["strengths"]
        assert isinstance(report["weaknesses"], list)
        assert report["growth_opportunities"]
        assert report["estimated_growth_potential"].startswith("+")
        assert len(report["ninety_day_plan"]) == 3
        assert [m["month"] for m in report["ninety_day_plan"]] == [1, 2, 3]

    def test_empty_business_scores_low_and_flags_gaps(self, user):
        report = build_first_business_report(user, use_llm=False)
        assert report["marketing_score"] < 40
        assert report["weaknesses"]
        # Lower readiness surfaces more headroom.
        assert report["estimated_growth_potential"] != "+0%"

    def test_service_plan_month3_is_bookings_oriented(self, user):
        profile = user.profile
        profile.business_model = "service"
        profile.save(update_fields=["business_model"])
        report = build_first_business_report(user, use_llm=False)
        month3 = report["ninety_day_plan"][2]
        assert "booking" in month3["focus"].lower()
