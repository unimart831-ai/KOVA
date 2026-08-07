# Nurture trigger/action choice expansion — CharField values only (no schema change).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("leads", "0004_rename_leads_lead_user_temp_idx_leads_lead_user_id_5e62e3_idx"),
    ]

    operations = [
        migrations.AlterField(
            model_name="nurturesequence",
            name="trigger",
            field=models.CharField(
                choices=[
                    ("all_new", "All new leads"),
                    ("from_form", "From form submissions"),
                    ("from_social", "From social (DMs & comments)"),
                    ("high_priority", "High-priority leads only"),
                    ("from_platform", "From specific platform"),
                    ("from_commerce", "From commerce purchases"),
                    ("from_booking", "From bookings"),
                    ("from_walk_in", "From walk-ins"),
                    ("from_qr_scan", "From QR scans"),
                    ("stale_winback", "Stale leads (7+ days inactive)"),
                    ("manual", "Manual enrollment only"),
                ],
                default="all_new",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="nurturestep",
            name="action_type",
            field=models.CharField(
                choices=[
                    ("send_email", "Send Email"),
                    ("send_whatsapp", "Send WhatsApp"),
                    ("add_tag", "Add Tag"),
                    ("change_status", "Change Status"),
                ],
                default="send_email",
                max_length=20,
            ),
        ),
    ]
