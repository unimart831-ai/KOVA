"""
Add idempotency, EXPIRED status, and attempts_count to CommercePayment.

- transaction_ref: unique idempotency key (user:product:phone:time_bucket)
- attempts_count: how many STK push attempts the buyer made
- status: adds EXPIRED choice for stale pending payments

This migration is idempotent — safe to re-run after partial failure.
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
        # 1. Add transaction_ref as nullable first (idempotent via RunSQL)
        migrations.RunSQL(
            sql="""
                ALTER TABLE products_commercepayment
                ADD COLUMN IF NOT EXISTS transaction_ref VARCHAR(255) NULL;
            """,
            reverse_sql="""
                ALTER TABLE products_commercepayment
                DROP COLUMN IF EXISTS transaction_ref;
            """,
            state_operations=[
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
            ],
        ),
        # 2. Backfill existing rows (only nulls, so safe to re-run)
        migrations.RunPython(backfill_transaction_refs, migrations.RunPython.noop),
        # 3. Make NOT NULL + UNIQUE (idempotent)
        migrations.RunSQL(
            sql="""
                ALTER TABLE products_commercepayment
                ALTER COLUMN transaction_ref SET NOT NULL;

                DO $$ BEGIN
                    ALTER TABLE products_commercepayment
                    ADD CONSTRAINT products_commercepayment_transaction_ref_key
                    UNIQUE (transaction_ref);
                EXCEPTION WHEN duplicate_table OR duplicate_object THEN
                    NULL;
                END $$;
            """,
            reverse_sql="""
                ALTER TABLE products_commercepayment
                ALTER COLUMN transaction_ref DROP NOT NULL;
                ALTER TABLE products_commercepayment
                DROP CONSTRAINT IF EXISTS products_commercepayment_transaction_ref_key;
            """,
            state_operations=[
                migrations.AlterField(
                    model_name="commercepayment",
                    name="transaction_ref",
                    field=models.CharField(
                        help_text="Idempotency key: user_id:product_id:phone:timestamp_bucket",
                        max_length=255,
                        unique=True,
                    ),
                ),
            ],
        ),
        # 4. Add attempts_count (idempotent)
        migrations.RunSQL(
            sql="""
                ALTER TABLE products_commercepayment
                ADD COLUMN IF NOT EXISTS attempts_count SMALLINT NOT NULL DEFAULT 1;
            """,
            reverse_sql="""
                ALTER TABLE products_commercepayment
                DROP COLUMN IF EXISTS attempts_count;
            """,
            state_operations=[
                migrations.AddField(
                    model_name="commercepayment",
                    name="attempts_count",
                    field=models.PositiveSmallIntegerField(
                        default=1,
                        help_text="How many STK push attempts the buyer made for this transaction",
                    ),
                ),
            ],
        ),
        # 5. Update status choices to include EXPIRED (no-op at DB level, Django-only)
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
