from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("leads", "0002_nurturesequence_leadenrollment_nurturestep"),
    ]

    operations = [
        migrations.AddField(
            model_name="lead",
            name="temperature",
            field=models.CharField(
                choices=[("hot", "Hot"), ("warm", "Warm"), ("cold", "Cold")],
                default="cold",
                help_text="HOT = ready to buy now, WARM = interested, COLD = early awareness.",
                max_length=10,
            ),
        ),
        migrations.AddIndex(
            model_name="lead",
            index=models.Index(
                fields=["user", "temperature", "-first_seen_at"],
                name="leads_lead_user_temp_idx",
            ),
        ),
    ]
