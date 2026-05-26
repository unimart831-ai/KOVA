"""Tests for system streamline: phone middleware, M-Pesa commerce, post-onboarding redirects."""

import json

import pytest
from django.urls import reverse

from apps.accounts.models import User, UserProfile
from apps.products.models import CommercePayment, Product


@pytest.mark.django_db
class TestRequirePhoneMiddleware:
    def test_blocks_platform_connect_without_phone(self, client):
        u = User.objects.create_user(username="nophone", email="np@b.com", password="P1!")
        u.onboarding_completed = False
        u.save()
        client.force_login(u)
        resp = client.get("/platforms/connect/instagram/", follow=False)
        assert resp.status_code == 302
        assert "onboarding/phone" in resp.url

    def test_allows_collect_phone_page(self, client):
        u = User.objects.create_user(username="np2", email="np2@b.com", password="P1!")
        client.force_login(u)
        resp = client.get("/accounts/onboarding/phone/")
        assert resp.status_code == 200

    def test_allows_onboarding_with_phone(self, client):
        u = User.objects.create_user(
            username="hasph", email="hp@b.com", password="P1!", phone_number="0712345678",
        )
        u.onboarding_completed = False
        u.save()
        client.force_login(u)
        resp = client.get("/accounts/onboarding/start/", follow=False)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestPostOnboardingRedirects:
    def test_commerce_user_redirects_to_snap(self):
        from apps.accounts.onboarding_redirects import post_onboarding_redirect_url_name

        u = User.objects.create_user(username="sell", email="s@b.com", password="P1!")
        p = u.profile
        p.industry = "ecommerce"
        p.save()
        u.profile.record_onboarding_step("intent_sell")
        assert post_onboarding_redirect_url_name(u) == "products:snap"

    def test_grow_user_redirects_to_studio(self):
        from apps.accounts.onboarding_redirects import post_onboarding_redirect_url_name

        u = User.objects.create_user(username="grow", email="g@b.com", password="P1!")
        u.profile.record_onboarding_step("intent_grow")
        assert post_onboarding_redirect_url_name(u) == "content:studio"

    def test_whatsapp_url_for_commerce(self, settings):
        from apps.accounts.onboarding_redirects import post_onboarding_site_path

        settings.SITE_URL = "https://app.kovaagent.com"
        u = User.objects.create_user(username="wa", email="wa@b.com", password="P1!")
        u.profile.industry = "ecommerce"
        u.profile.save()
        assert post_onboarding_site_path(u) == "https://app.kovaagent.com/products/snap/"


@pytest.mark.django_db
class TestCommerceMpesaFlow:
    def _product(self, user, *, plan="growth"):
        UserProfile.objects.filter(user=user).update(plan=plan)
        user.profile.page_slug = "demo-shop"
        user.profile.save()
        return Product.objects.create(
            user=user,
            name="KES Item",
            price=500,
            currency="KES",
            commerce_slug="kes-item",
            stock_status=Product.StockStatus.IN_STOCK,
        )

    def test_stk_initiation_happy_path(self, client, user, monkeypatch):
        product = self._product(user)

        monkeypatch.setattr(
            "apps.billing.mpesa.initiate_stk_push",
            lambda **kwargs: {
                "CheckoutRequestID": "ws_CO_test123",
                "MerchantRequestID": "mr_test",
            },
        )

        url = reverse(
            "public_commerce_pay",
            kwargs={"page_slug": "demo-shop", "commerce_slug": product.commerce_slug},
        )
        resp = client.post(url, {"phone": "0712345678"})
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        assert CommercePayment.objects.filter(checkout_request_id="ws_CO_test123").exists()

    def test_starter_plan_blocked(self, client, user):
        product = self._product(user, plan="starter")
        url = reverse(
            "public_commerce_pay",
            kwargs={"page_slug": "demo-shop", "commerce_slug": product.commerce_slug},
        )
        resp = client.post(url, {"phone": "0712345678"})
        assert resp.status_code == 403

    def test_callback_completes_payment(self, client, user):
        product = self._product(user)
        payment = CommercePayment.objects.create(
            user=user,
            product=product,
            checkout_request_id="ws_CB_test",
            merchant_request_id="mr",
            phone_number="254712345678",
            amount=500,
            currency="KES",
            source=CommercePayment.Source.COMMERCE_LINK,
        )
        payload = {
            "Body": {
                "stkCallback": {
                    "ResultCode": 0,
                    "CheckoutRequestID": payment.checkout_request_id,
                    "CallbackMetadata": {
                        "Item": [
                            {"Name": "Amount", "Value": 500},
                            {"Name": "MpesaReceiptNumber", "Value": "TESTRECEIPT1"},
                            {"Name": "PhoneNumber", "Value": 254712345678},
                        ]
                    },
                }
            }
        }
        resp = client.post(
            reverse("mpesa_commerce_callback"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert resp.status_code == 200
        payment.refresh_from_db()
        assert payment.status == CommercePayment.Status.COMPLETED
        assert payment.receipt_number == "TESTRECEIPT1"


@pytest.mark.django_db
class TestSnapToShopGoldenPath:
    def test_product_resolves_on_public_shop(self, client, user):
        user.profile.page_slug = "golden-shop"
        user.profile.company_name = "Golden Shop"
        user.profile.save()
        product = Product.objects.create(
            user=user,
            name="Golden Sneaker",
            price=2500,
            currency="KES",
            commerce_slug="golden-sneaker",
            stock_status=Product.StockStatus.IN_STOCK,
            is_active=True,
        )
        shop_url = reverse("public_shop", kwargs={"page_slug": "golden-shop"})
        resp = client.get(shop_url)
        assert resp.status_code == 200
        assert b"Golden Sneaker" in resp.content

        product_url = reverse(
            "public_commerce",
            kwargs={"page_slug": "golden-shop", "commerce_slug": product.commerce_slug},
        )
        resp2 = client.get(product_url)
        assert resp2.status_code == 200
        assert b"Golden Sneaker" in resp2.content
