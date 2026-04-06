"""
Tests for the AI agent system: configs, actions, task logging.
"""

import pytest

from apps.accounts.models import User, UserProfile
from apps.agents.models import AgentConfig, AgentAction


@pytest.mark.django_db
class TestAgentConfig:
    def test_create_all_agent_types(self, user):
        for agent_type, _ in AgentConfig.AgentType.choices:
            config = AgentConfig.objects.create(user=user, agent_type=agent_type)
            assert config.is_active is True
            assert config.name  # property returns display name
            assert config.icon  # property returns emoji
            assert config.role  # property returns description

    def test_unique_per_user(self, user):
        AgentConfig.objects.create(user=user, agent_type="research")
        with pytest.raises(Exception):  # IntegrityError
            AgentConfig.objects.create(user=user, agent_type="research")


@pytest.mark.django_db
class TestAgentAction:
    def test_log_action(self, user):
        action = AgentAction.objects.create(
            user=user,
            agent_type="create",
            action_type="generate_posts",
            description="Generated 3 Twitter posts from seed",
            status=AgentAction.ActionStatus.COMPLETED,
            tokens_used=1500,
            input_tokens=800,
            output_tokens=700,
            model_used="openai/gpt-4o-mini",
            duration_ms=3200,
        )
        assert action.pk is not None
        assert action.tokens_used == 1500

    def test_outcome_tracking(self, user):
        action = AgentAction.objects.create(
            user=user,
            agent_type="analyst",
            action_type="predict_engagement",
            description="Predicted engagement scores for batch",
            status=AgentAction.ActionStatus.COMPLETED,
            outcome_score=72.5,
            outcome_data={"prediction_accuracy": 0.85, "avg_error": 0.12},
        )
        assert action.outcome_score == 72.5
        assert action.outcome_data["prediction_accuracy"] == 0.85

    def test_composite_index_used(self, user):
        """Ensure the composite indexes we added exist on the model Meta."""
        indexes = AgentAction._meta.indexes
        field_sets = [tuple(idx.fields) for idx in indexes]
        assert ("user", "agent_type", "-created_at") in field_sets
        assert ("user", "status", "-created_at") in field_sets
        assert ("agent_type", "status", "-created_at") in field_sets
