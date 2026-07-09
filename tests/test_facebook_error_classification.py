"""Tests for Facebook Graph API error classification."""

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from apps.platforms.providers.instagram_facebook import (
    FacebookProvider,
    _graph_error_details,
    _normalize_fb_post_id,
)


def _mock_response(status_code: int, payload: dict) -> httpx.Response:
    request = httpx.Request("GET", "https://graph.facebook.com/v25.0/test")
    return httpx.Response(status_code, json=payload, request=request)


def test_graph_error_details_treats_code_12_as_non_auth():
    resp = _mock_response(400, {
        "error": {
            "message": "(#12) singular statuses API is deprecated for versions v2.4 and higher",
            "type": "OAuthException",
            "code": 12,
        }
    })
    details = _graph_error_details(resp)
    assert details["code"] == 12
    assert details["is_auth"] is False


def test_graph_error_details_treats_code_190_as_auth():
    resp = _mock_response(400, {
        "error": {
            "message": "Error validating access token",
            "type": "OAuthException",
            "code": 190,
        }
    })
    details = _graph_error_details(resp)
    assert details["code"] == 190
    assert details["is_auth"] is True


def test_normalize_fb_post_id_prefixes_page():
    assert _normalize_fb_post_id("1467491958709106", "109321003896572") == (
        "109321003896572_1467491958709106"
    )
    assert _normalize_fb_post_id("109321003896572_1461340372657598", "109321003896572") == (
        "109321003896572_1461340372657598"
    )


@patch("apps.platforms.providers.instagram_facebook.httpx.Client")
def test_get_comments_skips_deprecated_statuses_error(mock_client_cls):
    provider = FacebookProvider()
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client

    error_payload = {
        "error": {
            "message": "(#12) singular statuses API is deprecated for versions v2.4 and higher",
            "type": "OAuthException",
            "code": 12,
        }
    }
    request = httpx.Request("GET", "https://graph.facebook.com/v25.0/123/comments")
    mock_client.get.return_value = httpx.Response(
        400, json=error_payload, request=request,
    )

    comments = provider.get_comments(
        "page-token",
        "1467491958709106",
        page_id="109321003896572",
    )
    assert comments == []
    called_url = mock_client.get.call_args[0][0]
    assert "109321003896572_1467491958709106" in called_url
