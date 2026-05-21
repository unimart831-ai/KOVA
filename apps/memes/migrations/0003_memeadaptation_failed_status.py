from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("memes", "0002_trendalert"),
    ]

    operations = [
        migrations.AddField(
            model_name="memeadaptation",
            name="error_message",
            field=models.TextField(blank=True, help_text="Why adaptation failed, if status=failed"),
        ),
        migrations.AlterField(
            model_name="memeadaptation",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "Draft"),
                    ("approved", "Approved"),
                    ("published", "Published"),
                    ("rejected", "Rejected"),
                    ("failed", "Failed"),
                ],
                db_index=True,
                default="draft",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="memepreferences",
            name="excluded_categories",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Categories to never show, e.g., ['political']. Political excluded by default for new users.",
            ),
        ),
    ]
