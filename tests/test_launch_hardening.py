"""Launch-blocking security hardening tests."""

import pytest
from django.test import Client, override_settings

from apps.help.models import Article
from apps.links.models import KovaPage
from apps.utils.html_sanitize import sanitize_html, sanitize_user_css


class TestHtmlSanitize:
    def test_strips_script_tags(self):
        dirty = '<p>Hello</p><script>alert("xss")</script>'
        assert "<script" not in sanitize_html(dirty)
        assert "<p>Hello</p>" in sanitize_html(dirty)

    def test_strips_onclick_handlers(self):
        dirty = '<p onclick="alert(1)">Click</p>'
        cleaned = sanitize_html(dirty)
        assert "onclick" not in cleaned
        assert "Click" in cleaned

    def test_blocks_javascript_href(self):
        dirty = '<a href="javascript:alert(1)">bad</a>'
        cleaned = sanitize_html(dirty)
        assert "javascript:" not in cleaned

    def test_preserves_safe_formatting(self):
        dirty = "<h2>Title</h2><p>Text with <strong>bold</strong>.</p>"
        cleaned = sanitize_html(dirty)
        assert "<h2>Title</h2>" in cleaned
        assert "<strong>bold</strong>" in cleaned

    def test_css_strips_script_injection(self):
        dirty = "body { background: red; } @import url('evil.css'); javascript:alert(1)"
        cleaned = sanitize_user_css(dirty)
        assert "@import" not in cleaned
        assert "javascript:" not in cleaned

    def test_css_strips_html_tags(self):
        assert "<script>" not in sanitize_user_css("body {} </style><script>alert(1)</script>")


@pytest.mark.django_db
class TestArticleHtmlSanitizeOnSave:
    def test_body_html_sanitized_on_save(self, user):
        article = Article(
            slug="xss-test-article",
            title="XSS Test",
            body_html='<p>OK</p><img src=x onerror="alert(1)">',
            status=Article.Status.DRAFT,
        )
        article.save()
        article.refresh_from_db()
        assert "onerror" not in article.body_html
        assert "<p>OK</p>" in article.body_html


@pytest.mark.django_db
class TestKovaPageCssSanitizeOnSave:
    def test_custom_css_sanitized_on_save(self, user):
        page = KovaPage(
            user=user,
            title="Test Page",
            slug="css-test-page",
            custom_css="body { color: red; } @import url('http://evil.com/x.css');",
        )
        page.save()
        assert "@import" not in page.custom_css
        assert "color: red" in page.custom_css


class TestProductionSentryRequired:
    def test_production_settings_require_sentry_dsn(self):
        """Guard must exist — CI deploy check supplies SENTRY_DSN; prod boot fails without it."""
        from pathlib import Path

        source = Path("config/settings/production.py").read_text(encoding="utf-8")
        assert "if not SENTRY_DSN:" in source
        assert "SENTRY_DSN must be set in production" in source


class TestOpenAPISchemaProtection:
    def test_schema_public_in_debug(self):
        client = Client()
        with override_settings(DEBUG=True):
            response = client.get("/api/schema/")
            assert response.status_code == 200

    def test_schema_blocked_for_anonymous_in_production(self):
        client = Client()
        with override_settings(DEBUG=False):
            response = client.get("/api/schema/")
            assert response.status_code in (401, 403)

    def test_schema_accessible_for_staff_in_production(self, staff_user):
        client = Client()
        client.force_login(staff_user)
        with override_settings(DEBUG=False):
            response = client.get("/api/schema/")
            assert response.status_code == 200
