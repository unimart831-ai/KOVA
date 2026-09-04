"""
Smoke tests for public/marketing pages in default (light) mode.
"""

import pytest


PUBLIC_PAGES = [
    ("/", "landing"),
    ("/accounts/login/", "login"),
    ("/accounts/signup/", "signup"),
    ("/legal/privacy/", "privacy"),
    ("/legal/terms/", "terms"),
    ("/legal/cookies/", "cookies"),
]

# Decorative animation classes removed from public light surfaces (Jun 2026 audit)
DECORATIVE_ANIMATIONS = (
    "animate-ping",
    "animate-glow-breathe",
    "animate-float",
    "animate-pulse-ring",
)


@pytest.mark.django_db
class TestPublicLightModeSmoke:
    @pytest.mark.parametrize("url,name", PUBLIC_PAGES)
    def test_public_page_renders_200(self, client, url, name):
        resp = client.get(url)
        assert resp.status_code == 200, f"{name} ({url}) should return 200"

    @pytest.mark.parametrize("url,name", PUBLIC_PAGES)
    def test_public_page_has_light_background_classes(self, client, url, name):
        resp = client.get(url)
        content = resp.content.decode()
        assert "bg-white" in content or "marketing-section" in content or "brand-atmosphere" in content

    def test_landing_avoids_decorative_pulse_animations(self, client):
        resp = client.get("/")
        content = resp.content.decode()
        for cls in DECORATIVE_ANIMATIONS:
            assert cls not in content, f"landing should not use decorative {cls}"

    def test_landing_north_star_tagline_present(self, client):
        resp = client.get("/")
        assert "chases money" in resp.content.decode()

    def test_login_mission_panel_markup(self, client):
        resp = client.get("/accounts/login/")
        content = resp.content.decode()
        assert "Welcome back" in content
        assert "chases money" in content or "run the shop" in content
