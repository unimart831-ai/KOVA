"""
Tests for the accounts app: User model, soft-delete, profile creation.
"""

import pytest
from django.test import TestCase

from apps.core.accounts.models import User, UserProfile


@pytest.mark.django_db
class TestUserModel:
    def test_create_user(self):
        u = User.objects.create_user(username="a", email="a@b.com", password="Pass1234!")
        assert u.pk is not None
        assert u.email == "a@b.com"
        assert u.check_password("Pass1234!")

    def test_user_str(self):
        u = User.objects.create_user(username="x", email="x@y.com", password="P", full_name="Jane Doe")
        assert str(u) == "Jane Doe"

    def test_user_str_falls_back_to_email(self):
        u = User.objects.create_user(username="z", email="z@y.com", password="P")
        assert str(u) == "z@y.com"

    def test_first_initial(self):
        u = User(full_name="Alice")
        assert u.first_initial == "A"


@pytest.mark.django_db
class TestSoftDelete:
    def test_soft_delete_excludes_from_default_manager(self):
        u = User.objects.create_user(username="sd", email="sd@t.com", password="P")
        u.soft_delete()
        assert User.objects.filter(pk=u.pk).count() == 0

    def test_soft_delete_visible_via_all_objects(self):
        u = User.objects.create_user(username="sd2", email="sd2@t.com", password="P")
        u.soft_delete()
        assert User.all_objects.filter(pk=u.pk).count() == 1
        assert u.is_deleted is True
        assert u.deleted_at is not None

    def test_restore(self):
        u = User.objects.create_user(username="rs", email="rs@t.com", password="P")
        u.soft_delete()
        u.restore()
        assert User.objects.filter(pk=u.pk).count() == 1
        assert u.is_deleted is False
        assert u.deleted_at is None


@pytest.mark.django_db
class TestUserProfile:
    def test_profile_creation(self):
        u = User.objects.create_user(username="p", email="p@t.com", password="P")
        profile = UserProfile.objects.create(user=u, plan="starter")
        assert profile.plan == "starter"
        assert str(profile) == f"Profile: {u}"

    def test_encrypted_fields_roundtrip(self):
        """stripe_customer_id and mpesa_phone should encrypt/decrypt transparently."""
        u = User.objects.create_user(username="enc", email="enc@t.com", password="P")
        profile = UserProfile.objects.create(
            user=u,
            stripe_customer_id="cus_test123",
            mpesa_phone="254712345678",
        )
        # Re-fetch from DB
        profile.refresh_from_db()
        assert profile.stripe_customer_id == "cus_test123"
        assert profile.mpesa_phone == "254712345678"
