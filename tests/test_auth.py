"""
Tests for authentication, access control, and admin decorators.
"""

import pytest
from django.test import RequestFactory

from apps.core.accounts.models import User
from apps.core.admin_dashboard.decorators import superuser_required, senior_staff_required


@pytest.mark.django_db
class TestAuthFlows:
    def test_login_redirect_for_anonymous(self, client):
        for url in ["/content/", "/briefs/", "/engage/", "/analytics/"]:
            resp = client.get(url)
            assert resp.status_code == 302, f"{url} should redirect anonymous users"

    def test_login_with_valid_credentials(self, client, user):
        logged_in = client.login(email="test@kova.ai", password="TestPass123!")
        assert logged_in is True

    def test_login_with_wrong_password(self, client, user):
        logged_in = client.login(email="test@kova.ai", password="WrongPass!")
        assert logged_in is False


@pytest.mark.django_db
class TestAdminDecorators:
    def _make_request(self, user):
        rf = RequestFactory()
        request = rf.get("/fake/")
        request.user = user
        return request

    def test_superuser_required_blocks_regular_staff(self, staff_user):
        @superuser_required
        def my_view(request):
            return "ok"

        request = self._make_request(staff_user)
        # Should add message and redirect
        from django.contrib.messages.storage.fallback import FallbackStorage
        setattr(request, "session", "session")
        messages = FallbackStorage(request)
        setattr(request, "_messages", messages)

        resp = my_view(request)
        assert resp.status_code == 302

    def test_superuser_required_allows_superuser(self, superuser):
        from django.http import HttpResponse

        @superuser_required
        def my_view(request):
            return HttpResponse("ok")

        request = self._make_request(superuser)
        resp = my_view(request)
        assert resp.status_code == 200

    def test_senior_staff_required_blocks_regular_staff(self, staff_user):
        @senior_staff_required
        def my_view(request):
            return "ok"

        request = self._make_request(staff_user)
        from django.contrib.messages.storage.fallback import FallbackStorage
        setattr(request, "session", "session")
        messages = FallbackStorage(request)
        setattr(request, "_messages", messages)

        resp = my_view(request)
        assert resp.status_code == 302
