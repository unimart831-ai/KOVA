from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("content", "0029_content_safety"),
    ]

    operations = [
        migrations.AlterField(
            model_name="contentsafetyincident",
            name="image_url",
            field=models.CharField(
                blank=True,
                help_text="HTTPS URL or private storage path for staff review.",
                max_length=2000,
            ),
        ),
    ]
