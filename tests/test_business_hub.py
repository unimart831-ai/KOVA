"""Phase 2 — model-adaptive Business Hub + grounded AI Salesperson.

Verifies the Hub renders the right sections per business model, answers the five
questions, and that the AI Salesperson stays grounded in the business's own
inventory (with a safe WhatsApp handoff when it can't answer). All assertions
use the deterministic no-LLM path so CI needs no network.
"""

import pytest
from django.contrib.auth import get_user_model

from apps.commerce.links.hub.hub import build_hub_context, resolve_business_model
from apps.commerce.links.hub.salesperson import answer_customer_question
from apps.commerce.products.models import Product

User = get_user_model()


@pytest.fixture
def owner(db):
    u = User.objects.create_user(username="mary", email="mary@example.com", password="Passw0rd!")
    p = u.profile
    p.company_name = "Mary Tech"
    p.page_slug = "mary"
    p.page_active = True
    p.save()
    return u


def _product(user, name, **kw):
    return Product.objects.create(user=user, name=name, is_active=True, **kw)


@pytest.mark.django_db
class TestHubAdaptation:
    def test_resolve_infers_from_inventory(self, owner):
        assert resolve_business_model(owner.profile, has_products=True, has_booking=False) == "product"
        assert resolve_business_model(owner.profile, has_products=False, has_booking=True) == "service"

    def test_explicit_model_wins(self, owner):
        owner.profile.business_model = "professional"
        owner.profile.save(update_fields=["business_model"])
        assert resolve_business_model(owner.profile, has_products=True, has_booking=True) == "professional"

    def test_product_hub_orders_bestsellers_before_catalog(self, owner):
        _product(owner, "Dell Laptop", is_featured=True, price=50000)
        ctx = build_hub_context(owner.profile, owner)
        assert ctx["business_model"] == "product"
        sections = ctx["sections"]
        assert sections.index("bestsellers") < sections.index("catalog")

    def test_service_hub_leads_with_booking(self, owner):
        owner.profile.business_model = "service"
        owner.profile.save(update_fields=["business_model"])
        ctx = build_hub_context(owner.profile, owner)
        assert ctx["sections"][0] == "hero"
        assert "book" in ctx["sections"]
        assert ctx["sections"].index("book") < ctx["sections"].index("services")

    def test_salesperson_section_hidden_without_inventory_or_faq(self, owner):
        owner.profile.business_model = "professional"
        owner.profile.save(update_fields=["business_model"])
        ctx = build_hub_context(owner.profile, owner)
        assert "salesperson" not in ctx["sections"]

    def test_salesperson_section_shown_with_faq(self, owner):
        owner.profile.business_model = "professional"
        owner.profile.common_questions = ["Do you take remote clients?"]
        owner.profile.save(update_fields=["business_model", "common_questions"])
        ctx = build_hub_context(owner.profile, owner)
        assert "salesperson" in ctx["sections"]

    def test_five_question_contract_complete(self, owner):
        ctx = build_hub_context(owner.profile, owner)
        fq = ctx["five_questions"]
        for key in ("what", "why_trust", "whats_best", "how_to_buy", "what_after"):
            assert key in fq and fq[key]


@pytest.mark.django_db
class TestAISalesperson:
    def test_grounded_answer_recommends_matching_product(self, owner):
        _product(owner, "Dell Laptop", description="Great for programming and design", price=60000)
        _product(owner, "Office Chair", description="Comfortable seating", price=8000)

        result = answer_customer_question(owner.profile, owner, "Which laptop is best for programming?", use_llm=False)
        assert result["handoff"] is False
        assert any("Laptop" in p["name"] for p in result["products"])

    def test_unknown_question_hands_off_to_whatsapp(self, owner):
        _product(owner, "Dell Laptop", description="Great for programming", price=60000)
        result = answer_customer_question(owner.profile, owner, "Do you sell airplanes?", use_llm=False)
        assert result["handoff"] is True
        assert "whatsapp" in result["answer"].lower()

    def test_empty_question_is_safe(self, owner):
        result = answer_customer_question(owner.profile, owner, "   ", use_llm=False)
        assert result["handoff"] is False
        assert result["answer"]


@pytest.mark.django_db
class TestHubEndpoints:
    def test_page_renders_with_salesperson(self, client, owner):
        _product(owner, "Dell Laptop", is_featured=True, price=60000)
        resp = client.get("/p/mary/")
        assert resp.status_code == 200
        assert b"Dell Laptop" in resp.content
        assert b"Ask our assistant" in resp.content

    def test_ask_endpoint_returns_answer(self, client, owner, monkeypatch):
        _product(owner, "Dell Laptop", description="Great for programming", price=60000)
        # Force the deterministic path so the endpoint test needs no LLM.
        monkeypatch.setattr("apps.commerce.links.hub.salesperson._llm_answer", lambda *a, **k: "")
        resp = client.post("/p/mary/ask/", {"q": "laptop for programming"})
        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data
        assert data["answer"]

    def test_ask_endpoint_rejects_empty(self, client, owner):
        resp = client.post("/p/mary/ask/", {"q": ""})
        assert resp.status_code == 400
