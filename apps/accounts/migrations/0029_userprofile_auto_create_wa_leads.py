from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0028_userprofile_snap_blocked"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="auto_create_wa_leads",
            field=models.BooleanField(
                default=False,
                help_text="When True, inbound WhatsApp messages from new numbers auto-create a lead stub.",
            ),
        ),
    ]
