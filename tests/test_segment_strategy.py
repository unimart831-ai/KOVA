from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from apps.accounts.segments import infer_business_mode
from apps.agents.create_agent import build_generation_prompt
from apps.agents.playbooks import get_playbook_for_industry
from apps.campaigns.tasks import _generate_campaign_plan
from apps.content.autopilot import _strategist_plan_week
from apps.content.models import ContentSeed
from apps.products.models import Product


@pytest.mark.django_db
class TestSegmentStrategy:
    def test_creator_profiles_use_expert_mode_and_playbook(self, user):
        user.profile.industry = "creator"
        user.profile.target_audience = "Founders and operators in Africa"
        user.profile.goals = ["Grow audience", "Generate leads"]
        user.profile.platform_priority = {"linkedin": 1}
        user.profile.save(update_fields=["industry", "target_audience", "goals", "platform_priority"])

        assert infer_business_mode(user.profile, ["linkedin"]) == "expert"

        playbook = get_playbook_for_industry(
            "creator",
            company_name="Amara Writes",
            brand_voice="Clear, practical, and thoughtful",
        )
        assert playbook is not None
        assert playbook["name"] == "Creator & Expert Brand"

    def test_digital_keywords_can_override_default_mode(self, user):
        user.profile.industry = "consulting"
        user.profile.key_offerings = ["Template pack", "Mini course"]
        user.profile.save(update_fields=["industry", "key_offerings"])

        assert infer_business_mode(user.profile, ["linkedin"]) == "digital"

    def test_service_offer_prompt_uses_booking_language(self, user):
        product = Product.objects.create(
            user=user,
            name="Brand Strategy Session",
            offering_type=Product.OfferingType.SERVICE,
            product_url="https://example.com/book",
        )
        seed = ContentSeed.objects.create(
            user=user,
            product=product,
            idea="Promote our strategy session to founders",
        )

        prompt = build_generation_prompt(seed, [{"platform": "linkedin", "username": "coach"}])

        assert "SERVICE BEING PROMOTED" in prompt
        assert "Primary booking / inquiry URL" in prompt
        assert "Book a consultation" in prompt
        assert "Purchase URL" not in prompt

    def test_campaign_plan_prompt_includes_segment_context(self, user, monkeypatch):
        captured = {}

        def fake_generate(*, model, system, prompt, temperature, max_tokens):
            captured["system"] = system
            captured["prompt"] = prompt
            return SimpleNamespace(
                text=(
                    '{"name":"Authority Sprint","description":"Grow our professional brand",'
                    '"objective":"engagement","target_audience":"Operators","include_email":false,'
                    '"include_whatsapp_status":false,"key_message":"Lead with authority","status_updates":[],'
                    '"seeds":[{"idea":"Share a strong lesson","platforms":["linkedin"],"day":1}]}'
                )
            )

        monkeypatch.setattr("apps.agents.llm.generate", fake_generate)
        monkeypatch.setattr("apps.agents.llm.get_model_for_task", lambda *args, **kwargs: "fake-model")

        user.profile.industry = "creator"
        user.profile.target_audience = "Operators and consultants"
        user.profile.key_offerings = ["LinkedIn advisory"]
        user.profile.goals = ["Grow audience", "Generate leads"]
        user.profile.save(update_fields=["industry", "target_audience", "key_offerings", "goals"])

        plan = _generate_campaign_plan(
            user,
            "Grow my professional visibility on LinkedIn",
            ["linkedin"],
            "Amara",
            "Sharp and credible",
            7,
        )

        assert plan["name"] == "Authority Sprint"
        assert "Expert mode" in captured["system"]
        assert "authority" in captured["prompt"].lower()

    def test_autopilot_fallback_topics_adapt_for_expert_mode(self, user, monkeypatch):
        captured = {}

        def fake_generate(*, prompt, system, model, temperature, max_tokens, json_mode):
            captured["prompt"] = prompt
            return SimpleNamespace(content="not-json")

        monkeypatch.setattr("apps.agents.llm.generate", fake_generate)
        monkeypatch.setattr("apps.agents.llm.get_model_for_task", lambda *args, **kwargs: "fake-model")

        user.profile.industry = "creator"
        user.profile.target_audience = "Career-focused professionals"
        user.profile.goals = ["Build authority"]
        user.profile.save(update_fields=["industry", "target_audience", "goals"])

        strategy = _strategist_plan_week(
            user,
            user.profile,
            ["linkedin"],
            date(2026, 1, 5),
            posts_per_week=3,
        )

        topics = " ".join(item["topic"] for item in strategy["daily_topics"]).lower()
        assert "product highlight" not in topics
        assert any(keyword in topics for keyword in ["opinion", "lesson", "framework", "client insight"])
        assert "Expert mode" in captured["prompt"]
