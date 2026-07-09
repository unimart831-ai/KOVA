"""Tests for WhatsApp reply-to-act on daily brief."""
from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest

from apps.accounts.models import User, UserProfile
from apps.briefs.models import DailyBrief, BriefWhatsAppLog
from apps.briefs.whatsapp_commands import (
    _dispatch_command,
    find_user_by_whatsapp_id,
)
from apps.content.models import Post
from apps.platforms.models import SocialAccount


@pytest.fixture
def pro_user(db):
    u = User.objects.create_user(
        username="pro", email="pro@kova.ai", password="x",
        full_name="Pro User", phone_number="0712345678",
        brief_whatsapp_enabled=True,
    )
    UserProfile.objects.filter(user=u).update(plan="pro")
    return u


@pytest.fixture
def today_brief(pro_user):
    return DailyBrief.objects.create(
        user=pro_user,
        date=date.today(),
        summary="Para 1.\n\nPara 2.\n\nYour move today: Check inbox.",
        posts_pending=2,
        kova_score=80,
        kova_score_delta=3,
        suggested_posts=[
            {"idea": "First idea", "platform": "instagram"},
            {"idea": "Second idea", "platform": "facebook"},
        ],
    )


class TestFindUserByWhatsappId:
    def test_matches_kenyan_local_phone(self, pro_user):
        assert find_user_by_whatsapp_id("254712345678") == pro_user

    def test_unknown_number(self, db):
        assert find_user_by_whatsapp_id("254799999999") is None


class TestDispatchCommand:
    def test_help(self, pro_user):
        text, cmd, ok, _ = _dispatch_command(pro_user, "help")
        assert cmd == "help"
        assert ok is True
        assert "APPROVE" in text

    def test_score_with_brief(self, pro_user, today_brief):
        text, cmd, ok, meta = _dispatch_command(pro_user, "score")
        assert cmd == "score"
        assert "80" in text
        assert meta["kova_score"] == 80

    def test_standup_command(self, pro_user, today_brief):
        text, cmd, ok, _ = _dispatch_command(pro_user, "standup")
        assert cmd == "standup"
        assert ok is True
        assert "Morning Standup" in text
        assert "APPROVE ALL" in text

    @patch("apps.briefs.whatsapp_commands._send_owner_reply", return_value=True)
    def test_approve_no_pending(self, _reply, pro_user, today_brief):
        text, cmd, ok, _ = _dispatch_command(pro_user, "approve")
        assert "Nothing to approve" in text

    def test_money_command(self, pro_user, today_brief):
        text, cmd, ok, meta = _dispatch_command(pro_user, "money")
        assert cmd == "money"
        assert ok is True
        assert "Money this week" in text
        assert "revenue_week" in meta
        assert "total_kes" in meta or "mpesa_kes" in meta

    def test_leads_command(self, pro_user, today_brief):
        text, cmd, ok, meta = _dispatch_command(pro_user, "leads")
        assert cmd == "leads"
        assert ok is True
        assert "Leads:" in text
        assert "leads_week" in meta

    def test_reject_no_pending(self, pro_user, today_brief):
        text, cmd, ok, _ = _dispatch_command(pro_user, "reject")
        assert cmd == "reject"
        assert "Nothing to reject" in text

    def test_reject_first_post(self, pro_user, today_brief):
        sa = SocialAccount.objects.create(
            user=pro_user, platform="instagram", username="test",
            platform_user_id="ig2", is_active=True,
        )
        post = Post.objects.create(
            user=pro_user,
            social_account=sa,
            content_text="Reject me",
            status=Post.Status.PENDING_APPROVAL,
        )
        text, cmd, ok, result = _dispatch_command(pro_user, "reject")
        assert ok is True
        assert result["rejected"] == 1
        post.refresh_from_db()
        assert post.status == Post.Status.REJECTED

    def test_book_command_no_link(self, pro_user, today_brief):
        text, cmd, ok, meta = _dispatch_command(pro_user, "book")
        assert cmd == "book"
        assert ok is True
        assert meta["has_booking_link"] is False
        assert "booking page" in text.lower()

    def test_book_command_with_link(self, pro_user, today_brief):
        from apps.bookings.models import BookingLink

        BookingLink.objects.create(
            user=pro_user,
            slug="pro-salon",
            label="Pro Salon",
            services=[{"name": "Cut", "duration_minutes": 30, "price_kes": 1000}],
            working_hours={"mon": [{"start": "09:00", "end": "17:00"}]},
        )
        text, cmd, ok, meta = _dispatch_command(pro_user, "book")
        assert cmd == "book"
        assert ok is True
        assert meta["has_booking_link"] is True
        assert "Pro Salon" in text
        assert "Cut" in text

    def test_idea_out_of_range(self, pro_user, today_brief):
        text, cmd, ok, _ = _dispatch_command(pro_user, "idea 9")
        assert ok is False
        assert "Only 2 idea" in text

    @patch("apps.briefs.actions.create_seed_from_brief_idea")
    def test_idea_queues_seed(self, mock_seed, pro_user, today_brief):
        from apps.content.models import ContentSeed

        mock_seed.return_value = ContentSeed(user=pro_user, idea="Second idea")
        text, cmd, ok, meta = _dispatch_command(pro_user, "idea 2")
        assert cmd == "idea_2"
        assert ok is True
        mock_seed.assert_called_once()

    def test_approve_first_post(self, pro_user, today_brief):
        sa = SocialAccount.objects.create(
            user=pro_user, platform="instagram", username="test",
            platform_user_id="ig1", is_active=True,
        )
        post = Post.objects.create(
            user=pro_user,
            social_account=sa,
            content_text="Test post content",
            status=Post.Status.PENDING_APPROVAL,
        )
        text, cmd, ok, result = _dispatch_command(pro_user, "approve")
        assert ok is True
        assert result["approved"] == 1
        post.refresh_from_db()
        assert post.status == Post.Status.APPROVED


