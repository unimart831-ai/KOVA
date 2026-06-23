"""Sprint H — Today board NBA, professional snap modes, booking→lead bridge."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User, UserProfile
from apps.bookings.models import Booking, BookingLink
from apps.briefs.dashboard import _money_board_from_stats, get_money_board_stats
from apps.engage.models import Interaction
from apps.leads.bridges import _engage_lead_metadata, create_lead_from_booking
from apps.leads.models import Lead
from apps.products.models import BusinessAsset, Product


@pytest.mark.django_db
class TestMoneyBoardNextAction:
    def test_board_includes_next_action_card(self, user):
        stats = {
            "leads_week": 2,
            "needs_reply": 1,
            "needs_reply_wa": 1,
            "needs_reply_engage": 0,
            "hot_leads": 0,
            "ready_to_approve": 0,
            "next_action": {
                "key": "reply",
                "label": "Reply to 1 waiting message(s)",
                "whatsapp_command": "leads",
                "priority": "high",
            },
        }
        board = _money_board_from_stats(stats)
        assert board["next_action"]["key"] == "reply"
        assert board["next_action"]["url_name"] == "engage:unified_inbox"
        assert "Reply" in board["next_action"]["label"]

    def test_get_money_board_stats_attaches_nba(self, user):
        user.onboarding_completed = True
        user.save(update_fields=["onboarding_completed"])
        Interaction.objects.create(
            user=user,
            platform="instagram",
            interaction_type="comment",
            status="new",
            content="Can I book?",
            author_username="buyer1",
            author_name="Buyer",
            ai_intent="pricing",
        )
        stats = get_money_board_stats(user)
        assert stats.get("next_action")
        assert stats["next_action"]["key"] in ("reply", "approve", "hot_leads", "snap", "book", "money")


@pytest.mark.django_db
class TestSnapProfessionalModes:
    @patch("apps.utils.fire_task")
    @patch("apps.products.image_utils.normalize_uploaded_image")
    def test_snap_launch_portfolio_without_price(self, mock_norm, mock_fire, auth_client, user):
        UserProfile.objects.filter(user=user).update(business_model="professional")
        mock_norm.side_effect = lambda f: f
        img = SimpleUploadedFile("snap.jpg", b"fake-image-bytes", content_type="image/jpeg")
        url = reverse("products:snap_launch")
        with patch("apps.content.safety.check_uploaded_images_safe") as mock_safe:
            mock_safe.return_value = MagicMock(safe=True)
            resp = auth_client.post(
                url,
                {
                    "name": "Website redesign",
                    "snap_mode": "portfolio",
                    "offering_type": "product",
                    "client": "Acme Co",
                    "outcome": "40% more leads",
                    "currency": "KES",
                    "visual_mode": "as_is",
                    "polish_mode": "lite",
                    "scene_pack": "auto",
                    "photos": img,
                },
            )
        assert resp.status_code == 302
        product = Product.objects.filter(user=user).order_by("-created_at").first()
        assert product is not None
        assert product.price == 0
        asset = BusinessAsset.objects.get(product=product)
        assert asset.asset_type == BusinessAsset.AssetType.PORTFOLIO
        assert asset.metadata.get("client") == "Acme Co"
        assert asset.metadata.get("outcome") == "40% more leads"

    @patch("apps.utils.fire_task")
    @patch("apps.products.image_utils.normalize_uploaded_image")
    def test_snap_launch_case_study(self, mock_norm, mock_fire, auth_client, user):
        mock_norm.side_effect = lambda f: f
        img = SimpleUploadedFile("snap.jpg", b"fake-image-bytes", content_type="image/jpeg")
        url = reverse("products:snap_launch")
        with patch("apps.content.safety.check_uploaded_images_safe") as mock_safe:
            mock_safe.return_value = MagicMock(safe=True)
            resp = auth_client.post(
                url,
                {
                    "name": "Tax audit win",
                    "price": "5000",
                    "snap_mode": "case_study",
                    "client": "Jane Ltd",
                    "pain": "Missed deadlines",
                    "outcome": "Full compliance in 2 weeks",
                    "currency": "KES",
                    "visual_mode": "as_is",
                    "polish_mode": "lite",
                    "scene_pack": "auto",
                    "photos": img,
                },
            )
        assert resp.status_code == 302
        asset = BusinessAsset.objects.get(product__user=user, product__name="Tax audit win")
        assert asset.asset_type == BusinessAsset.AssetType.CASE_STUDY
        assert asset.metadata.get("pain") == "Missed deadlines"


@pytest.mark.django_db
class TestBookingLeadBridge:
    def test_create_lead_from_booking(self, user):
        link = BookingLink.objects.create(
            user=user,
            slug="test-svc",
            label="Consult",
            services=[{"name": "Consult", "duration": 30, "price": 2000}],
            working_hours={"mon": [{"start": "09:00", "end": "17:00"}]},
        )
        booking = Booking.objects.create(
            booking_link=link,
            customer_name="Mary",
            customer_phone="254712345678",
            customer_email="mary@example.com",
            service_name="Consult",
            duration_minutes=30,
            price_kes=2000,
            scheduled_at=timezone.now() + timedelta(days=1),
            status=Booking.Status.CONFIRMED,
            source_channel="whatsapp",
        )
        lead = create_lead_from_booking(booking)
        assert lead is not None
        assert lead.temperature == Lead.Temperature.HOT
        assert lead.source_type == Lead.Source.BOOKING
        assert lead.phone == "254712345678"

    def test_engage_booking_intent_metadata(self, user):
        BookingLink.objects.create(
            user=user,
            slug="svc-book",
            label="Book",
            services=[],
            working_hours={"mon": []},
        )
        interaction = Interaction.objects.create(
            user=user,
            platform="instagram",
            interaction_type="comment",
            status="new",
            content="I'd like to book a session",
            author_username="client1",
            author_name="Client",
            ai_intent="booking",
        )
        meta = _engage_lead_metadata(interaction)
        assert meta["engage_intent"] == "booking"
        assert "booking_url" in meta
        assert meta["suggested_owner_action"]
