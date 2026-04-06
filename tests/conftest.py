"""
Shared pytest fixtures for the Kova Agent test suite.
"""

import pytest
from django.test import RequestFactory

from apps.accounts.models import User, UserProfile


@pytest.fixture
def user(db):
    """Create a test user with profile."""
    u = User.objects.create_user(
        username="testuser",
        email="test@kova.ai",
        password="TestPass123!",
        full_name="Test User",
    )
    UserProfile.objects.create(user=u, plan="growth")
    return u


@pytest.fixture
def staff_user(db):
    """Create a staff user."""
    return User.objects.create_user(
        username="staffuser",
        email="staff@kova.ai",
        password="StaffPass123!",
        is_staff=True,
    )


@pytest.fixture
def superuser(db):
    """Create a superuser."""
    return User.objects.create_superuser(
        username="admin",
        email="admin@kova.ai",
        password="AdminPass123!",
    )


@pytest.fixture
def rf():
    """Django RequestFactory."""
    return RequestFactory()


@pytest.fixture
def auth_client(client, user):
    """Logged-in test client."""
    client.login(email="test@kova.ai", password="TestPass123!")
    return client
