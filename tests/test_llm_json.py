"""
Tests for apps.agents.llm.parse_llm_json — the 5-stage repair pipeline
that extracts valid JSON from messy LLM output.
"""

import json

import pytest

from apps.agents.llm import parse_llm_json


# ── 1. Clean JSON ────────────────────────────────────────────────────

class TestCleanJSON:
    def test_simple_object(self):
        raw = '{"brand_voice": "Bold and direct", "tone": "confident"}'
        assert parse_llm_json(raw) == {"brand_voice": "Bold and direct", "tone": "confident"}

    def test_simple_array(self):
        raw = '["pillar1", "pillar2", "pillar3"]'
        assert parse_llm_json(raw) == ["pillar1", "pillar2", "pillar3"]

    def test_nested_object(self):
        raw = '{"posts": [{"text": "hello"}, {"text": "world"}], "count": 2}'
        result = parse_llm_json(raw)
        assert result["count"] == 2
        assert len(result["posts"]) == 2

    def test_with_whitespace(self):
        raw = '  \n  {"key": "value"}  \n  '
        assert parse_llm_json(raw) == {"key": "value"}

    def test_with_bom(self):
        raw = '\ufeff{"key": "value"}'
        assert parse_llm_json(raw) == {"key": "value"}


# ── 2. Markdown fences ──────────────────────────────────────────────

class TestMarkdownFences:
    def test_json_fence(self):
        raw = '```json\n{"brand": "Kova"}\n```'
        assert parse_llm_json(raw) == {"brand": "Kova"}

    def test_plain_fence(self):
        raw = '```\n{"brand": "Kova"}\n```'
        assert parse_llm_json(raw) == {"brand": "Kova"}

    def test_fence_with_trailing_whitespace(self):
        raw = '```json\n{"key": "val"}\n```  '
        assert parse_llm_json(raw) == {"key": "val"}

    def test_fence_with_array(self):
        raw = '```json\n["a", "b", "c"]\n```'
        assert parse_llm_json(raw) == ["a", "b", "c"]


# ── 3. Prose preamble ───────────────────────────────────────────────

class TestProsePreamble:
    def test_preamble_before_object(self):
        raw = 'Here is the JSON response:\n{"tone": "witty"}'
        assert parse_llm_json(raw) == {"tone": "witty"}

    def test_preamble_with_newlines(self):
        raw = "Sure! Here's your brand profile:\n\n{\"voice\": \"bold\"}"
        assert parse_llm_json(raw) == {"voice": "bold"}

    def test_prose_and_trailing_text(self):
        raw = 'The result is: {"x": 1} Hope that helps!'
        assert parse_llm_json(raw) == {"x": 1}

    def test_think_block_removal(self):
        raw = '<think>I need to generate JSON...</think>\n{"key": "value"}'
        assert parse_llm_json(raw) == {"key": "value"}

    def test_pure_prose_no_json(self):
        raw = "We need to output JSON with keys format, tone, and audience."
        with pytest.raises(json.JSONDecodeError, match="prose instead of JSON"):
            parse_llm_json(raw)


# ── 4. Smart / curly quotes ─────────────────────────────────────────

class TestSmartQuotes:
    def test_curly_double_quotes(self):
        raw = '{\u201cbrand\u201d: \u201cKova\u201d}'
        assert parse_llm_json(raw) == {"brand": "Kova"}

    def test_curly_single_quotes_in_values(self):
        raw = '{"msg": "it\u2019s great"}'
        assert parse_llm_json(raw) == {"msg": "it's great"}

    def test_unicode_dashes(self):
        raw = '{"range": "10\u201320"}'
        assert parse_llm_json(raw) == {"range": "10-20"}

    def test_ellipsis_char(self):
        raw = '{"text": "wait\u2026"}'
        assert parse_llm_json(raw) == {"text": "wait..."}


# ── 5. Truncated JSON (missing closing braces) ──────────────────────

class TestTruncatedJSON:
    def test_missing_closing_brace(self):
        raw = '{"brand": "Kova", "tone": "bold"'
        result = parse_llm_json(raw)
        assert result["brand"] == "Kova"
        assert result["tone"] == "bold"

    def test_missing_closing_bracket_and_brace(self):
        raw = '{"items": ["a", "b"'
        result = parse_llm_json(raw)
        assert result["items"] == ["a", "b"]

    def test_truncated_mid_string(self):
        raw = '{"text": "This is a long post that got cut off'
        result = parse_llm_json(raw)
        assert "This is a long post" in result["text"]

    def test_truncated_with_trailing_comma(self):
        raw = '{"a": 1, "b": 2,'
        result = parse_llm_json(raw)
        assert result["a"] == 1
        assert result["b"] == 2


