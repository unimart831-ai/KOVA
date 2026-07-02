"""Phase 4 — the RevenueFunnel object + post-purchase loop.

Verifies the unifying funnel: a product's journey is one object that accumulates
attributed conversions + revenue, and a completed payment closes the loop
(funnel conversion + cross-sell) via the post-purchase signal. Idempotent.
"""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from apps.products.models import CommercePayment, Product, RevenueFunnel
from apps.products.post_purchase import build_cross_sell, run_post_purchase
from apps.products.revenue_funnel import ensure_funnel_for_product, mark_stage, record_conversion

User = get_user_model()


@pytest.fixture
def owner(db):
    u = User.objects.create_user(username="rev", email="rev@example.com", password="Passw0rd!")
    u.profile.page_slug = "rev"
    u.profile.save()
    return u


def _product(user, name, **kw):
    return Product.objects.create(user=user, name=name, is_active=True, **kw)


def _payment(user, product, amount, *, status=CommercePayment.Status.PENDING):
    return CommercePayment.objects.create(
        user=user,
        product=product,
        transaction_ref=f"tr-{product.pk}-{amount}",
        checkout_request_id=f"chk-{product.pk}-{amount}",
        phone_number="254700111222",
        amount=Decimal(str(amount)),
        status=status,
    )


@pytest.mark.django_db
class TestRevenueFunnelService:
    def test_ensure_creates_funnel_with_landing_stage(self, owner):
        p = _product(owner, "Dell Laptop", price=60000)
        f = ensure_funnel_for_product(p)
        assert f.product_id == p.pk
        assert f.landing_url
        assert f.stages.get("landing", {}).get("done") is True

    def test_ensure_is_idempotent(self, owner):
        p = _product(owner, "Dell Laptop")
        f1 = ensure_funnel_for_product(p)
        f2 = ensure_funnel_for_product(p)
        assert f1.pk == f2.pk
        assert RevenueFunnel.objects.filter(product=p).count() == 1

    def test_record_conversion_accumulates_revenue(self, owner):
        p = _product(owner, "Dell Laptop", price=60000)
        f = ensure_funnel_for_product(p)
        record_conversion(f, _payment(owner, p, 60000))
        f.refresh_from_db()
        assert f.conversions == 1
        assert f.attributed_revenue == Decimal("60000")
        assert f.status == RevenueFunnel.Status.CONVERTED
        assert f.stages.get("checkout", {}).get("done") is True

    def test_mark_stage_is_idempotent(self, owner):
        p = _product(owner, "Dell Laptop")
        f = ensure_funnel_for_product(p)
        mark_stage(f, "upsell")
        first_ts = f.stages["upsell"]["at"]
        mark_stage(f, "upsell")
        f.refresh_from_db()
        assert f.stages["upsell"]["at"] == first_ts


@pytest.mark.django_db
class TestPostPurchaseLoop:
    def test_completed_payment_builds_funnel_via_signal(self, owner):
        p = _product(owner, "Dell Laptop", price=60000)
        _payment(owner, p, 60000, status=CommercePayment.Status.COMPLETED)  # fires signal
        f = RevenueFunnel.objects.get(product=p)
        assert f.conversions == 1
        assert f.attributed_revenue == Decimal("60000")
        assert f.status == RevenueFunnel.Status.CONVERTED

    def test_cross_sell_recommends_other_products(self, owner):
        p1 = _product(owner, "Dell Laptop", price=60000)
        _product(owner, "Laptop Bag", price=3000)
        cross = build_cross_sell(p1)
        assert any(x.name == "Laptop Bag" for x in cross)

    def test_post_purchase_marks_upsell_when_cross_sell_exists(self, owner):
        p1 = _product(owner, "Dell Laptop", price=60000)
        _product(owner, "Laptop Bag", price=3000)
        pay = _payment(owner, p1, 60000, status=CommercePayment.Status.PENDING)
        pay.status = CommercePayment.Status.COMPLETED  # in-memory only — no save, no signal
        summary = run_post_purchase(pay)
        assert summary["funnel"] is True
        assert "Laptop Bag" in summary["cross_sell"]
        f = RevenueFunnel.objects.get(product=p1)
        assert f.stages.get("upsell", {}).get("done") is True

    def test_resaving_completed_payment_does_not_double_count(self, owner):
        p = _product(owner, "Dell Laptop", price=60000)
        pay = _payment(owner, p, 60000, status=CommercePayment.Status.COMPLETED)
        pay.result_desc = "touch"
        pay.save()  # _was_completed True → signal returns early
        f = RevenueFunnel.objects.get(product=p)
        assert f.conversions == 1
