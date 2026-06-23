from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("leads", "0006_alter_lead_source_type_and_more"),
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
                    ("from_booking_intent", "Booking intent (social)"),
                    ("from_walk_in", "From walk-ins"),
                    ("from_qr_scan", "From QR scans"),
                    ("stale_winback", "Stale leads (7+ days inactive)"),
                    ("manual", "Manual enrollment only"),
                ],
                default="all_new",
                max_length=20,
            ),
        ),
    ]
