"""Tests for proactive owner WhatsApp alerts (payments + new leads)."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from apps.core.accounts.models import User


@pytest.fixture
def owner(db):
    return User.objects.create_user(
        username="owner", email="owner@kova.ai", password="x",
        full_name="Owner", phone_number="0712345678",
    )


class TestNewLeadAlert:
    @patch("apps.create.briefs.owner_alerts.queue_owner_alert")
    def test_inbound_lead_triggers_alert(self, mock_queue, owner):
        from apps.commerce.leads.models import Lead

        Lead.objects.create(
            user=owner,
            email="customer@example.com",
            name="Jane Customer",
            source_type=Lead.Source.FORM_SUBMISSION,
        )
        assert mock_queue.called
        body = mock_queue.call_args[0][1]
        assert "New lead" in body
        assert "Jane Customer" in body

    @patch("apps.create.briefs.owner_alerts.queue_owner_alert")
    def test_commerce_purchase_lead_skipped(self, mock_queue, owner):
        from apps.commerce.leads.models import Lead

        Lead.objects.create(
            user=owner,
            email="buyer@example.com",
            source_type=Lead.Source.COMMERCE_PURCHASE,
        )
        assert not mock_queue.called

    @patch("apps.create.briefs.owner_alerts.queue_owner_alert")
    def test_manual_lead_skipped(self, mock_queue, owner):
        from apps.commerce.leads.models import Lead

        Lead.objects.create(
            user=owner,
            email="manual@example.com",
            source_type=Lead.Source.MANUAL,
        )
        assert not mock_queue.called


class TestPaymentAlert:
    @patch("apps.commerce.products.commerce_wa_orders._try_whatsapp_owner_alert")
    def test_payment_completion_notifies_seller(
        self, mock_alert, owner, django_capture_on_commit_callbacks,
    ):
        from django.utils import timezone

        from apps.commerce.products.models import CommercePayment, Product

        product = Product.objects.create(user=owner, name="Leather Shoes", price=2500)
        payment = CommercePayment.objects.create(
            user=owner,
            product=product,
            transaction_ref="ref-1",
            checkout_request_id="chk-1",
            phone_number="254798765432",
            amount=2500,
        )
        with django_capture_on_commit_callbacks(execute=True):
            payment.status = CommercePayment.Status.COMPLETED
            payment.receipt_number = "QAB12CD34"
            payment.completed_at = timezone.now()
            payment.save()

        assert mock_alert.called
        body = mock_alert.call_args[0][1]
        assert "Payment received" in body
        assert "Leather Shoes" in body
        assert "QAB12CD34" in body

    @patch("apps.commerce.products.commerce_wa_orders._try_whatsapp_owner_alert")
    def test_no_alert_while_pending(self, mock_alert, owner):
        from apps.commerce.products.models import CommercePayment, Product

        product = Product.objects.create(user=owner, name="Leather Shoes", price=2500)
        CommercePayment.objects.create(
            user=owner,
            product=product,
            transaction_ref="ref-2",
            checkout_request_id="chk-2",
            phone_number="254798765432",
            amount=2500,
        )
        assert not mock_alert.called


class TestSendOwnerAlert:
    def test_skips_without_phone(self, db):
        from apps.create.briefs.owner_alerts import send_owner_alert

        user = User.objects.create_user(
            username="nophone", email="np@kova.ai", password="x", phone_number="",
        )
        assert send_owner_alert(user, "hello") is False

    @patch("apps.core.platforms.providers.whatsapp.WhatsAppProvider.send_text_message")
    def test_sends_via_master_number(self, mock_send, owner, settings):
        from apps.create.briefs.owner_alerts import send_owner_alert

        settings.WHATSAPP_ACCESS_TOKEN = "token"
        settings.WHATSAPP_PHONE_NUMBER_ID = "12345"
        mock_send.return_value = {"success": True}

        assert send_owner_alert(owner, "hello") is True
        kwargs = mock_send.call_args.kwargs
        assert kwargs["to"] == "254712345678"
        assert kwargs["body"] == "hello"
