"""Tests for daily brief WhatsApp button helpers."""
from __future__ import annotations

from django.test import SimpleTestCase, override_settings

from apps.create.briefs.whatsapp_buttons import (
    build_daily_brief_template_components,
    map_button_inbound,
)


class TestMapButtonInbound(SimpleTestCase):
    def test_button_id(self):
        assert map_button_inbound("brief_approve", "") == "approve"

    def test_title_case_insensitive(self):
        assert map_button_inbound("", "Approve") == "approve"

    def test_unknown_passthrough(self):
        assert map_button_inbound("", "custom text") == "custom text"


@override_settings(KOVA_DAILY_BRIEF_URL_SUFFIX="utm_source=whatsapp")
class TestBuildTemplateComponents(SimpleTestCase):
    def test_body_and_url_button(self):
        components = build_daily_brief_template_components("Jane", "3 posts waiting", "72/100")
        assert len(components) == 2
        assert components[0]["type"] == "body"
        assert components[1]["sub_type"] == "url"
        assert components[1]["parameters"][0]["text"] == "utm_source=whatsapp"

    @override_settings(KOVA_DAILY_BRIEF_URL_SUFFIX="")
    def test_no_url_button_when_suffix_empty(self):
        components = build_daily_brief_template_components("Jane", "Hi", "70/100")
        assert len(components) == 1
