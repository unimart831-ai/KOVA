# Generated manually — fernet_fields blocked makemigrations in this environment.

import apps.platforms.encryption
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("analytics", "0012_alter_pageview_section"),
    ]

    operations = [
        migrations.AddField(
            model_name="shopifystore",
            name="oauth_installed_at",
            field=models.DateTimeField(blank=True, help_text="When the store was connected via Shopify OAuth.", null=True),
        ),
        migrations.AddField(
            model_name="shopifystore",
            name="scopes",
            field=models.CharField(blank=True, help_text="Granted OAuth scopes.", max_length=500),
        ),
        migrations.AlterField(
            model_name="shopifystore",
            name="access_token",
            field=apps.platforms.encryption.EncryptedTokenField(
                help_text="Shopify Admin API access token (encrypted at rest).",
            ),
        ),
        migrations.AlterField(
            model_name="shopifystore",
            name="webhook_secret",
            field=models.CharField(
                blank=True,
                help_text="Optional per-store HMAC secret; OAuth apps use SHOPIFY_API_SECRET.",
                max_length=255,
            ),
        ),
    ]
