from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("media_queue", "0002_add_posts_per_slot"),
    ]

    operations = [
        migrations.AddField(
            model_name="queueitem",
            name="caption_variants",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='AI caption variants. Each: {"text": "...", "angle": "Hook|Value|Social|Promo"}.',
            ),
        ),
        migrations.AddField(
            model_name="queueitem",
            name="active_variant",
            field=models.PositiveSmallIntegerField(
                blank=True,
                null=True,
                help_text="Index of the user-selected variant. Null = auto-rotate by publish count.",
            ),
        ),
    ]
