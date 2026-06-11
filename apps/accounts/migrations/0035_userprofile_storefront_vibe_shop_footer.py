from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0034_alter_user_is_support_staff"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="storefront_vibe",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "Auto (match industry)"),
                    ("classic_shop", "Classic shop"),
                    ("magazine", "Magazine"),
                    ("reels_first", "Reels first"),
                    ("minimal_catalog", "Minimal catalog"),
                    ("lookbook", "Lookbook"),
                ],
                default="",
                help_text="Layout style for your public /shop/ pages. Empty = auto from industry.",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="shop_footer",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text='Optional shop footer: {"hours": "...", "delivery_note": "...", "policy_url": "..."}',
            ),
        ),
    ]
