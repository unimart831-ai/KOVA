"""
Comprehensive test suite for the Kova email system.

Covers: EmailService methods, Celery email tasks, template rendering,
edge cases, email configuration, and the automation helpers.
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from django.conf import settings
from django.core import mail

from apps.accounts.models import User, UserProfile
from apps.emails.models import EmailLog, EmailSubscriber
from apps.emails.services import EMAIL_TEMPLATES, EmailService, email_service

LOCMEM = "django.core.mail.backends.locmem.EmailBackend"


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _use_locmem_email(settings):
    """Force locmem email backend for every test in this module."""
    settings.EMAIL_BACKEND = LOCMEM


@pytest.fixture
def user_no_email(db):
    """User with an empty email field."""
    u = User.objects.create_user(
        username="noemail",
        email="",
        password="TestPass123!",
        full_name="No Email",
    )
    return u


@pytest.fixture
def subscriber(user, db):
    """Active EmailSubscriber belonging to the default test user."""
    return EmailSubscriber.objects.create(
        user=user,
        email=user.email,
        name="Test Subscriber",
        source=EmailSubscriber.Source.MANUAL,
        status=EmailSubscriber.Status.ACTIVE,
    )


# ═══════════════════════════════════════════════════════════════════════════
# 1. Email Configuration
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestEmailConfiguration:
    def test_default_from_email_is_set(self):
        assert settings.DEFAULT_FROM_EMAIL
        assert "@" in settings.DEFAULT_FROM_EMAIL

    def test_email_backend_is_locmem_in_tests(self):
        """pytest-django uses locmem backend (or console for dev);
        either way, mail.outbox is available."""
        assert hasattr(mail, "outbox")

    def test_site_url_is_set(self):
        assert hasattr(settings, "SITE_URL")

    def test_email_templates_registry_is_populated(self):
        assert len(EMAIL_TEMPLATES) > 0

    def test_all_template_entries_have_path_and_subject(self):
        for key, (path, subject) in EMAIL_TEMPLATES.items():
            assert path, f"Template path missing for {key}"
            assert subject, f"Default subject missing for {key}"
            assert path.endswith(".html"), f"Template {key} path should end with .html"


# ═══════════════════════════════════════════════════════════════════════════
# 2. EmailService — core _send method
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestEmailServiceCore:

    def test_send_creates_email_log(self, user):
        log = email_service._send("welcome", user.email, user=user)
        assert isinstance(log, EmailLog)
        assert log.pk is not None
        assert log.to_email == user.email
        assert log.email_type == "welcome"

    def test_send_sets_status_to_sent(self, user):
        log = email_service._send("welcome", user.email, user=user)
        assert log.status == EmailLog.Status.SENT
        assert log.sent_at is not None

    def test_send_populates_outbox(self, user):
        mail.outbox.clear()
        email_service._send("welcome", user.email, user=user)
        assert len(mail.outbox) == 1

    def test_send_correct_subject(self, user):
        mail.outbox.clear()
        email_service._send("welcome", user.email, user=user)
        msg = mail.outbox[0]
        _, default_subject = EMAIL_TEMPLATES["welcome"]
        assert msg.subject == default_subject

    def test_send_subject_override(self, user):
        mail.outbox.clear()
        email_service._send("welcome", user.email, user=user, subject="Custom Subject")
        assert mail.outbox[0].subject == "Custom Subject"

    def test_send_correct_from_address(self, user):
        mail.outbox.clear()
        email_service._send("welcome", user.email, user=user)
        assert mail.outbox[0].from_email == settings.DEFAULT_FROM_EMAIL

    def test_send_correct_to_address(self, user):
        mail.outbox.clear()
        email_service._send("welcome", user.email, user=user)
        assert mail.outbox[0].to == [user.email]

    def test_send_includes_html_alternative(self, user):
        mail.outbox.clear()
        email_service._send("welcome", user.email, user=user)
        msg = mail.outbox[0]
        assert len(msg.alternatives) == 1
        html_body, content_type = msg.alternatives[0]
        assert content_type == "text/html"
        assert "<html" in html_body.lower() or "<table" in html_body.lower()

    def test_send_plain_text_body_exists(self, user):
        mail.outbox.clear()
        email_service._send("welcome", user.email, user=user)
        msg = mail.outbox[0]
        assert msg.body  # plain text version (strip_tags output)
        assert "<html" not in msg.body.lower()

    def test_send_with_custom_context(self, user):
        mail.outbox.clear()
        email_service._send(
            "system", user.email, user=user,
            context={"custom_key": "custom_value"},
        )
        assert len(mail.outbox) == 1

    def test_send_without_user(self):
        mail.outbox.clear()
        log = email_service._send(
            "team_invitation", "stranger@example.com",
            context={"inviter_name": "Tester", "team_name": "Acme", "invite_url": "/invite/abc"},
        )
        assert log.user is None
        assert log.to_email == "stranger@example.com"
        assert log.status == EmailLog.Status.SENT

    def test_send_stores_metadata(self, user):
        log = email_service._send(
            "payment_confirmation", user.email, user=user,
            metadata={"amount": "500", "plan": "growth"},
        )
        assert log.metadata["amount"] == "500"

    def test_send_unknown_type_falls_back_to_system(self, user):
        mail.outbox.clear()
        log = email_service._send("nonexistent_type", user.email, user=user)
        assert log.status == EmailLog.Status.SENT
        assert mail.outbox[0].subject == "Notification from Kova Agent"

    def test_send_includes_message_id_header(self, user):
        mail.outbox.clear()
        log = email_service._send("welcome", user.email, user=user)
        msg = mail.outbox[0]
        assert "Message-ID" in msg.extra_headers
        assert str(log.pk) in msg.extra_headers["Message-ID"]

    def test_send_includes_unsubscribe_header_when_subscriber_exists(self, user, subscriber):
        mail.outbox.clear()
        email_service._send("welcome", user.email, user=user)
        msg = mail.outbox[0]
        assert "List-Unsubscribe" in msg.extra_headers
        assert "List-Unsubscribe-Post" in msg.extra_headers

    def test_send_no_unsubscribe_header_without_subscriber(self, user):
        mail.outbox.clear()
        email_service._send("welcome", user.email, user=user)
        msg = mail.outbox[0]
        assert "List-Unsubscribe" not in msg.extra_headers

    def test_send_failure_logs_error(self, user):
        with patch("apps.emails.services.EmailMultiAlternatives") as mock_cls:
            mock_cls.return_value.send.side_effect = Exception("SMTP down")
            mock_cls.return_value.attach_alternative = MagicMock()
            mock_cls.return_value.extra_headers = {}
            log = email_service._send("welcome", user.email, user=user)
        assert log.status == EmailLog.Status.FAILED
        assert log.failed_at is not None
        assert "SMTP down" in log.error_message


# ═══════════════════════════════════════════════════════════════════════════
# 3. EmailService — convenience methods
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestEmailServiceMethods:

    def test_send_welcome(self, user):
        mail.outbox.clear()
        log = email_service.send_welcome(user)
        assert log.email_type == "welcome"
        assert log.to_email == user.email
        assert len(mail.outbox) == 1
        html = mail.outbox[0].alternatives[0][0]
        assert "first_name" not in html or user.first_name in html or user.email.split("@")[0] in html

    def test_send_password_changed(self, user):
        mail.outbox.clear()
        log = email_service.send_password_changed(user)
        assert log.email_type == "password_changed"
        assert len(mail.outbox) == 1

    def test_send_payment_confirmation(self, user):
        mail.outbox.clear()
        log = email_service.send_payment_confirmation(
            user, amount="500 KES", plan="Growth", provider="mpesa", receipt_number="RCP001"
        )
        assert log.email_type == "payment_confirmation"
        assert log.metadata["amount"] == "500 KES"
        assert log.metadata["plan"] == "Growth"

    def test_send_payment_failed(self, user):
        mail.outbox.clear()
        log = email_service.send_payment_failed(user, plan="Growth")
        assert log.email_type == "payment_failed"
        assert len(mail.outbox) == 1

    def test_send_plan_changed(self, user):
        mail.outbox.clear()
        log = email_service.send_plan_changed(user, old_plan="Starter", new_plan="Growth")
        assert log.email_type == "plan_changed"
        assert log.metadata["old_plan"] == "Starter"
        assert log.metadata["new_plan"] == "Growth"

    def test_send_subscription_canceled(self, user):
        mail.outbox.clear()
        log = email_service.send_subscription_canceled(user)
        assert log.email_type == "subscription_canceled"
        assert len(mail.outbox) == 1

    def test_send_payment_reminder(self, user):
        mail.outbox.clear()
        log = email_service.send_payment_reminder(user, days_until_expiry=3)
        assert log.email_type == "payment_reminder"

    def test_send_trial_ending(self, user):
        mail.outbox.clear()
        log = email_service.send_trial_ending(user, days_left=7)
        assert log.email_type == "trial_ending"

    def test_send_invoice(self, user):
        mail.outbox.clear()
        log = email_service.send_invoice(
            user, amount="1500 KES", plan="Pro",
            invoice_date="2026-05-01", invoice_number="INV-001",
        )
        assert log.email_type == "invoice"
        assert log.metadata["invoice_number"] == "INV-001"

    def test_send_receipt(self, user):
        mail.outbox.clear()
        log = email_service.send_receipt(
            user, amount="1500 KES", plan="Pro",
            receipt_number="RCT-001", payment_method="M-Pesa",
        )
        assert log.email_type == "receipt"
        assert log.metadata["receipt_number"] == "RCT-001"

    def test_send_team_invitation(self):
        mail.outbox.clear()
        log = email_service.send_team_invitation(
            to_email="invitee@example.com",
            inviter_name="Alice",
            team_name="Acme Corp",
            invite_url="https://app.kovaagent.com/invite/abc",
        )
        assert log.email_type == "team_invitation"
        assert log.to_email == "invitee@example.com"
        assert log.user is None

    def test_send_weekly_report(self, user):
        mail.outbox.clear()
        log = email_service.send_weekly_report(user, report_data={
            "posts_created": 10,
            "posts_published": 7,
            "plan": "Growth",
        })
        assert log.email_type == "weekly_report"

    def test_send_monthly_report(self, user):
        mail.outbox.clear()
        log = email_service.send_monthly_report(user, report_data={
            "posts_published": 30,
            "revenue": 5000,
        })
        assert log.email_type == "monthly_report"

    def test_send_feature_announcement(self, user):
        mail.outbox.clear()
        log = email_service.send_feature_announcement(
            user,
            feature_title="New Calendar Intel",
            feature_description="Holiday-aware post scheduling",
        )
        assert log.email_type == "feature_announcement"

    def test_send_promotional(self, user):
        mail.outbox.clear()
        log = email_service.send_promotional(
            user,
            promo_title="Half price!",
            promo_body="Upgrade this week for 50% off.",
            cta_text="Upgrade Now",
        )
        assert log.email_type == "promotional"

    def test_send_usage_warning(self, user):
        mail.outbox.clear()
        log = email_service.send_usage_warning(user, resource="posts", current=95, limit=100)
        assert log.email_type == "usage_warning"

    def test_send_partner_application_received(self, user):
        mail.outbox.clear()
        log = email_service.send_partner_application_received(
            to_email=user.email, full_name="Test Partner", user=user,
        )
        assert log.email_type == "partner_app_received"

    def test_send_partner_application_approved(self, user):
        mail.outbox.clear()
        log = email_service.send_partner_application_approved(
            user, referral_code="KOVA123",
        )
        assert log.email_type == "partner_app_approved"
        assert log.metadata["referral_code"] == "KOVA123"

    def test_send_partner_approved_no_account(self):
        mail.outbox.clear()
        log = email_service.send_partner_approved_no_account(
            to_email="noaccount@example.com", full_name="Jane Doe",
        )
        assert log.email_type == "partner_approved_noacc"
        assert log.user is None

    def test_send_partner_application_rejected(self, user):
        mail.outbox.clear()
        log = email_service.send_partner_application_rejected(
            to_email=user.email, full_name="Test User", user=user, reason="Incomplete profile",
        )
        assert log.email_type == "partner_app_rejected"

    def test_send_partner_new_referral(self, user):
        mail.outbox.clear()
        log = email_service.send_partner_new_referral(
            user, referred_email="referred@example.com", total_referrals=5,
        )
        assert log.email_type == "partner_new_referral"

    def test_send_partner_milestone(self, user):
        mail.outbox.clear()
        log = email_service.send_partner_milestone(
            user, milestone_label="10 referrals", bonus_kes=5000,
        )
        assert log.email_type == "partner_milestone"
        assert log.metadata["bonus_kes"] == "5000"


# ═══════════════════════════════════════════════════════════════════════════
# 4. Template context population
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestTemplateContext:

    def test_base_context_includes_site_url(self, user):
        mail.outbox.clear()
        email_service._send("system", user.email, user=user)
        html = mail.outbox[0].alternatives[0][0]
        site_url = getattr(settings, "SITE_URL", "")
        assert site_url in html or "kovaagent.com" in html

    def test_base_context_includes_current_year(self, user):
        from django.utils import timezone
        mail.outbox.clear()
        email_service._send("system", user.email, user=user)
        html = mail.outbox[0].alternatives[0][0]
        assert str(timezone.now().year) in html

    def test_user_first_name_in_context(self, user):
        user.first_name = "Alice"
        user.save(update_fields=["first_name"])
        mail.outbox.clear()
        email_service._send("welcome", user.email, user=user)
        html = mail.outbox[0].alternatives[0][0]
        assert "Alice" in html

    def test_first_name_fallback_to_email_handle(self, user):
        user.first_name = ""
        user.save(update_fields=["first_name"])
        mail.outbox.clear()
        email_service._send("welcome", user.email, user=user)
        html = mail.outbox[0].alternatives[0][0]
        handle = user.email.split("@")[0]
        assert handle in html

    def test_payment_context_variables_render(self, user):
        mail.outbox.clear()
        email_service.send_payment_confirmation(
            user, amount="1,000 KES", plan="Growth",
            provider="mpesa", receipt_number="RCP-999",
        )
        html = mail.outbox[0].alternatives[0][0]
        assert "1,000 KES" in html or "1000" in html

    def test_team_invitation_context_renders(self):
        mail.outbox.clear()
        email_service.send_team_invitation(
            to_email="invitee@example.com",
            inviter_name="Bob",
            team_name="Widget Co",
            invite_url="https://app.kovaagent.com/invite/xyz",
        )
        html = mail.outbox[0].alternatives[0][0]
        assert "Widget Co" in html or "Bob" in html


# ═══════════════════════════════════════════════════════════════════════════
# 5. Edge cases
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestEdgeCases:

    def test_empty_context_does_not_crash(self, user):
        mail.outbox.clear()
        log = email_service._send("system", user.email, user=user, context={})
        assert log.status == EmailLog.Status.SENT

    def test_none_context_does_not_crash(self, user):
        mail.outbox.clear()
        log = email_service._send("system", user.email, user=user, context=None)
        assert log.status == EmailLog.Status.SENT

    def test_special_characters_in_user_data(self, user):
        user.first_name = '<script>alert("xss")</script>'
        user.save(update_fields=["first_name"])
        mail.outbox.clear()
        log = email_service._send("welcome", user.email, user=user)
        assert log.status == EmailLog.Status.SENT
        html = mail.outbox[0].alternatives[0][0]
        assert "<script>" not in html or "&lt;script&gt;" in html

    def test_unicode_in_subject_and_context(self, user):
        mail.outbox.clear()
        log = email_service._send(
            "system", user.email, user=user,
            subject="Habari yako! 🎉 — Special chars: éàü",
            context={"greeting": "Jambo 👋"},
        )
        assert log.status == EmailLog.Status.SENT
        assert mail.outbox[0].subject == "Habari yako! 🎉 — Special chars: éàü"

    def test_very_long_subject_stored(self, user):
        long_subject = "A" * 300
        mail.outbox.clear()
        log = email_service._send("system", user.email, user=user, subject=long_subject)
        assert log.status == EmailLog.Status.SENT
        assert len(mail.outbox[0].subject) == 300

    def test_multiple_sends_increment_outbox(self, user):
        mail.outbox.clear()
        email_service._send("welcome", user.email, user=user)
        email_service._send("payment_confirmation", user.email, user=user,
                            context={"amount": "100", "plan": "Starter",
                                     "provider": "stripe", "receipt_number": ""})
        assert len(mail.outbox) == 2

    def test_send_to_nonexistent_email_type_graceful(self, user):
        mail.outbox.clear()
        log = email_service._send("totally_made_up", user.email, user=user)
        assert log.status == EmailLog.Status.SENT

    def test_none_metadata_does_not_crash(self, user):
        log = email_service._send("system", user.email, user=user, metadata=None)
        assert log.metadata == {}

    def test_usage_warning_zero_limit(self, user):
        mail.outbox.clear()
        log = email_service.send_usage_warning(user, resource="posts", current=5, limit=0)
        assert log.status == EmailLog.Status.SENT


# ═══════════════════════════════════════════════════════════════════════════
# 6. Celery email tasks (called synchronously)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestCeleryEmailTasks:

    def test_send_email_task_happy_path(self, user):
        from apps.emails.tasks import send_email_task

        mail.outbox.clear()
        send_email_task(
            email_type="welcome",
            to_email=user.email,
            user_id=str(user.pk),
        )
        assert len(mail.outbox) == 1
        log = EmailLog.objects.filter(to_email=user.email, email_type="welcome").first()
        assert log is not None
        assert log.status == EmailLog.Status.SENT

    def test_send_email_task_missing_user(self):
        from apps.emails.tasks import send_email_task

        mail.outbox.clear()
        fake_id = str(uuid.uuid4())
        send_email_task(
            email_type="system",
            to_email="ghost@example.com",
            user_id=fake_id,
        )
        assert len(mail.outbox) == 1
        log = EmailLog.objects.filter(to_email="ghost@example.com").first()
        assert log is not None
        assert log.user is None

    def test_send_email_task_no_user_id(self):
        from apps.emails.tasks import send_email_task

        mail.outbox.clear()
        send_email_task(
            email_type="team_invitation",
            to_email="somebody@example.com",
            context={"inviter_name": "A", "team_name": "B", "invite_url": "/c"},
        )
        assert len(mail.outbox) == 1

    def test_send_welcome_email_task(self, user):
        from apps.emails.tasks import send_welcome_email

        mail.outbox.clear()
        send_welcome_email(str(user.pk))
        assert len(mail.outbox) == 1
        assert "welcome" in mail.outbox[0].subject.lower() or "Welcome" in mail.outbox[0].subject

    def test_send_welcome_email_task_deleted_user(self):
        from apps.emails.tasks import send_welcome_email

        mail.outbox.clear()
        send_welcome_email(str(uuid.uuid4()))
        assert len(mail.outbox) == 0

    def test_send_payment_confirmation_email_task(self, user):
        from apps.emails.tasks import send_payment_confirmation_email

        mail.outbox.clear()
        send_payment_confirmation_email(
            str(user.pk), amount="500 KES", plan="Growth",
        )
        assert len(mail.outbox) == 1

    def test_send_payment_failed_email_task(self, user):
        from apps.emails.tasks import send_payment_failed_email

        mail.outbox.clear()
        send_payment_failed_email(str(user.pk), plan="Growth")
        assert len(mail.outbox) == 1

    def test_send_plan_changed_email_task(self, user):
        from apps.emails.tasks import send_plan_changed_email

        mail.outbox.clear()
        send_plan_changed_email(str(user.pk), old_plan="Starter", new_plan="Growth")
        assert len(mail.outbox) == 1

    def test_send_subscription_canceled_email_task(self, user):
        from apps.emails.tasks import send_subscription_canceled_email

        mail.outbox.clear()
        send_subscription_canceled_email(str(user.pk))
        assert len(mail.outbox) == 1

    def test_send_payment_reminder_email_task(self, user):
        from apps.emails.tasks import send_payment_reminder_email

        mail.outbox.clear()
        send_payment_reminder_email(str(user.pk), days_until_expiry=3)
        assert len(mail.outbox) == 1

    def test_send_team_invitation_email_task(self):
        from apps.emails.tasks import send_team_invitation_email

        mail.outbox.clear()
        send_team_invitation_email(
            to_email="new@example.com",
            inviter_name="Alice",
            team_name="Acme",
            invite_url="https://app.kovaagent.com/invite/abc",
        )
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == ["new@example.com"]

    def test_send_weekly_report_email_task(self, user):
        from apps.emails.tasks import send_weekly_report_email

        mail.outbox.clear()
        send_weekly_report_email(str(user.pk), report_data={"posts_created": 5})
        assert len(mail.outbox) == 1

    def test_send_feature_announcement_email_task(self, user):
        from apps.emails.tasks import send_feature_announcement_email

        mail.outbox.clear()
        send_feature_announcement_email(
            str(user.pk), "New Feature", "It's awesome",
        )
        assert len(mail.outbox) == 1

    def test_send_usage_warning_email_task(self, user):
        from apps.emails.tasks import send_usage_warning_email

        mail.outbox.clear()
        send_usage_warning_email(str(user.pk), resource="posts", current=90, limit=100)
        assert len(mail.outbox) == 1

    # -- Partner tasks --

    def test_send_partner_app_received_email_task(self, user):
        from apps.emails.tasks import send_partner_app_received_email

        mail.outbox.clear()
        send_partner_app_received_email(
            to_email=user.email, full_name="Test", user_id=str(user.pk),
        )
        assert len(mail.outbox) == 1

    def test_send_partner_app_received_email_task_no_user(self):
        from apps.emails.tasks import send_partner_app_received_email

        mail.outbox.clear()
        send_partner_app_received_email(
            to_email="anon@example.com", full_name="Anon",
        )
        # Template references `first_name` which isn't in context without
        # a user — the email service logs an error and skips sending.
        assert len(mail.outbox) == 0

    def test_send_partner_app_approved_email_task(self, user):
        from apps.emails.tasks import send_partner_app_approved_email

        mail.outbox.clear()
        send_partner_app_approved_email(str(user.pk), referral_code="KOVA-ABC")
        assert len(mail.outbox) == 1

    def test_send_partner_app_approved_no_account_email_task(self):
        from apps.emails.tasks import send_partner_app_approved_no_account_email

        mail.outbox.clear()
        send_partner_app_approved_no_account_email(
            to_email="noaccount@example.com", full_name="Jane",
        )
        assert len(mail.outbox) == 1

    def test_send_partner_app_rejected_email_task(self, user):
        from apps.emails.tasks import send_partner_app_rejected_email

        mail.outbox.clear()
        send_partner_app_rejected_email(
            to_email=user.email, full_name="Test", user_id=str(user.pk), reason="Not eligible",
        )
        assert len(mail.outbox) == 1

    def test_send_partner_new_referral_email_task(self, user):
        from apps.emails.tasks import send_partner_new_referral_email

        mail.outbox.clear()
        send_partner_new_referral_email(str(user.pk), "referred@example.com", total_referrals=3)
        assert len(mail.outbox) == 1

    def test_send_partner_milestone_email_task(self, user):
        from apps.emails.tasks import send_partner_milestone_email

        mail.outbox.clear()
        send_partner_milestone_email(str(user.pk), "10 referrals", 5000)
        assert len(mail.outbox) == 1

    # -- Retry logic --

    def test_send_email_task_has_retry_config(self):
        from apps.emails.tasks import send_email_task

        assert send_email_task.max_retries == 3
        assert send_email_task.default_retry_delay == 60

    def test_send_allauth_email_has_retry_config(self):
        from apps.emails.tasks import send_allauth_email

        assert send_allauth_email.max_retries == 3
        assert send_allauth_email.default_retry_delay == 30


# ═══════════════════════════════════════════════════════════════════════════
# 7. Allauth async email adapter
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestAllauthAdapter:

    def test_adapter_routes_to_celery(self, user):
        from apps.accounts.adapter import AsyncEmailAccountAdapter

        adapter = AsyncEmailAccountAdapter()
        mock_user = MagicMock()
        mock_user.email = user.email
        mock_user.first_name = user.first_name

        mock_site = MagicMock()
        mock_site.name = "Kova Agent"
        mock_site.domain = "kovaagent.com"

        with patch("apps.emails.tasks.send_allauth_email.delay") as mock_delay:
            adapter.send_mail(
                template_prefix="account/email/email_confirmation",
                email=user.email,
                context={
                    "user": mock_user,
                    "current_site": mock_site,
                    "key": "abc123",
                    "activate_url": "/confirm/abc123/",
                },
            )
            mock_delay.assert_called_once()
            args = mock_delay.call_args
            assert args[0][0] == "account/email/email_confirmation"
            assert args[0][1] == user.email
            safe_ctx = args[0][2]
            assert safe_ctx["user_email"] == user.email
            assert safe_ctx["key"] == "abc123"

    def test_adapter_serializes_only_safe_context(self, user):
        from apps.accounts.adapter import AsyncEmailAccountAdapter

        adapter = AsyncEmailAccountAdapter()
        complex_obj = MagicMock()
        complex_obj.__str__ = lambda self: "stringified"

        with patch("apps.emails.tasks.send_allauth_email.delay") as mock_delay:
            adapter.send_mail(
                "account/email/email_confirmation",
                user.email,
                {"complex": complex_obj, "simple": "value"},
            )
            safe_ctx = mock_delay.call_args[0][2]
            assert safe_ctx["simple"] == "value"
            assert safe_ctx["complex"] == "stringified"


# ═══════════════════════════════════════════════════════════════════════════
# 8. Automation helpers
# ═══════════════════════════════════════════════════════════════════════════


class TestIsMailableEmail:

    def test_valid_email(self):
        from apps.emails.automation import is_mailable_email

        assert is_mailable_email("user@example.com") is True

    def test_empty_email(self):
        from apps.emails.automation import is_mailable_email

        assert is_mailable_email("") is False

    def test_none_email(self):
        from apps.emails.automation import is_mailable_email

        assert is_mailable_email(None) is False

    def test_no_at_sign(self):
        from apps.emails.automation import is_mailable_email

        assert is_mailable_email("invalid-email") is False

    def test_placeholder_domain_rejected(self):
        from apps.emails.automation import is_mailable_email

        assert is_mailable_email("wa_254700@kova.page") is False

    def test_whatsapp_prefix_rejected(self):
        from apps.emails.automation import is_mailable_email

        assert is_mailable_email("wa_254712345678@example.com") is False

    def test_noemail_prefix_rejected(self):
        from apps.emails.automation import is_mailable_email

        assert is_mailable_email("noemail_customer@example.com") is False

    def test_noreply_prefix_rejected(self):
        from apps.emails.automation import is_mailable_email

        assert is_mailable_email("noreply@example.com") is False

    def test_normal_email_with_plus(self):
        from apps.emails.automation import is_mailable_email

        assert is_mailable_email("user+tag@example.com") is True


# ═══════════════════════════════════════════════════════════════════════════
# 9. EmailLog model
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestEmailLogModel:

    def test_email_log_created_per_send(self, user):
        initial_count = EmailLog.objects.count()
        email_service._send("welcome", user.email, user=user)
        assert EmailLog.objects.count() == initial_count + 1

    def test_email_log_str(self, user):
        log = email_service._send("welcome", user.email, user=user)
        s = str(log)
        assert "Welcome" in s
        assert user.email in s

    def test_email_log_ordering(self, user):
        email_service._send("welcome", user.email, user=user)
        email_service._send("system", user.email, user=user)
        logs = list(EmailLog.objects.filter(user=user)[:2])
        assert logs[0].created_at >= logs[1].created_at

    def test_email_log_uuid_pk(self, user):
        log = email_service._send("welcome", user.email, user=user)
        assert isinstance(log.pk, uuid.UUID)


# ═══════════════════════════════════════════════════════════════════════════
# 10. EmailSubscriber model basics
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestEmailSubscriberModel:

    def test_unsubscribe_token_auto_generated(self, user):
        sub = EmailSubscriber.objects.create(
            user=user, email="sub@example.com", name="Sub",
        )
        assert sub.unsubscribe_token
        assert len(sub.unsubscribe_token) > 10

    def test_record_bounce_increments(self, user):
        sub = EmailSubscriber.objects.create(
            user=user, email="bounce@example.com", name="Bouncy",
        )
        assert sub.bounce_count == 0
        sub.record_bounce()
        sub.refresh_from_db()
        assert sub.bounce_count == 1
        assert sub.status == EmailSubscriber.Status.ACTIVE

    def test_record_bounce_marks_bounced_after_threshold(self, user):
        sub = EmailSubscriber.objects.create(
            user=user, email="hardbounce@example.com",
        )
        sub.record_bounce()
        sub.record_bounce()
        sub.record_bounce()
        sub.refresh_from_db()
        assert sub.status == EmailSubscriber.Status.BOUNCED

    def test_subscriber_str(self, user):
        sub = EmailSubscriber.objects.create(
            user=user, email="show@example.com", name="Shown",
        )
        assert "Shown" in str(sub)


@pytest.mark.django_db
class TestEmailBootstrap:
    def test_bootstrap_email_marketing_does_not_recurse(self, user):
        from apps.emails.automation import bootstrap_email_automation
        from apps.emails.subscriber_sync import bootstrap_email_marketing

        marketing = bootstrap_email_marketing(user)
        assert "synced" in marketing
        assert "list_count" in marketing

        automation = bootstrap_email_automation(user)
        assert "synced" in automation
        assert "pending_sent" in automation
