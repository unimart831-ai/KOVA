"""Quick check of all social accounts."""
import django, os
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.development"
django.setup()

from apps.platforms.models import SocialAccount

print(f"Total accounts: {SocialAccount.objects.count()}\n")
for sa in SocialAccount.objects.all():
    pages = sa.metadata.get("pages", [])
    print(f"Account: {sa.display_name}")
    print(f"  Platform: {sa.platform}")
    print(f"  Active: {sa.is_active}")
    print(f"  User ID: {sa.platform_user_id}")
    print(f"  Pages: {len(pages)}")
    for p in pages:
        print(f"    - {p['name']} (ID: {p['id']})")
    print(f"  Token expires: {sa.token_expires_at}")
    print(f"  Has token: {bool(sa.access_token)}")
    print(f"  Owner: {sa.user}")
    print()
