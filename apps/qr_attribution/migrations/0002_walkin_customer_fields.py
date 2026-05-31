from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("qr_attribution", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="walkinevent",
            name="customer_name",
            field=models.CharField(
                blank=True,
                help_text="Optional name captured at cashier for lead creation.",
                max_length=200,
            ),
        ),
        migrations.AddField(
            model_name="walkinevent",
            name="customer_phone",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Optional phone (E.164 or local) — creates a Lead when set.",
                max_length=20,
            ),
        ),
    ]
