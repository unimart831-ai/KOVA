from __future__ import annotations

import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.billing.models import AgencySalesInquiry


@pytest.mark.django_db
class TestAdminSalesInquiryNav:
    def test_staff_sees_sales_inquiry_list(self, client, staff_user):
        inquiry = AgencySalesInquiry.objects.create(
            name="Jane",
            email="jane@agency.co.ke",
            message="Need agency plan",
            status=AgencySalesInquiry.Status.NEW,
        )
        client.force_login(staff_user)
        resp = client.get(reverse("admin_dashboard:sales_inquiry_list"))
        assert resp.status_code == 200
        assert inquiry.email.encode() in resp.content

    def test_sidebar_badge_on_dashboard(self, client, staff_user):
        AgencySalesInquiry.objects.create(
            name="New Lead",
            email="new@agency.co.ke",
            message="Hi",
            status=AgencySalesInquiry.Status.NEW,
        )
        client.force_login(staff_user)
        resp = client.get(reverse("admin_dashboard:overview"))
        assert resp.status_code == 200
        assert b"Agency Sales" in resp.content
        assert b"/dashboard/billing/sales-inquiries" in resp.content


@pytest.mark.django_db
class TestAdminGlobalSearch:
    def test_requires_staff(self, client, user):
        resp = client.get(reverse("admin_dashboard:global_search"), {"q": "test@kova.ai"})
        assert resp.status_code == 302

    def test_finds_user_by_email(self, client, staff_user, user):
        client.force_login(staff_user)
        resp = client.get(reverse("admin_dashboard:global_search"), {"q": user.email})
        assert resp.status_code == 200
        assert user.email.encode() in resp.content
        assert b"Users" in resp.content

    def test_htmx_partial(self, client, staff_user, user):
        client.force_login(staff_user)
        resp = client.get(
            reverse("admin_dashboard:global_search"),
            {"q": user.email},
            HTTP_HX_REQUEST="true",
        )
        assert resp.status_code == 200
        assert user.email.encode() in resp.content

    def test_suggest_requires_staff(self, client, user):
        resp = client.get(reverse("admin_dashboard:global_search_suggest"), {"q": "te"})
        assert resp.status_code == 302

    def test_suggest_returns_200_for_staff(self, client, staff_user, user):
        client.force_login(staff_user)
        resp = client.get(reverse("admin_dashboard:global_search_suggest"), {"q": user.email[:2]})
        assert resp.status_code == 200

    def test_suggest_finds_user(self, client, staff_user, user):
        client.force_login(staff_user)
        resp = client.get(reverse("admin_dashboard:global_search_suggest"), {"q": user.email})
        assert resp.status_code == 200
        assert user.email.encode() in resp.content
        assert b"Users" in resp.content
