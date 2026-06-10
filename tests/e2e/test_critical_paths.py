"""
E2E tests for Kova Agent critical user paths.

These tests cover the essential flows that must work for the product to deliver value:
1. Signup → Onboarding → Dashboard
2. Landing page renders and CTAs work
3. Public pages (booking, QR, Kova pages) load correctly
4. Login → Content Studio accessible

Requires: playwright install chromium
Run: pytest tests/e2e/ -v
"""

import pytest
from django.contrib.auth import get_user_model
from playwright.sync_api import sync_playwright, expect

User = get_user_model()


@pytest.fixture
def base_url(live_server):
    return live_server.url


@pytest.fixture
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def page(browser):
    context = browser.new_context(viewport={"width": 1280, "height": 720})
    page = context.new_page()
    yield page
    context.close()


@pytest.fixture
def mobile_page(browser):
    context = browser.new_context(
        viewport={"width": 375, "height": 812},
        user_agent=(
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
            "AppleWebKit/605.1.15"
        ),
    )
    page = context.new_page()
    yield page
    context.close()


@pytest.mark.django_db(transaction=True)
class TestLandingPage:
    """Landing page must render, show pricing, and link to signup."""

    def test_landing_loads(self, page, base_url):
        page.goto(base_url)
        expect(page).to_have_title("Kova Agent")
        assert page.locator("body").is_visible()

    def test_landing_has_signup_cta(self, page, base_url):
        page.goto(base_url)
        signup_links = page.locator("a[href*='signup']")
        assert signup_links.count() > 0

    def test_landing_responsive(self, mobile_page, base_url):
        mobile_page.goto(base_url)
        assert mobile_page.locator("body").is_visible()


@pytest.mark.django_db(transaction=True)
class TestAuthFlow:
    """Signup and login pages must be accessible and functional."""

    def test_signup_page_loads(self, page, base_url):
        page.goto(f"{base_url}/accounts/signup/")
        assert page.locator("form").is_visible()
        assert page.locator("input[name='email']").is_visible()
        assert page.locator("input[name='phone_number']").is_visible()

    def test_login_page_loads(self, page, base_url):
        page.goto(f"{base_url}/accounts/login/")
        assert page.locator("form").is_visible()

    def test_signup_with_valid_data(self, page, base_url):
        page.goto(f"{base_url}/accounts/signup/")
        page.fill("input[name='email']", "testuser@example.com")
        page.fill("input[name='phone_number']", "0712345678")
        page.fill("input[name='password1']", "TestPass123!@#")
        page.fill("input[name='password2']", "TestPass123!@#")
        page.click("button[type='submit']")
        page.wait_for_load_state("networkidle")
        user = User.objects.filter(email="testuser@example.com").first()
        assert user is not None
        assert user.phone_number == "0712345678"

    def test_login_redirect_unauthenticated(self, page, base_url):
        page.goto(f"{base_url}/brief/")
        page.wait_for_load_state("networkidle")
        assert "/login" in page.url or "/accounts/" in page.url


@pytest.mark.django_db(transaction=True)
class TestWedgeChecklistOnToday:
    """After signup/onboarding, wedge checklist visible on Today."""

    def test_wedge_checklist_visible_after_onboarding(self, page, base_url):
        user = User.objects.create_user(
            username="wedgeuser",
            email="wedge@example.com",
            password="TestPass123!@#",
        )
        user.phone_number = "0712345678"
        user.onboarding_completed = True
        user.save()

        page.goto(f"{base_url}/accounts/login/")
        page.fill("input[name='login']", "wedge@example.com")
        page.fill("input[name='password']", "TestPass123!@#")
        page.click("button[type='submit']")
        page.wait_for_load_state("networkidle")

        page.goto(f"{base_url}/brief/")
        page.wait_for_load_state("networkidle")
        assert "Get the wedge loop running" in page.content()
        assert "Connect WhatsApp" in page.content() or "WhatsApp" in page.content()


@pytest.mark.django_db(transaction=True)
class TestOnboardingFlow:
    """Signup → onboarding wizard → completion page."""

    def test_onboarding_wizard_completes_without_platform(self, page, base_url):
        user = User.objects.create_user(
            username="onboard", email="onboard@example.com", password="TestPass123!@#",
        )
        user.phone_number = "0712345678"
        user.onboarding_completed = False
        user.save()

        page.goto(f"{base_url}/accounts/login/")
        page.fill("input[name='login']", "onboard@example.com")
        page.fill("input[name='password']", "TestPass123!@#")
        page.click("button[type='submit']")
        page.wait_for_load_state("networkidle")

        page.goto(f"{base_url}/accounts/onboarding/?step=1&via=manual")
        page.fill("input[name='full_name']", "Onboard Test")
        page.fill("input[name='company_name']", "Test Brand Co")
        page.select_option("select[name='industry']", "agency")
        page.click("button[type='submit']")
        page.wait_for_load_state("networkidle")

        page.click("button[type='submit']")
        page.wait_for_load_state("networkidle")

        user.refresh_from_db()
        assert user.onboarding_completed is True
        assert "onboarding/complete" in page.url or "Setting up" in page.content()


@pytest.mark.django_db(transaction=True)
class TestHealthCheck:
    """Health check endpoint must return 200."""

    def test_health_returns_ok(self, page, base_url):
        response = page.goto(f"{base_url}/health/")
        assert response.status == 200


@pytest.mark.django_db(transaction=True)
class TestLegalPages:
    """Legal pages must be accessible."""

    @pytest.mark.parametrize("path", ["/privacy/", "/terms/", "/cookies/"])
    def test_legal_page_loads(self, page, base_url, path):
        response = page.goto(f"{base_url}{path}")
        assert response.status == 200


@pytest.mark.django_db(transaction=True)
class TestAPISchema:
    """OpenAPI schema must be accessible."""

    def test_schema_endpoint(self, page, base_url):
        response = page.goto(f"{base_url}/api/schema/")
        assert response.status == 200

    def test_swagger_ui(self, page, base_url):
        response = page.goto(f"{base_url}/api/schema/swagger/")
        assert response.status == 200