# ── 6. Truncated posts array ────────────────────────────────────────

class TestTruncatedPosts:
    def test_salvages_complete_posts(self):
        """Stage 4 repairs truncated JSON and keeps partial posts
        (design: 'a truncated post is better than an empty one')."""
        raw = (
            '{"format": "carousel", "posts": ['
            '{"text": "Post one", "hashtags": ["#ai"]}, '
            '{"text": "Post two", "hashtags": ["#brand"]}, '
            '{"text": "Post three that got trun'
        )
        result = parse_llm_json(raw)
        assert "posts" in result
        assert len(result["posts"]) >= 2
        assert result["posts"][0]["text"] == "Post one"
        assert result["posts"][1]["text"] == "Post two"

    def test_salvages_single_complete_post(self):
        """Partial second post is preserved by the truncation repair."""
        raw = (
            '{"tone": "bold", "posts": ['
            '{"text": "Only complete one"}, '
            '{"text": "incomplete'
        )
        result = parse_llm_json(raw)
        assert len(result["posts"]) >= 1
        assert result["posts"][0]["text"] == "Only complete one"

    def test_stage5_salvage_when_repair_fails(self):
        """Stage 5 kicks in when the truncation lands inside nested structure
        that Stage 4 can't close cleanly."""
        raw = (
            '{"posts": ['
            '{"text": "Good post", "meta": {"id": 1}}, '
            '{"text": "Bad post", "meta": {"id":'
        )
        result = parse_llm_json(raw)
        assert "posts" in result
        assert result["posts"][0]["text"] == "Good post"


# ── 7. Completely invalid input ─────────────────────────────────────

class TestInvalidInput:
    def test_empty_string(self):
        with pytest.raises(json.JSONDecodeError, match="empty response"):
            parse_llm_json("")

    def test_whitespace_only(self):
        with pytest.raises(json.JSONDecodeError, match="empty response"):
            parse_llm_json("   \n\t  ")

    def test_none_input(self):
        with pytest.raises((json.JSONDecodeError, TypeError, AttributeError)):
            parse_llm_json(None)

    def test_random_garbage(self):
        with pytest.raises(json.JSONDecodeError):
            parse_llm_json("!@#$%^&*()_+")

    def test_html_without_json(self):
        with pytest.raises(json.JSONDecodeError):
            parse_llm_json("<html><body>Hello</body></html>")


# ── 8. Trailing commas ──────────────────────────────────────────────

class TestTrailingCommas:
    def test_trailing_comma_in_object(self):
        raw = '{"a": 1, "b": 2,}'
        result = parse_llm_json(raw)
        assert result == {"a": 1, "b": 2}

    def test_trailing_comma_in_array(self):
        raw = '["x", "y", "z",]'
        result = parse_llm_json(raw)
        assert result == ["x", "y", "z"]

    def test_trailing_comma_nested(self):
        raw = '{"list": ["a", "b",], "val": 1,}'
        result = parse_llm_json(raw)
        assert result == {"list": ["a", "b"], "val": 1}


# ── 9. Edge cases ───────────────────────────────────────────────────

class TestEdgeCases:
    def test_single_quoted_json(self):
        raw = "{'key': 'value'}"
        result = parse_llm_json(raw)
        assert result == {"key": "value"}

    def test_control_characters_stripped(self):
        raw = '{"key": "val\x00ue"}'
        result = parse_llm_json(raw)
        assert result["key"] == "value"

    def test_newlines_inside_string_values(self):
        raw = '{"bio": "Line one\nLine two"}'
        result = parse_llm_json(raw)
        assert "Line one" in result["bio"]
        assert "Line two" in result["bio"]

    def test_array_at_top_level_in_prose(self):
        raw = 'Here are the results: [{"id": 1}, {"id": 2}]'
        result = parse_llm_json(raw)
        assert len(result) == 2
        assert result[0]["id"] == 1

    def test_real_brand_builder_response(self):
        """Simulates a realistic AI Brand Builder response."""
        raw = '''```json
{
  "brand_voice": "Bold, direct, and unapologetically ambitious.",
  "target_audience": "Entrepreneurs aged 25-45 who want to scale.",
  "content_pillars": ["Growth hacks", "Founder stories", "Industry trends", "Product updates"],
  "tone_attributes": ["confident", "bold", "educational"],
  "brand_voice_examples": ["We don't follow trends — we set them."],
  "brand_restrictions": "Never use corporate jargon. Never promise guaranteed results."
}
```'''
        result = parse_llm_json(raw)
        assert result["brand_voice"].startswith("Bold")
        assert len(result["content_pillars"]) == 4
        assert "confident" in result["tone_attributes"]
