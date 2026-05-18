from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("content", "0019_add_content_intent"),
    ]

    operations = [
        migrations.AddField(
            model_name="post",
            name="post_format",
            field=models.CharField(
                choices=[
                    ("text", "Text"),
                    ("image", "Image"),
                    ("carousel", "Carousel"),
                    ("story", "Story"),
                    ("reel", "Reel"),
                    ("video", "Video"),
                ],
                db_index=True,
                default="text",
                max_length=20,
                help_text="The content format — drives which publish API endpoint is called.",
            ),
        ),
        migrations.AddField(
            model_name="post",
            name="carousel_slides",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Ordered carousel slides. Each: {heading, body, image_prompt, image_url}.",
            ),
        ),
        migrations.AddField(
            model_name="post",
            name="aspect_ratio",
            field=models.CharField(
                blank=True,
                choices=[
                    ("square", "Square (1:1)"),
                    ("portrait", "Portrait (4:5)"),
                    ("landscape", "Landscape (16:9)"),
                    ("story", "Story / Reel (9:16)"),
                ],
                default="square",
                max_length=20,
                help_text="Aspect ratio for image/video generation. Derived from post_format if not set.",
            ),
        ),
        migrations.AddIndex(
            model_name="post",
            index=models.Index(fields=["user", "post_format", "-created_at"], name="content_post_user_format_idx"),
        ),
    ]
