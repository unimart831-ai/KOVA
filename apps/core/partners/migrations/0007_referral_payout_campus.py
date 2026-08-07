# Generated manually — marketplace audit P7 referral improvements.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("partners", "0006_partner_billing_webhooks_sandbox"),
    ]

    operations = [
        migrations.AddField(
            model_name="partnerapplication",
            name="application_type",
            field=models.CharField(
                choices=[("standard", "Standard Partner"), ("campus_rep", "Campus Rep")],
                db_index=True,
                default="standard",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="partner",
            name="application_type",
            field=models.CharField(
                choices=[("standard", "Standard Partner"), ("campus_rep", "Campus Rep")],
                db_index=True,
                default="standard",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="partner",
            name="stripe_connect_account_id",
            field=models.CharField(
                blank=True,
                help_text="Stripe Connect account ID for international payouts (v2 full Connect).",
                max_length=255,
            ),
        ),
        migrations.CreateModel(
            name="ReferralClick",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("referral_code", models.CharField(db_index=True, max_length=30)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.TextField(blank=True)),
                ("landing_path", models.CharField(blank=True, max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "partner",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="clicks",
                        to="partners.partner",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="PayoutRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount_kes", models.DecimalField(decimal_places=2, max_digits=10)),
                (
                    "mpesa_number",
                    models.CharField(
                        blank=True,
                        help_text="Kenyan M-Pesa number (254XXXXXXXXX).",
                        max_length=30,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending Review"),
                            ("approved", "Approved"),
                            ("paid", "Paid"),
                            ("rejected", "Rejected"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=10,
                    ),
                ),
                ("admin_notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
                (
                    "partner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="payout_requests",
                        to="partners.partner",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="referralclick",
            index=models.Index(fields=["referral_code", "-created_at"], name="partners_re_referra_idx"),
        ),
        migrations.AddIndex(
            model_name="referralclick",
            index=models.Index(fields=["partner", "-created_at"], name="partners_re_partner_idx"),
        ),
    ]
