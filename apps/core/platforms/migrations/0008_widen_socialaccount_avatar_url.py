from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("platforms", "0007_alter_socialaccount_platform"),
    ]

    operations = [
        migrations.AlterField(
            model_name="socialaccount",
            name="avatar_url",
            field=models.URLField(blank=True, max_length=2048),
        ),
    ]
