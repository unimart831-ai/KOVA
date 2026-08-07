from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0029_userprofile_auto_create_wa_leads"),
    ]

    operations = [
        migrations.RenameField(
            model_name="userprofile",
            old_name="auto_create_wa_leads",
            new_name="autopilot_auto_create_wa_leads",
        ),
        migrations.AddField(
            model_name="userprofile",
            name="autopilot_auto_enroll_leads",
            field=models.BooleanField(
                default=False,
                help_text="Auto-enroll new leads in your default Welcome nurture sequence.",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="autopilot_auto_publish_approved",
            field=models.BooleanField(
                default=False,
                help_text="Publish approved posts when scheduled_at is due — no extra click.",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="autopilot_wa_faq_replies",
            field=models.BooleanField(
                default=False,
                help_text="Auto-reply to WhatsApp messages matching your FAQ keyword rules.",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="autopilot_wa_followup_24h",
            field=models.BooleanField(
                default=False,
                help_text="Send a utility follow-up if a customer message has no owner reply in 24h.",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="wa_faq_answers",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='Up to 5 FAQ rules: [{"keywords": ["hours", "open"], "reply": "..."}]',
            ),
        ),
    ]
