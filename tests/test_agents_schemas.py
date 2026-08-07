"""
Tests for the LLM-output validation layer.

The concrete bug this prevents: LLM returns prose ("I cannot provide a score...")
for predicted_score. The old code passed that string straight into a FloatField,
crashing Post.objects.create() and silently dropping the whole batch.
"""

import pytest

from apps.create.agents.schemas import PostDraft


class TestPredictedScoreCoercion:
    def test_float_passthrough(self):
        assert PostDraft.from_llm_dict({"predicted_score": 72.5}).predicted_score == 72.5

    def test_int_coerced_to_float(self):
        assert PostDraft.from_llm_dict({"predicted_score": 72}).predicted_score == 72.0

    def test_numeric_string(self):
        assert PostDraft.from_llm_dict({"predicted_score": "72"}).predicted_score == 72.0

    def test_decimal_string(self):
        assert PostDraft.from_llm_dict({"predicted_score": "72.5"}).predicted_score == 72.5

    def test_percent_string(self):
        assert PostDraft.from_llm_dict({"predicted_score": "72%"}).predicted_score == 72.0

    def test_percent_string_with_whitespace(self):
        assert PostDraft.from_llm_dict({"predicted_score": "  85%  "}).predicted_score == 85.0

    def test_clamps_above_100(self):
        assert PostDraft.from_llm_dict({"predicted_score": 150}).predicted_score == 100.0

    def test_clamps_below_zero(self):
        assert PostDraft.from_llm_dict({"predicted_score": -10}).predicted_score == 0.0

    def test_none_stays_none(self):
        assert PostDraft.from_llm_dict({"predicted_score": None}).predicted_score is None

    def test_empty_string_becomes_none(self):
        assert PostDraft.from_llm_dict({"predicted_score": ""}).predicted_score is None

    def test_missing_field_is_none(self):
        assert PostDraft.from_llm_dict({}).predicted_score is None

    def test_prose_refusal_becomes_none(self, caplog):
        # The actual string from production logs that crashed the task
        prose = (
            "As a high-performance AI agent, my content is designed to drive "
            "engagement and results. I cannot provide a predicted score..."
        )
        draft = PostDraft.from_llm_dict({"predicted_score": prose})
        assert draft.predicted_score is None
        assert "rejected" in caplog.text.lower()

    def test_dict_becomes_none(self):
        draft = PostDraft.from_llm_dict({"predicted_score": {"nope": "nope"}})
        assert draft.predicted_score is None

    def test_list_becomes_none(self):
        draft = PostDraft.from_llm_dict({"predicted_score": [1, 2, 3]})
        assert draft.predicted_score is None

    def test_bool_becomes_none(self):
        # bool is a subclass of int in Python — explicit reject
        draft = PostDraft.from_llm_dict({"predicted_score": True})
        assert draft.predicted_score is None


class TestStringFieldCoercion:
    def test_content_text_default(self):
        assert PostDraft.from_llm_dict({}).content_text == ""

    def test_content_text_strips_whitespace(self):
        assert PostDraft.from_llm_dict({"content_text": "  hello  "}).content_text == "hello"

    def test_none_string_becomes_empty(self):
        assert PostDraft.from_llm_dict({"reasoning": None}).reasoning == ""

    def test_number_coerced_to_string(self):
        assert PostDraft.from_llm_dict({"angle": 42}).angle == "42"


class TestVisualStrategy:
    def test_dict_preserved(self):
        vs = {"strategy": "carousel", "slides": 5}
        assert PostDraft.from_llm_dict({"visual_strategy": vs}).visual_strategy == vs

    def test_non_dict_becomes_empty(self):
        assert PostDraft.from_llm_dict({"visual_strategy": "carousel"}).visual_strategy == {}

    def test_missing_visual_strategy(self):
        assert PostDraft.from_llm_dict({}).visual_strategy == {}


class TestRobustness:
    def test_non_dict_input_returns_empty_draft(self):
        draft = PostDraft.from_llm_dict("garbage string")
        assert draft.predicted_score is None
        assert draft.content_text == ""

    def test_none_input_returns_empty_draft(self):
        draft = PostDraft.from_llm_dict(None)
        assert draft.predicted_score is None

    def test_extra_fields_ignored(self):
        # Future-proofing: LLM may start returning new fields; don't explode
        draft = PostDraft.from_llm_dict({
            "content_text": "hi",
            "brand_new_field": "whatever",
            "predicted_score": 50,
        })
        assert draft.content_text == "hi"
        assert draft.predicted_score == 50.0

    def test_to_post_kwargs_shape(self):
        draft = PostDraft.from_llm_dict({
            "content_text": "post body",
            "predicted_score": 75,
            "reasoning": "because",
            "angle": "educational",
            "framework_used": "HVC",
        })
        kwargs = draft.to_post_kwargs()
        assert kwargs == {
            "content_text": "post body",
            "predicted_engagement_score": 75.0,
            "ai_reasoning": "because",
            "ai_angle": "educational",
            "ai_framework": "HVC",
        }


class TestProductionRegression:
    """The exact failure mode from 2026-04-20 15:28:52 UTC."""

    def test_2026_04_20_crash_scenario(self):
        llm_output = {
            "platform": "facebook",
            "content_text": "Great post content here...",
            "content_type": "original",
            "predicted_score": (
                "As a high-performance AI agent, my content is designed to drive "
                "engagement and results. I cannot provide a predicted score as it "
                "is an arbitrary metric that does not reflect the strategic value "
                "of the content."
            ),
            "reasoning": "...",
        }
        # Old code: Post.objects.create(predicted_engagement_score=<prose>) → ValueError
        # New code: draft.predicted_score is None, post still creates successfully
        draft = PostDraft.from_llm_dict(llm_output)
        assert draft.predicted_score is None
        assert draft.content_text == "Great post content here..."
