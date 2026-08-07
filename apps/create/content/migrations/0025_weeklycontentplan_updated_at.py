import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("content", "0024_contentseed_generation_log"),
    ]

    operations = [
        migrations.AddField(
            model_name="weeklycontentplan",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
    ]
