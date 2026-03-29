"""Quick test for the scheduling engine."""
import os, sys, django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.development"
django.setup()

from apps.content.scheduling import get_next_best_slot, get_smart_queue_slot, get_quick_schedule_time
from django.contrib.auth import get_user_model

User = get_user_model()
user = User.objects.get(email="zuripay@kova.ai")

fmt = "%a %b %d, %I:%M %p"

print("=== Next Best Slot ===")
for platform in ["twitter", "linkedin", "instagram", "tiktok"]:
    slot = get_next_best_slot(user, platform)
    print(f"  {platform}: {slot.strftime(fmt)}")

print()
print("=== Smart Queue ===")
print(f"  Next slot: {get_smart_queue_slot(user).strftime(fmt)}")

print()
print("=== Quick Pick ===")
for opt in ["30min", "1hr", "3hr", "tomorrow_am", "tomorrow_pm"]:
    t = get_quick_schedule_time(opt)
    print(f"  {opt}: {t.strftime(fmt)}")
