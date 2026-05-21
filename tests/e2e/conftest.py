"""
E2E test configuration for Playwright.

Uses Django's LiveServerTestCase equivalent via pytest-django's live_server fixture.
Run with: pytest tests/e2e/ --headed  (to see the browser)
"""

import pytest


@pytest.fixture(scope="session")
def browser_context_args():
    return {
        "viewport": {"width": 1280, "height": 720},
        "locale": "en-US",
    }


@pytest.fixture
def mobile_context_args():
    return {
        "viewport": {"width": 375, "height": 812},
        "locale": "en-US",
        "user_agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
        ),
    }
