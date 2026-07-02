"""Operations Autopilot — toggles, auto-enroll, auto-publish, WA FAQ and follow-up."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import UserProfile
from apps.content.models import Post
from apps.content.tasks import check_and_publish_due_posts
from apps.leads.defaults import WELCOME_SEQUENCE_NAME, ensure_default_nurture_sequences
from apps.leads.models import Lead, LeadEnrollment, NurtureSequence
from apps.platforms.models import SocialAccount
from apps.whatsapp.autopilot import send_followup_nudges, try_faq_auto_reply
from apps.whatsapp.models import WhatsAppConversation, WhatsAppMessage


@pytest.mark.django_db
class TestAutopilotTogglesSave:
    def test_settings_form_saves_autopilot_toggles(self, user):
        from apps.accounts.forms import AutopilotSettingsForm

        user.profile.plan = "pro"
        user.profile.save(update_fields=["plan"])

        form = AutopilotSettingsForm(
            {
                "autopilot_auto_publish_approved": True,
                "autopilot_auto_enroll_leads": True,
                "autopilot_auto_create_wa_leads": True,
                "autopilot_wa_followup_24h": True,
                "autopilot_wa_faq_replies": True,
                "faq_keywords_0": "hours, open",
                "faq_reply_0": "We are open Mon–Sat 8am–6pm.",
            },
            instance=user.profile,
            user=user,
        )
        assert form.is_valid(), form.errors
        form.save()

        user.profile.refresh_from_db()
        assert user.profile.autopilot_auto_publish_approved is True
        assert user.profile.autopilot_auto_enroll_leads is True
        assert user.profile.wa_faq_answers[0]["keywords"] == ["hours", "open"]

    def test_settings_page_includes_autopilot_section(self, auth_client):
        resp = auth_client.get(reverse("accounts:settings"))
        assert resp.status_code == 200
        assert b"settings-autopilot" in resp.content
        assert b"Auto-publish approved posts" in resp.content


@pytest.mark.django_db
class TestAutoEnrollOnLeadCreate:
    def test_enrolls_when_toggle_on(self, user):
        ensure_default_nurture_sequences(user)
        UserProfile.objects.filter(user=user).update(autopilot_auto_enroll_leads=True)

        Lead.objects.create(
            user=user,
            email="newlead@example.com",
            name="New Lead",
            source_type=Lead.Source.FORM_SUBMISSION,
        )

        welcome = NurtureSequence.objects.get(user=user, name=WELCOME_SEQUENCE_NAME)
        assert LeadEnrollment.objects.filter(
            lead__email="newlead@example.com",
            sequence=welcome,
        ).exists()

    def test_skips_when_toggle_off(self, user):
        ensure_default_nurture_sequences(user)
        UserProfile.objects.filter(user=user).update(autopilot_auto_enroll_leads=False)

        Lead.objects.create(
            user=user,
            email="noenroll@example.com",
            source_type=Lead.Source.FORM_SUBMISSION,
        )

        assert LeadEnrollment.objects.filter(lead__email="noenroll@example.com").count() == 0


@pytest.mark.django_db
class TestAutoPublishRespectsPause:
    def test_does_not_dispatch_when_autopilot_off(self, user):
        from apps.platforms.models import SocialAccount

        account = SocialAccount.objects.create(
            user=user,
            platform="instagram",
            platform_user_id="ig1",
            username="shop",
            access_token="tok",
            is_active=True,
        )
        past = timezone.now() - timedelta(minutes=5)
        Post.objects.create(
            user=user,
            social_account=account,
            content_text="Due post",
            status=Post.Status.SCHEDULED,
            scheduled_at=past,
        )

        with patch("apps.content.tasks.publish_post.delay") as mock_delay:
            result = check_and_publish_due_posts()

        assert result["dispatched"] == 0
        mock_delay.assert_not_called()

    def test_dispatches_user_approved_without_autopilot(self, user):
        from apps.platforms.models import SocialAccount

        account = SocialAccount.objects.create(
            user=user,
            platform="instagram",
            platform_user_id="ig1b",
            username="shop",
            access_token="tok",
            is_active=True,
        )
        past = timezone.now() - timedelta(minutes=5)
        Post.objects.create(
            user=user,
            social_account=account,
            content_text="User approved post",
            status=Post.Status.APPROVED,
            scheduled_at=past,
        )

        with patch("apps.content.tasks.publish_post.delay") as mock_delay:
            result = check_and_publish_due_posts()

        assert result["dispatched"] == 1
        mock_delay.assert_called_once()

    def test_dispatches_when_enabled_not_paused(self, user):
        from apps.platforms.models import SocialAccount

        UserProfile.objects.filter(user=user).update(autopilot_auto_publish_approved=True)
        account = SocialAccount.objects.create(
            user=user,
            platform="instagram",
            platform_user_id="ig2",
            username="shop2",
            access_token="tok",
            is_active=True,
        )
        past = timezone.now() - timedelta(minutes=5)
        Post.objects.create(
            user=user,
            social_account=account,
            content_text="Due post enabled",
            status=Post.Status.APPROVED,
            scheduled_at=past,
        )

        with patch("apps.content.tasks.publish_post.delay") as mock_delay:
            result = check_and_publish_due_posts()

        assert result["dispatched"] == 1
        mock_delay.assert_called_once()

    def test_skips_when_user_auto_publish_paused(self, user):
        from apps.platforms.models import SocialAccount

        UserProfile.objects.filter(user=user).update(
            autopilot_auto_publish_approved=True,
            auto_publish_paused=True,
        )
        account = SocialAccount.objects.create(
            user=user,
            platform="instagram",
            platform_user_id="ig3",
            username="shop3",
            access_token="tok",
            is_active=True,
        )
        past = timezone.now() - timedelta(minutes=5)
        Post.objects.create(
            user=user,
            social_account=account,
            content_text="Paused post",
            status=Post.Status.APPROVED,
            scheduled_at=past,
        )

        with patch("apps.content.tasks.publish_post.delay") as mock_delay:
            result = check_and_publish_due_posts()

        assert result["dispatched"] == 0
        mock_delay.assert_not_called()


@pytest.mark.django_db
class TestFaqKeywordMatch:
    def test_match_faq_reply(self):
        from apps.accounts.autopilot_helpers import match_faq_reply

        faqs = [{"keywords": ["price", "cost"], "reply": "From KES 500"}]
        assert match_faq_reply("What is the price?", faqs) == "From KES 500"
        assert match_faq_reply("Hello", faqs) is None

    def test_try_faq_auto_reply_sends(self, user):
        user.profile.plan = "pro"
        user.profile.autopilot_wa_faq_replies = True
        user.profile.wa_faq_answers = [
            {"keywords": ["hours"], "reply": "Open 9–5 daily"},
        ]
        user.profile.save()

        account = SocialAccount.objects.create(
            user=user,
            platform="whatsapp",
            platform_user_id="wa1",
            username="wa",
            access_token="tok",
            is_active=True,
        )
        conversation = WhatsAppConversation.objects.create(
            social_account=account,
            contact_wa_id="254711223344",
            window_expires_at=timezone.now() + timedelta(hours=12),
        )
        inbound = WhatsAppMessage.objects.create(
            conversation=conversation,
            direction=WhatsAppMessage.Direction.INBOUND,
            message_type=WhatsAppMessage.MessageType.TEXT,
            content="What are your hours?",
        )

        with patch("apps.whatsapp.services.send_text_message") as mock_send:
            mock_send.return_value = {"success": True, "wamid": "wamid.test"}
            assert try_faq_auto_reply(conversation, inbound) is True

        mock_send.assert_called_once()
        assert "9–5" in mock_send.call_args.kwargs.get("body", mock_send.call_args[0][1])


@pytest.mark.django_db
class TestFollowUpSkipsWhenToggleOff:
    def test_no_nudges_when_toggle_off(self, user):
        user.profile.plan = "pro"
        user.profile.autopilot_wa_followup_24h = False
        user.profile.save()

        account = SocialAccount.objects.create(
            user=user,
            platform="whatsapp",
            platform_user_id="wa2",
            username="wa2",
            access_token="tok",
            is_active=True,
        )
        conversation = WhatsAppConversation.objects.create(
            social_account=account,
            contact_wa_id="254700111222",
            last_message_at=timezone.now() - timedelta(hours=30),
            window_expires_at=timezone.now() + timedelta(hours=2),
        )
        WhatsAppMessage.objects.create(
            conversation=conversation,
            direction=WhatsAppMessage.Direction.INBOUND,
            message_type=WhatsAppMessage.MessageType.TEXT,
            content="Still waiting",
            created_at=timezone.now() - timedelta(hours=30),
        )

        with patch("apps.whatsapp.services.send_text_message") as mock_send:
            result = send_followup_nudges()

        assert result["sent"] == 0
        mock_send.assert_not_called()

    def test_nudge_when_toggle_on(self, user):
        user.profile.plan = "pro"
        user.profile.autopilot_wa_followup_24h = True
        user.profile.save()

        account = SocialAccount.objects.create(
            user=user,
            platform="whatsapp",
            platform_user_id="wa3",
            username="wa3",
            access_token="tok",
            is_active=True,
        )
        conversation = WhatsAppConversation.objects.create(
            social_account=account,
            contact_wa_id="254700333444",
            last_message_at=timezone.now() - timedelta(hours=30),
            window_expires_at=timezone.now() + timedelta(hours=2),
        )
        WhatsAppMessage.objects.create(
            conversation=conversation,
            direction=WhatsAppMessage.Direction.INBOUND,
            message_type=WhatsAppMessage.MessageType.TEXT,
            content="Any update?",
            created_at=timezone.now() - timedelta(hours=30),
        )

        with patch("apps.whatsapp.services.send_text_message") as mock_send:
            mock_send.return_value = {"success": True}
            result = send_followup_nudges()

        assert result["sent"] == 1
        mock_send.assert_called_once()
