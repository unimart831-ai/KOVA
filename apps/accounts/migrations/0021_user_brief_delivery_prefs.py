from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0020_userprofile_commerce_autopilot"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="brief_email_enabled",
            field=models.BooleanField(
                default=True,
                help_text="Send the daily brief to your email (Growth plan and above).",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="brief_whatsapp_enabled",
            field=models.BooleanField(
                default=True,
                help_text="Send a morning brief ping to WhatsApp (Pro plan and above).",
            ),
        ),
    ]
