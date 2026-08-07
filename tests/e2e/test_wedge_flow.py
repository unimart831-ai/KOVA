"""
E2E: full wedge path visible on Today after mocked setup.
Complements pytest integration test in test_phase3_score_sprint.py.
"""

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from playwright.sync_api import expect

from apps.core.accounts.models import UserProfile
from apps.create.content.models import Post
from apps.commerce.leads.models import Lead
from apps.core.platforms.models import SocialAccount
from apps.commerce.products.models import Product

User = get_user_model()


@pytest.mark.django_db(transaction=True)
class TestWedgeFlowE2E:
    def test_today_shows_money_board_and_wedge_after_flow(self, page, base_url):
        user = User.objects.create_user(
            username="wedgedemo",
            email="wedgedemo@example.com",
            password="TestPass123!@#",
        )
        user.phone_number = "0712345678"
        user.onboarding_completed = True
        user.save()
        UserProfile.objects.filter(user=user).update(plan="growth")

        SocialAccount.objects.create(
            user=user,
            platform="whatsapp",
            platform_user_id="wa-e2e",
            username="wa",
            access_token="tok",
            is_active=True,
        )
        ig = SocialAccount.objects.create(
            user=user,
            platform="instagram",
            platform_user_id="ig-e2e",
            username="ig",
            access_token="tok",
            is_active=True,
        )
        product = Product.objects.create(user=user, name="E2E Snap", source=Product.Source.SNAP)
        Post.objects.create(
            user=user,
            product=product,
            social_account=ig,
            platform="instagram",
            content_text="Offer post",
            status=Post.Status.PUBLISHED,
            published_at=timezone.now(),
            cta_url="https://shop.test",
            cta_type="link",
        )
        Lead.objects.create(user=user, phone="254711122233", name="E2E Lead", source="qr")

        page.goto(f"{base_url}/accounts/login/")
        page.fill("input[name='login']", "wedgedemo@example.com")
        page.fill("input[name='password']", "TestPass123!@#")
        page.click("button[type='submit']")
        page.wait_for_load_state("networkidle")

        page.goto(f"{base_url}/brief/")
        page.wait_for_load_state("networkidle")
        expect(page.locator("body")).to_contain_text("Get the wedge loop running")
        expect(page.locator("body")).to_contain_text("Needs reply")
