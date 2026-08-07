from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("content", "0025_weeklycontentplan_updated_at"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="post",
            index=models.Index(
                fields=["user", "status", "published_at"],
                name="content_post_user_pub_idx",
            ),
        ),
    ]
