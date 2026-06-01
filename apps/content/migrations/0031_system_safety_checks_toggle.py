# Staff runtime toggle for content safety moderation checks

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("content", "0030_alter_contentsafetyincident_image_url"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="systemsafetyconfig",
            name="content_safety_checks_enabled",
            field=models.BooleanField(
                default=True,
                help_text=(
                    "When False, staff have paused all moderation checks "
                    "(vision, API text, local blocklist). Env CONTENT_SAFETY_ENABLED "
                    "must still be true for this to take effect."
                ),
            ),
        ),
        migrations.AddField(
            model_name="systemsafetyconfig",
            name="content_safety_paused_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="systemsafetyconfig",
            name="content_safety_paused_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
