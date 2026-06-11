import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0032_user_is_support_staff"),
    ]

    operations = [
        migrations.CreateModel(
            name="PilotMetricsSnapshot",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("snapshot_date", models.DateField(unique=True)),
                ("captured_at", models.DateTimeField()),
                ("aggregate", models.JSONField(default=dict)),
                ("businesses", models.JSONField(default=list)),
            ],
            options={
                "ordering": ["-snapshot_date"],
            },
        ),
    ]
