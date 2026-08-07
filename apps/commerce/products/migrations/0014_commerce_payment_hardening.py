"""
Add idempotency, EXPIRED status, and attempts_count to CommercePayment.

- transaction_ref: unique idempotency key (user:product:phone:time_bucket)
- attempts_count: how many STK push attempts the buyer made
- status: adds EXPIRED choice for stale pending payments

Uses Django schema operations (not raw PostgreSQL SQL) so SQLite local dev works.
"""

from django.db import migrations, models


def backfill_transaction_refs(apps, schema_editor):
    """Give existing payments a unique transaction_ref so the UNIQUE constraint holds."""
    CommercePayment = apps.get_model("products", "CommercePayment")
    for payment in CommercePayment.objects.filter(transaction_ref__isnull=True).iterator():
        payment.transaction_ref = f"legacy:{payment.pk}"
        payment.save(update_fields=["transaction_ref"])


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0013_product_fulfillment_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="commercepayment",
            name="transaction_ref",
            field=models.CharField(
                help_text="Idempotency key: user_id:product_id:phone:timestamp_bucket",
                max_length=255,
                null=True,
                blank=True,
            ),
        ),
        migrations.RunPython(backfill_transaction_refs, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="commercepayment",
            name="transaction_ref",
            field=models.CharField(
                help_text="Idempotency key: user_id:product_id:phone:timestamp_bucket",
                max_length=255,
                unique=True,
            ),
        ),
        migrations.AddField(
            model_name="commercepayment",
            name="attempts_count",
            field=models.PositiveSmallIntegerField(
                default=1,
                help_text="How many STK push attempts the buyer made for this transaction",
            ),
        ),
        migrations.AlterField(
            model_name="commercepayment",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("completed", "Completed"),
                    ("failed", "Failed"),
                    ("expired", "Expired"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
    ]
