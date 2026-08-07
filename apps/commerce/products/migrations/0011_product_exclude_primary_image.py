"""Allow hiding the original upload when Plus scenes exist."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0010_default_studio_polish_plus"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="exclude_primary_image",
            field=models.BooleanField(
                default=False,
                help_text="When true, original upload is kept on file but omitted from carousels and posts.",
            ),
        ),
    ]
