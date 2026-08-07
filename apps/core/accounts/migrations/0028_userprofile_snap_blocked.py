from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("content", "0029_content_safety"),
        ("accounts", "0027_userprofile_content_safety"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="snap_blocked_until",
            field=models.DateTimeField(
                blank=True,
                help_text="When set and in the future, Snap to Sell is blocked for this user only.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="snap_blocked_incident",
            field=models.ForeignKey(
                blank=True,
                help_text="Incident that applied the current snap block (cleared on dismiss).",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="content.contentsafetyincident",
            ),
        ),
    ]
