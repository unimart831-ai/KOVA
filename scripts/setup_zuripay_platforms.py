"""Create mock social accounts for Zuri Pay testing."""
import os, sys, django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.development"
django.setup()

from django.contrib.auth import get_user_model
from apps.platforms.models import SocialAccount
from django.utils import timezone
from datetime import timedelta

User = get_user_model()
user = User.objects.get(email="zuripay@kova.ai")
print(f"User: {user.email} (onboarding: {user.onboarding_completed})")

platforms = [
    {
        "platform": "twitter",
        "platform_user_id": "zp_tw_001",
        "username": "@ZuriPayHQ",
        "display_name": "Zuri Pay",
    },
    {
        "platform": "linkedin",
        "platform_user_id": "zp_li_001",
        "username": "zuri-pay",
        "display_name": "Zuri Pay",
    },
    {
        "platform": "instagram",
        "platform_user_id": "zp_ig_001",
        "username": "@zuripay",
        "display_name": "Zuri Pay",
    },
    {
        "platform": "tiktok",
        "platform_user_id": "zp_tt_001",
        "username": "@zuripay",
        "display_name": "Zuri Pay",
    },
]

for p in platforms:
    acct, created = SocialAccount.objects.get_or_create(
        user=user,
        platform=p["platform"],
        platform_user_id=p["platform_user_id"],
        defaults={
            "username": p["username"],
            "display_name": p["display_name"],
            "access_token": "mock_token_" + p["platform"],
            "refresh_token": "mock_refresh_" + p["platform"],
            "token_expires_at": timezone.now() + timedelta(days=90),
            "token_scope": "read write",
            "is_active": True,
            "metadata": {"mock": True, "note": "Dev testing account"},
        },
    )
    status = "Created" if created else "Already exists"
    print(f"  {status}: {p['platform']} -- {p['username']}")

print(f"\nTotal connected: {SocialAccount.objects.filter(user=user, is_active=True).count()}")
print("Done! Refresh the Platforms page to see them.")
