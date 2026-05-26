from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0002_add_booking_unique_together"),
        ("products", "0012_batchsnapsession"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="booking_link",
            field=models.ForeignKey(
                blank=True,
                help_text="If this is a service, use this booking page as the primary fulfillment path.",
                null=True,
                on_delete=models.SET_NULL,
                related_name="products",
                to="bookings.bookinglink",
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="fulfillment_notes",
            field=models.TextField(
                blank=True,
                help_text="Optional instructions for how customers book, access, or receive this offer.",
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="fulfillment_url",
            field=models.URLField(
                blank=True,
                help_text="Optional external booking, access, or delivery URL for service and digital offers.",
            ),
        ),
    ]
