from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("analytics", "0010_competitorscreenshot_performancerecycle"),
    ]

    operations = [
        migrations.AddField(
            model_name="shopifystore",
            name="last_product_sync",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="shopifystore",
            name="products_synced",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Products imported from this Shopify store into Kova catalog.",
            ),
        ),
    ]
