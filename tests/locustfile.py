"""
Kova Agent — Load Testing Suite (Locust)

Usage:
  locust -f tests/locustfile.py --host=http://localhost:8000

  Or against production:
  locust -f tests/locustfile.py --host=https://kovaagent-production.up.railway.app

Configuration:
  Set environment variables before running:
    KOVA_TEST_EMAIL=test@example.com
    KOVA_TEST_PASSWORD=testpass123

  Or use the defaults (test user must exist on target).
"""

import os
import re

from locust import HttpUser, between, task


class KovaUser(HttpUser):
    """Simulates a typical Kova Agent user session."""

    wait_time = between(2, 8)  # Think time between actions (seconds)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.csrf_token = None
        self.email = os.environ.get("KOVA_TEST_EMAIL", "loadtest@kovaagent.com")
        self.password = os.environ.get("KOVA_TEST_PASSWORD", "KovaLoad2026!")

    def _extract_csrf(self, response):
        """Extract CSRF token from a page response."""
        match = re.search(
            r'name=["\']csrfmiddlewaretoken["\'] value=["\']([^"\']+)["\']',
            response.text,
        )
        if match:
            self.csrf_token = match.group(1)
        return self.csrf_token

    def on_start(self):
        """Login at the start of each user session."""
        # Get login page (and CSRF token)
        resp = self.client.get("/accounts/login/", name="/accounts/login [GET]")
        self._extract_csrf(resp)

        if self.csrf_token:
            self.client.post(
                "/accounts/login/",
                data={
                    "login": self.email,
                    "password": self.password,
                    "csrfmiddlewaretoken": self.csrf_token,
                },
                name="/accounts/login [POST]",
                headers={"Referer": f"{self.host}/accounts/login/"},
            )

    # ── HIGH FREQUENCY: Pages users visit most ────────────────────────

    @task(10)
    def view_daily_brief(self):
        """Most visited page — the home/Daily Brief."""
        self.client.get("/brief/", name="/brief/ [Daily Brief]")

    @task(8)
    def view_content_studio(self):
        """Content creation hub."""
        self.client.get("/content/studio/", name="/content/studio/")

    @task(6)
    def view_content_queue(self):
        """Queue of scheduled/published posts."""
        self.client.get("/content/queue/", name="/content/queue/")

    @task(5)
    def view_engage_inbox(self):
        """Unified engagement inbox."""
        self.client.get("/engage/inbox/", name="/engage/inbox/")

    # ── MEDIUM FREQUENCY: Regular checks ──────────────────────────────

    @task(4)
    def view_agent_control(self):
        """Agent control center."""
        self.client.get("/agents/", name="/agents/ [Control]")

    @task(4)
    def view_analytics_insights(self):
        """Analytics insights page."""
        self.client.get("/analytics/insights/", name="/analytics/insights/")

    @task(3)
    def view_content_calendar(self):
        """Content calendar view."""
        self.client.get("/content/calendar/", name="/content/calendar/")

    @task(3)
    def view_competitors(self):
        """Competitor dashboard."""
        self.client.get("/analytics/competitors/", name="/analytics/competitors/")

    @task(3)
    def view_notifications(self):
        """Notifications page."""
        self.client.get("/notifications/", name="/notifications/")

    # ── LOW FREQUENCY: Settings, billing ──────────────────────────────

    @task(2)
    def view_billing(self):
        """Billing overview."""
        self.client.get("/billing/", name="/billing/ [Overview]")

    @task(2)
    def view_platforms(self):
        """Connected platforms list."""
        self.client.get("/platforms/", name="/platforms/ [List]")

    @task(2)
    def view_settings(self):
        """User settings page."""
        self.client.get("/accounts/settings/", name="/accounts/settings/")

    @task(1)
    def view_agent_activity(self):
        """Agent activity log."""
        self.client.get("/agents/activity/", name="/agents/activity/")

    # ── HTMX PARTIALS: Simulates real-time polling ────────────────────

    @task(6)
    def htmx_notification_bell(self):
        """HTMX: notification bell badge (polled frequently)."""
        self.client.get(
            "/notifications/bell/",
            name="/notifications/bell/ [HTMX]",
            headers={"HX-Request": "true"},
        )

    @task(4)
    def htmx_studio_posts(self):
        """HTMX: studio posts partial."""
        self.client.get(
            "/content/studio/posts/",
            name="/content/studio/posts/ [HTMX]",
            headers={"HX-Request": "true"},
        )

    # ── HEALTH CHECK: Should always be fast ───────────────────────────

    @task(1)
    def health_check(self):
        """Health endpoint — should respond < 50ms."""
        self.client.get("/health/", name="/health/")


class UnauthenticatedUser(HttpUser):
    """Simulates unauthenticated visitors (landing, pricing, login page)."""

    wait_time = between(3, 10)
    weight = 1  # 1 unauthenticated for every 3 authenticated

    @task(10)
    def view_landing(self):
        """Marketing landing page."""
        self.client.get("/", name="/ [Landing]")

    @task(5)
    def view_pricing(self):
        """Pricing page."""
        self.client.get("/billing/pricing/", name="/billing/pricing/")

    @task(3)
    def view_login_page(self):
        """Login page (not submitting)."""
        self.client.get("/accounts/login/", name="/accounts/login/ [View]")

    @task(1)
    def view_signup_page(self):
        """Signup page."""
        self.client.get("/accounts/signup/", name="/accounts/signup/ [View]")

    @task(1)
    def health_check(self):
        self.client.get("/health/", name="/health/")
