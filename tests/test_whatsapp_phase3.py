"""Phase 3 — invisible WhatsApp: grounded customer assistant, Business Memory,
and owner opportunity cards.

All assertions use deterministic paths (no LLM/network).
"""

import pytest
from django.contrib.auth import get_user_model

from apps.create.briefs.opportunities import build_opportunity_cards, format_opportunity_cards_message
from apps.commerce.links.hub.salesperson import business_knowledge_block
from apps.commerce.products.models import Product
from apps.messaging.whatsapp.memory import (
    memory_context_block,
    recall_customer_memory,
    remember_customer_interaction,
)

User = get_user_model()


@pytest.fixture
def owner(db):
    return User.objects.create_user(username="shop", email="shop@example.com", password="Passw0rd!")


def _product(user, name, **kw):
    return Product.objects.create(user=user, name=name, is_active=True, **kw)


@pytest.mark.django_db
class TestGroundedKnowledge:
    def test_knowledge_block_includes_catalog_and_faq(self, owner):
        _product(owner, "Dell Laptop", price=60000, description="For programming")
        owner.profile.common_questions = ["Do you deliver?"]
        owner.profile.save(update_fields=["common_questions"])
        block = business_knowledge_block(owner.profile, owner)
        assert "Dell Laptop" in block
        assert "Do you deliver?" in block

    def test_empty_when_no_inventory(self, owner):
        assert business_knowledge_block(owner.profile, owner) == ""


@pytest.mark.django_db
class TestBusinessMemory:
    def test_first_interaction_detects_interest_no_recall(self, owner):
        _product(owner, "Dell Laptop")
        mem = remember_customer_interaction(
            owner, "254700111222", name="Jane", message_text="Do you have a Dell Laptop?"
        )
        assert mem.interaction_count == 1
        assert "Dell Laptop" in mem.interests
        # First-timers get no "returning" block.
        assert memory_context_block(mem) == ""

    def test_returning_customer_recall_has_context(self, owner):
        _product(owner, "Dell Laptop")
        remember_customer_interaction(owner, "254700111222", name="Jane", message_text="Dell Laptop?")
        mem = remember_customer_interaction(owner, "254700111222", message_text="still thinking")
        assert mem.interaction_count == 2
        block = memory_context_block(mem)
        assert "Dell Laptop" in block
        assert "Jane" in block

    def test_recall_none_for_unknown_contact(self, owner):
        assert recall_customer_memory(owner, "254999888777") is None


@pytest.mark.django_db
class TestGroundedWhatsAppPrompt:
    def test_system_prompt_grounds_catalog_and_memory(self, owner):
        from apps.core.platforms.models import SocialAccount
        from apps.messaging.whatsapp.models import WhatsAppConversation
        from apps.messaging.whatsapp.tasks import _build_system_prompt

        _product(owner, "Dell Laptop", price=60000)
        acct = SocialAccount.objects.create(
            user=owner,
            platform="whatsapp",
            platform_user_id="wa1",
            username="wa",
            access_token="t",
            is_active=True,
        )
        conv = WhatsAppConversation.objects.create(
            social_account=acct,
            contact_wa_id="254700111222",
            contact_phone="254700111222",
            contact_name="Jane",
        )
        remember_customer_interaction(owner, "254700111222", name="Jane", message_text="Dell Laptop?")
        remember_customer_interaction(owner, "254700111222", message_text="Dell Laptop still?")

        prompt = _build_system_prompt(owner.profile, conv)
        assert "Dell Laptop" in prompt
        assert "RETURNING CUSTOMER MEMORY" in prompt


@pytest.mark.django_db
class TestOpportunityCards:
    def test_returning_interest_is_high_priority(self, owner):
        _product(owner, "Dell Laptop")
        for phone in ("254700000001", "254700000002"):
            remember_customer_interaction(owner, phone, message_text="Dell Laptop?")
            remember_customer_interaction(owner, phone, message_text="Dell Laptop still?")
        cards = build_opportunity_cards(owner)
        assert cards
        assert cards[0]["priority"] == "high"
        assert "Dell Laptop" in cards[0]["title"]
        assert cards[0]["command"].startswith("IDEA")

    def test_low_stock_card(self, owner):
        _product(owner, "Sneakers", stock_status=Product.StockStatus.LOW_STOCK)
        cards = build_opportunity_cards(owner)
        assert any("Sneakers" in c["title"] for c in cards)

    def test_format_message_when_empty(self, owner):
        assert "No new opportunities" in format_opportunity_cards_message(owner)

    def test_format_message_lists_cards(self, owner):
        _product(owner, "Sneakers", stock_status=Product.StockStatus.LOW_STOCK)
        msg = format_opportunity_cards_message(owner)
        assert "Opportunities Kova spotted" in msg
        assert "Sneakers" in msg
