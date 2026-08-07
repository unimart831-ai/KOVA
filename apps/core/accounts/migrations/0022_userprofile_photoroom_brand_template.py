# Generated manually for Phase D Photoroom brand template

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0021_user_brief_delivery_prefs"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="photoroom_brand_template",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text=(
                    "Optional locked Photoroom Plus styling: shadow_mode, padding, ai_seed, "
                    "outline_color, style_suffix, enabled."
                ),
            ),
        ),
    ]