class TestPriceStockCommands:
    def test_price_list_empty(self, pro_user):
        text, cmd, ok, _ = _dispatch_command(pro_user, "price")
        assert cmd == "price"
        assert ok is True
        assert "No products yet" in text

    def test_price_list_with_products(self, pro_user):
        from apps.products.models import Product

        Product.objects.create(user=pro_user, name="Leather Shoes", price=2500)
        text, cmd, ok, meta = _dispatch_command(pro_user, "price")
        assert ok is True
        assert "Leather Shoes" in text
        assert meta["count"] == 1

    def test_price_update(self, pro_user):
        from apps.products.models import Product

        p = Product.objects.create(user=pro_user, name="Leather Shoes", price=2500)
        text, cmd, ok, meta = _dispatch_command(pro_user, "price shoes 3000")
        assert ok is True
        assert "3,000" in text
        p.refresh_from_db()
        assert p.price == 3000

    def test_price_update_no_match(self, pro_user):
        text, cmd, ok, _ = _dispatch_command(pro_user, "price widget 500")
        assert ok is False
        assert "No product matching" in text

    def test_price_update_ambiguous(self, pro_user):
        from apps.products.models import Product

        Product.objects.create(user=pro_user, name="Red Shoes", price=1000)
        Product.objects.create(user=pro_user, name="Blue Shoes", price=1200)
        text, cmd, ok, _ = _dispatch_command(pro_user, "price shoes 3000")
        assert ok is False
        assert "Red Shoes" in text and "Blue Shoes" in text

    def test_stock_overview(self, pro_user):
        from apps.products.models import Product

        Product.objects.create(user=pro_user, name="In Stock Item", price=100)
        Product.objects.create(
            user=pro_user, name="Gone Item", price=100,
            stock_status=Product.StockStatus.OUT_OF_STOCK,
        )
        text, cmd, ok, meta = _dispatch_command(pro_user, "stock")
        assert cmd == "stock"
        assert ok is True
        assert "Gone Item" in text
        assert meta["out"] == 1

    def test_stock_set_quantity(self, pro_user):
        from apps.products.models import Product, StockUpdate

        p = Product.objects.create(user=pro_user, name="Leather Shoes", price=2500)
        text, cmd, ok, meta = _dispatch_command(pro_user, "stock shoes 10")
        assert ok is True
        p.refresh_from_db()
        assert p.quantity == 10
        assert p.stock_status == Product.StockStatus.IN_STOCK
        assert StockUpdate.objects.filter(product=p).exists()

    def test_stock_quantity_triggers_low_stock(self, pro_user):
        from apps.products.models import Product

        p = Product.objects.create(
            user=pro_user, name="Leather Shoes", price=2500, low_stock_threshold=5,
        )
        _dispatch_command(pro_user, "stock shoes 3")
        p.refresh_from_db()
        assert p.stock_status == Product.StockStatus.LOW_STOCK

    def test_stock_mark_out(self, pro_user):
        from apps.products.models import Product

        p = Product.objects.create(user=pro_user, name="Leather Shoes", price=2500)
        text, cmd, ok, _ = _dispatch_command(pro_user, "stock shoes out")
        assert ok is True
        p.refresh_from_db()
        assert p.stock_status == Product.StockStatus.OUT_OF_STOCK
        assert p.quantity == 0

    def test_stock_mark_back_in(self, pro_user):
        from apps.products.models import Product

        p = Product.objects.create(
            user=pro_user, name="Leather Shoes", price=2500,
            stock_status=Product.StockStatus.OUT_OF_STOCK, quantity=0,
        )
        text, cmd, ok, _ = _dispatch_command(pro_user, "stock shoes in")
        assert ok is True
        p.refresh_from_db()
        assert p.stock_status == Product.StockStatus.IN_STOCK

    def test_help_mentions_price_and_stock(self, pro_user):
        text, _, _, _ = _dispatch_command(pro_user, "help")
        assert "PRICE" in text
        assert "STOCK" in text


class TestBriefWhatsAppLog:
    @patch("apps.briefs.whatsapp_commands._send_owner_action_buttons", return_value=True)
    @patch("apps.briefs.whatsapp_commands._send_owner_reply", return_value=True)
    def test_handle_owner_command_logs(self, _reply, _buttons, pro_user, today_brief):
        from apps.briefs.whatsapp_commands import handle_owner_brief_command

        msg = {
            "from": "254712345678",
            "type": "text",
            "text": {"body": "help"},
        }
        assert handle_owner_brief_command(msg) is True
        assert BriefWhatsAppLog.objects.filter(user=pro_user, command="help").exists()

    @patch("apps.briefs.whatsapp_commands._send_owner_action_buttons", return_value=True)
    @patch("apps.briefs.whatsapp_commands._send_owner_reply", return_value=True)
    def test_button_reply_id_maps_to_approve(self, mock_reply, _buttons, pro_user, today_brief):
        from apps.briefs.whatsapp_commands import handle_owner_brief_command

        msg = {
            "from": "254712345678",
            "type": "interactive",
            "interactive": {
                "type": "button_reply",
                "button_reply": {"id": "brief_approve", "title": "Approve"},
            },
        }
        assert handle_owner_brief_command(msg) is True
        assert BriefWhatsAppLog.objects.filter(user=pro_user, command="approve").exists()
