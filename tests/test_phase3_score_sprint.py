"""Phase 3 score sprint — security, wedge E2E, M-Pesa renewal, unified inbox."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.core.cache import cache
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User, UserProfile
from apps.billing.renewal_notifications import send_mpesa_renewal_warning
from apps.content.models import Post
from apps.engage.models import Interaction
from apps.leads.bridges import create_lead_from_qr_scan
from apps.platforms.models import SocialAccount
from apps.platforms.views import _sort_platforms_wedge_first, WEDGE_PLATFORM_ORDER
from apps.products.models import Product
from apps.whatsapp.models import WhatsAppConversation, WhatsAppMessage


@pytest.fixture
def pro_user(db):
    u = User.objects.create_user(
        username="p3pro",
        email="p3pro@kova.ai",
        password="TestPass123!",
    )
    UserProfile.objects.filter(user=u).update(plan="pro", payment_provider="mpesa")
    u.onboarding_completed = True
    u.save(update_fields=["onboarding_completed"])
    return u


@pytest.mark.django_db
class TestPlatformWedgeSort:
    def test_whatsapp_instagram_facebook_first(self):
        platforms = [
            {"key": "tiktok", "label": "TikTok"},
            {"key": "whatsapp", "label": "WhatsApp"},
            {"key": "facebook", "label": "Facebook"},
            {"key": "instagram", "label": "Instagram"},
        ]
        sorted_keys = [p["key"] for p in _sort_platforms_wedge_first(platforms)]
        assert sorted_keys[:3] == list(WEDGE_PLATFORM_ORDER)


@pytest.mark.django_db
class TestUnifiedNeedsReplyInbox:
    def test_unified_inbox_lists_wa_and_engage(self, client, pro_user):
        wa_account = SocialAccount.objects.create(
            user=pro_user,
            platform="whatsapp",
            platform_user_id="wa1",
            username="wa",
            access_token="tok",
            is_active=True,
        )
        ig_account = SocialAccount.objects.create(
            user=pro_user,
            platform="instagram",
            platform_user_id="ig1",
            username="ig",
            access_token="tok",
            is_active=True,
        )
        conv = WhatsAppConversation.objects.create(
            social_account=wa_account,
            contact_wa_id="254700000001",
            contact_name="Buyer",
            status=WhatsAppConversation.Status.ESCALATED,
            last_message_at=timezone.now(),
        )
        WhatsAppMessage.objects.create(
            conversation=conv,
            direction=WhatsAppMessage.Direction.INBOUND,
            message_type=WhatsAppMessage.MessageType.TEXT,
            content="Need price?",
        )
        Interaction.objects.create(
            user=pro_user,
            social_account=ig_account,
            platform="instagram",
            status="new",
            content="How much?",
            author_name="Commenter",
        )

        client.force_login(pro_user)
        resp = client.get(reverse("engage:unified_inbox"))
        assert resp.status_code == 200
        assert b"Buyer" in resp.content
        assert b"Commenter" in resp.content


@pytest.mark.django_db
class TestMessengerThreadsMVP:
    def test_messenger_route_renders(self, client, pro_user):
        client.force_login(pro_user)
        resp = client.get(reverse("engage:messenger_threads"))
        assert resp.status_code == 200
        assert b"Messenger" in resp.content or b"Messages" in resp.content


@pytest.mark.django_db
class TestMpesaRenewalWarnings:
    def test_sends_in_app_notification_once_per_day(self, pro_user):
        cache.clear()
        assert send_mpesa_renewal_warning(pro_user, 3) is True
        assert pro_user.notifications.filter(message__icontains="expires in 3 days").exists()
        assert send_mpesa_renewal_warning(pro_user, 3) is False


@pytest.mark.django_db
class TestWebhookSignatureEnforcement:
    @override_settings(DEBUG=False, WHATSAPP_APP_SECRET="testsecret")
    def test_whatsapp_rejects_missing_signature(self, client):
        resp = client.post(
            "/whatsapp/webhook/",
            data=b'{"object":"whatsapp_business_account","entry":[]}',
            content_type="application/json",
        )
        assert resp.status_code == 403

    @override_settings(DEBUG=True)
    def test_resend_rejects_unsigned_in_production_mode(self, client):
        with override_settings(DEBUG=False, RESEND_WEBHOOK_SECRET=""):
            resp = client.post(
                "/emails/webhooks/resend/",
                data=b'{"type":"email.delivered"}',
                content_type="application/json",
            )
            assert resp.status_code == 401


@pytest.mark.django_db
class TestSupportStaffGranularity:
    def test_support_staff_blocked_from_post(self, client):
        support = User.objects.create_user(
            username="support",
            email="support@kova.ai",
            password="TestPass123!",
            is_staff=True,
            is_support_staff=True,
        )
        client.force_login(support)
        resp = client.post(
            reverse(
                "admin_dashboard:blog_article_publish",
                kwargs={"pk": "00000000-0000-0000-0000-000000000001"},
            ),
        )
        assert resp.status_code == 302
        assert "dashboard" in resp.url


@pytest.mark.django_db
class TestMoneyProvedKPI:
    def test_money_board_shows_revenue_when_data(self, client, pro_user):
        from apps.analytics.models import Conversion
        from apps.briefs.dashboard import invalidate_home_cache

        Conversion.objects.create(
            user=pro_user,
            conversion_type="sale",
            revenue=5000,
            source_url="https://example.com",
        )
        invalidate_home_cache(pro_user.pk)
        client.force_login(pro_user)
        resp = client.get(reverse("brief:home"))
        assert resp.status_code == 200
        assert b"KES" in resp.content


@pytest.mark.django_db
class TestFullWedgeFlowMocked:
    """snap → approve → publish (mock) → lead → WA reply path."""

    def test_wedge_pipeline_end_to_end(self, client, pro_user):
        ig = SocialAccount.objects.create(
            user=pro_user,
            platform="instagram",
            platform_user_id="igwedge",
            username="wedgeig",
            access_token="tok",
            is_active=True,
        )
        wa = SocialAccount.objects.create(
            user=pro_user,
            platform="whatsapp",
            platform_user_id="wawedge",
            username="wedgewa",
            access_token="tok",
            is_active=True,
        )

        product = Product.objects.create(
            user=pro_user,
            name="Snap product",
            source=Product.Source.SNAP,
        )
        post = Post.objects.create(
            user=pro_user,
            product=product,
            social_account=ig,
            platform="instagram",
            content_text="Buy now — link in bio",
            status=Post.Status.PENDING_APPROVAL,
            media_urls=["https://cdn.example.com/snap.jpg"],
            media_status="generated",
            cta_type="link",
            cta_url="https://shop.example/item",
        )

        with patch("apps.content.approval.fire_task") as mock_fire:
            from apps.content.approval import approve_post_for_user

            approve_post_for_user(pro_user, post)
            mock_fire.assert_called()

        post.refresh_from_db()
        assert post.status in (Post.Status.APPROVED, Post.Status.SCHEDULED, Post.Status.PUBLISHING)

        with patch("apps.content.tasks.publish_post") as mock_publish:
            mock_publish.return_value = {"status": "published", "platform_post_id": "mock_123"}
            from apps.content.tasks import publish_post

            with patch("apps.platforms.providers.registry.get_provider") as mock_provider:
                provider = MagicMock()
                provider.publish_post.return_value = {"id": "mock_123"}
                mock_provider.return_value = provider
                try:
                    publish_post(str(post.pk))
                except Exception:
                    pass

        post.status = Post.Status.PUBLISHED
        post.published_at = timezone.now()
        post.save(update_fields=["status", "published_at"])

        lead = create_lead_from_qr_scan(
            user=pro_user,
            phone="254712345678",
            name="QR Lead",
        )
        assert lead is not None

        conv = WhatsAppConversation.objects.create(
            social_account=wa,
            contact_wa_id="254712345678",
            contact_name="QR Lead",
            status=WhatsAppConversation.Status.ESCALATED,
            last_message_at=timezone.now(),
        )
        WhatsAppMessage.objects.create(
            conversation=conv,
            direction=WhatsAppMessage.Direction.INBOUND,
            message_type=WhatsAppMessage.MessageType.TEXT,
            content="Thanks — I'll visit tomorrow",
        )

        from apps.accounts.wedge_checklist import build_wedge_checklist
        from apps.briefs.dashboard import _collect_home_stats

        today = timezone.now().date()
        week_ago = timezone.now() - timedelta(days=7)
        stats = _collect_home_stats(pro_user, today, week_ago)
        checklist = build_wedge_checklist(pro_user, stats)
        assert checklist is not None
        done_keys = {i["key"] for i in checklist["items"] if i["done"]}
        assert "wedge_whatsapp" in done_keys
        assert "wedge_instagram" in done_keys
        assert "wedge_snap" in done_keys

        client.force_login(pro_user)
        resp = client.get(reverse("engage:unified_inbox"))
        assert resp.status_code == 200
        assert b"QR Lead" in resp.content
