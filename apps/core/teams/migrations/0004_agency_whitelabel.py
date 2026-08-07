# Generated manually — marketplace audit P6 white-label fields.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("teams", "0003_team_deleted_at_team_is_deleted_alter_team_owner"),
    ]

    operations = [
        migrations.AddField(
            model_name="brand",
            name="custom_domain",
            field=models.CharField(
                blank=True,
                help_text="Custom domain for commerce/Kova Link (display + CNAME setup).",
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name="brand",
            name="custom_domain_verified",
            field=models.BooleanField(
                default=False,
                help_text="True once DNS CNAME is verified (manual for v1).",
            ),
        ),
        migrations.AddField(
            model_name="brand",
            name="logo_url",
            field=models.URLField(
                blank=True,
                help_text="Agency/client logo URL for reports and commerce pages.",
            ),
        ),
        migrations.AddField(
            model_name="brand",
            name="theme_primary_color",
            field=models.CharField(
                blank=True,
                help_text="Hex accent color for client-facing pages, e.g. #059669.",
                max_length=7,
            ),
        ),
        migrations.AddField(
            model_name="teammember",
            name="brand",
            field=models.ForeignKey(
                blank=True,
                help_text="For client role — limits dashboard to this brand's content.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="client_members",
                to="teams.brand",
            ),
        ),
        migrations.AddField(
            model_name="teaminvitation",
            name="brand",
            field=models.ForeignKey(
                blank=True,
                help_text="Required when inviting a client — scopes them to one brand.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="invitations",
                to="teams.brand",
            ),
        ),
        migrations.AlterField(
            model_name="teammember",
            name="role",
            field=models.CharField(
                choices=[
                    ("owner", "Owner"),
                    ("admin", "Admin"),
                    ("editor", "Editor"),
                    ("viewer", "Viewer"),
                    ("client", "Client"),
                ],
                default="editor",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="teaminvitation",
            name="role",
            field=models.CharField(
                choices=[
                    ("owner", "Owner"),
                    ("admin", "Admin"),
                    ("editor", "Editor"),
                    ("viewer", "Viewer"),
                    ("client", "Client"),
                ],
                default="editor",
                max_length=20,
            ),
        ),
    ]
