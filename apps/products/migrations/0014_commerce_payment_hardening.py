"""
Add idempotency, EXPIRED status, and attempts_count to CommercePayment.

- transaction_ref: unique idempotency key (user:product:phone:time_bucket)
- attempts_count: how many STK push attempts the buyer made
- status: adds EXPIRED choice for stale pending payments
"""

from django.db import migrations, models


def backfill_transaction_refs(apps, schema_editor):
    """Give existing payments a unique transaction_ref so the NOT NULL + UNIQUE constraint holds."""
    CommercePayment = apps.get_model("products", "CommercePayment")
    for payment in CommercePayment.objects.all().iterator():
        payment.transaction_ref = f"legacy:{payment.pk}"
        payment.save(update_fields=["transaction_ref"])


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0013_product_fulfillment_fields"),
    ]

    operations = [
        # 1. Add transaction_ref as nullable first (so existing rows don't break)
        migrations.AddField(
            model_name="commercepayment",
            name="transaction_ref",
            field=models.CharField(
                db_index=True,
                help_text="Idempotency key: user_id:product_id:phone:timestamp_bucket",
                max_length=255,
                null=True,
                blank=True,
            ),
        ),
        # 2. Backfill existing rows
        migrations.RunPython(backfill_transaction_refs, migrations.RunPython.noop),
        # 3. Make it NOT NULL + UNIQUE
        migrations.AlterField(
            model_name="commercepayment",
            name="transaction_ref",
            field=models.CharField(
                db_index=True,
                help_text="Idempotency key: user_id:product_id:phone:timestamp_bucket",
                max_length=255,
                unique=True,
            ),
        ),
        # 4. Add attempts_count
        migrations.AddField(
            model_name="commercepayment",
            name="attempts_count",
            field=models.PositiveSmallIntegerField(
                default=1,
                help_text="How many STK push attempts the buyer made for this transaction",
            ),
        ),
        # 5. Update status choices to include EXPIRED
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
        # 6. Add index on transaction_ref
        migrations.AddIndex(
            model_name="commercepayment",
            index=models.Index(fields=["transaction_ref"], name="products_co_transac_idx"),
        ),
    ]
