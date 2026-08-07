from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("content", "0034_kova_plan_and_marketing_campaign"),
        ("analytics", "0013_shopify_oauth"),
    ]

    operations = [
        migrations.AddField(
            model_name="conversion",
            name="marketing_campaign",
            field=models.ForeignKey(
                blank=True,
                help_text="Marketing campaign this event is attributed to.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="conversions",
                to="content.marketingcampaign",
            ),
        ),
        migrations.AddIndex(
            model_name="conversion",
            index=models.Index(
                fields=["user", "marketing_campaign", "-created_at"],
                name="analytics_c_user_id_camp_idx",
            ),
        ),
    ]
