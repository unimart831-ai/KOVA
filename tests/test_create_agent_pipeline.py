"""
End-to-end integration test for the seed → Post pipeline.

Covers the production regression from 2026-04-20: LLM returned prose in
predicted_score, which crashed Post.objects.create() and silently dropped
the whole batch. The test stubs the LLM at the boundary, runs the real
run_create_agent() path, and asserts Posts survive the prose payload.
"""

import json

import pytest

from apps.create.agents.create_agent import run_create_agent
from apps.create.agents.llm import LLMResponse
from apps.create.content.models import ContentSeed, Post
from apps.core.platforms.models import SocialAccount


def _fake_llm(response_dict):
    """Build a fake generate() that returns a fixed JSON payload."""
    payload = json.dumps(response_dict)

    def _fake(*args, **kwargs):
        return LLMResponse(
            content=payload,
            model="test-stub",
            input_tokens=100,
            output_tokens=len(payload) // 4,
            total_tokens=100 + len(payload) // 4,
            duration_ms=50,
            finish_reason="stop",
        )
    return _fake


@pytest.fixture
def connected_account(user):
    return SocialAccount.objects.create(
        user=user,
        platform="twitter",
        platform_user_id="abc123",
        username="testhandle",
        is_active=True,
    )


@pytest.fixture
def seed(user, connected_account):
    return ContentSeed.objects.create(
        user=user,
        idea="Launch announcement for our new AI feature",
        status=ContentSeed.SeedStatus.NEW,
    )


@pytest.mark.django_db
class TestCreateAgentPipeline:
    def test_happy_path_creates_post(self, seed, connected_account, monkeypatch):
        """Valid LLM output → Post is created with parsed fields."""
        llm_output = {
            "batch_strategy": "Authoritative product launch tone",
            "posts": [{
                "platform": "twitter",
                "content_text": "Big news: our new AI feature just shipped. Here's what it does and why it matters for you.",
                "content_type": "original",
                "predicted_score": 82,
                "reasoning": "Clear value prop with curiosity hook",
                "angle": "announcement",
                "framework_used": "AIDA",
            }],
        }
        monkeypatch.setattr(
            "apps.create.agents.create_agent.generate",
            _fake_llm(llm_output),
        )

        posts = run_create_agent(seed)

        assert len(posts) == 1
        post = posts[0]
        assert post.platform == "twitter"
        assert "new AI feature" in post.content_text
        assert post.predicted_engagement_score == 82.0
        assert post.ai_framework == "AIDA"
        assert post.generated_by_agent == "create"

        seed.refresh_from_db()
        assert seed.status != ContentSeed.SeedStatus.FAILED

    def test_prose_in_predicted_score_does_not_drop_post(
        self, seed, connected_account, monkeypatch
    ):
        """2026-04-20 regression: prose score must not crash the batch."""
        prose = (
            "As a high-performance AI agent, my content is designed to drive "
            "engagement and results. I cannot provide a predicted score as it "
            "is an arbitrary metric that does not reflect the strategic value "
            "of the content."
        )
        llm_output = {
            "batch_strategy": "brand voice test",
            "posts": [{
                "platform": "twitter",
                "content_text": "A perfectly good post that should survive the prose-score bug in the old code path.",
                "content_type": "original",
                "predicted_score": prose,
                "reasoning": "valid reasoning",
            }],
        }
        monkeypatch.setattr(
            "apps.create.agents.create_agent.generate",
            _fake_llm(llm_output),
        )

        posts = run_create_agent(seed)

        assert len(posts) == 1, "Pre-fix: this would return [] because Post.objects.create() crashed"
        assert posts[0].predicted_engagement_score is None
        assert "perfectly good post" in posts[0].content_text

    def test_no_connected_platforms_marks_seed_failed(self, user, monkeypatch):
        """Guard path: user with no active platforms → seed.FAILED, no LLM call."""
        seed = ContentSeed.objects.create(
            user=user,
            idea="test idea",
            status=ContentSeed.SeedStatus.NEW,
        )

        def _should_not_be_called(*args, **kwargs):
            raise AssertionError("LLM was called despite no connected platforms")

        monkeypatch.setattr(
            "apps.create.agents.create_agent.generate",
            _should_not_be_called,
        )

        posts = run_create_agent(seed)

        assert posts == []
        seed.refresh_from_db()
        assert seed.status == ContentSeed.SeedStatus.FAILED
        assert "No connected platforms" in seed.error_message

    def test_llm_returns_platform_with_no_account_is_skipped(
        self, seed, connected_account, monkeypatch
    ):
        """LLM hallucinates a platform the user hasn't connected → drop that post, keep others."""
        llm_output = {
            "batch_strategy": "test",
            "posts": [
                {
                    "platform": "instagram",  # not connected
                    "content_text": "Instagram version that should be dropped.",
                    "predicted_score": 70,
                },
                {
                    "platform": "twitter",  # connected
                    "content_text": "Twitter version that should survive the batch, reasonable length.",
                    "predicted_score": 75,
                },
            ],
        }
        monkeypatch.setattr(
            "apps.create.agents.create_agent.generate",
            _fake_llm(llm_output),
        )

        posts = run_create_agent(seed)

        platforms_created = {p.platform for p in posts}
        assert "twitter" in platforms_created
        assert "instagram" not in platforms_created
