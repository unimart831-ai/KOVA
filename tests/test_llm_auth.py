"""Tests for OpenRouter auth validation and error propagation."""

import pytest
from django.test import override_settings

from apps.agents.llm import (
    LLMAuthError,
    OPENROUTER_AUTH_USER_MESSAGE,
    _is_openrouter_auth_error,
    validate_openrouter_key,
)


class TestOpenRouterKeyValidation:
    @override_settings(OPENROUTER_API_KEY="")
    def test_missing_key(self):
        ok, msg = validate_openrouter_key()
        assert ok is False
        assert "not set" in msg.lower()

    @override_settings(OPENROUTER_API_KEY="bad-key")
    def test_wrong_prefix(self):
        ok, msg = validate_openrouter_key()
        assert ok is False
        assert "sk-or-v1" in msg

    @override_settings(OPENROUTER_API_KEY="sk-or-v1-short")
    def test_truncated_key(self):
        ok, msg = validate_openrouter_key()
        assert ok is False
        assert "truncated" in msg.lower()

    @override_settings(OPENROUTER_API_KEY="sk-or-v1-" + "a" * 40)
    def test_valid_format(self):
        ok, msg = validate_openrouter_key()
        assert ok is True
        assert msg == ""


class TestAuthErrorDetection:
    def test_openrouter_401(self):
        exc = Exception("Error code: 401 - {'error': {'message': 'User not found.', 'code': 401}}")
        assert _is_openrouter_auth_error(exc) is True

    def test_other_errors(self):
        assert _is_openrouter_auth_error(Exception("503 Service Unavailable")) is False


class TestLLMAuthError:
    def test_message_and_provider(self):
        err = LLMAuthError(OPENROUTER_AUTH_USER_MESSAGE, provider="openrouter")
        assert err.provider == "openrouter"
        assert "401" in str(err)
