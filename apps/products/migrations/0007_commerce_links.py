from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0006_restockscan"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="commerce_slug",
            field=models.SlugField(
                blank=True,
                db_index=True,
                help_text="Public slug for Commerce Link (/shop/<page>/<slug>/). Auto-generated.",
                max_length=60,
            ),
        ),
        migrations.CreateModel(
            name="CommercePayment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("checkout_request_id", models.CharField(db_index=True, max_length=100, unique=True)),
                ("merchant_request_id", models.CharField(blank=True, max_length=100)),
                ("receipt_number", models.CharField(blank=True, db_index=True, max_length=50)),
                ("phone_number", models.CharField(max_length=15)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("currency", models.CharField(default="KES", max_length=5)),
                ("status", models.CharField(
                    choices=[("pending", "Pending"), ("completed", "Completed"), ("failed", "Failed")],
                    default="pending",
                    max_length=20,
                )),
                ("source", models.CharField(
                    choices=[("commerce_link", "Commerce Link"), ("whatsapp", "WhatsApp")],
                    default="commerce_link",
                    max_length=20,
                )),
                ("result_code", models.IntegerField(blank=True, null=True)),
                ("result_desc", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("product", models.ForeignKey(
                    blank=True, null=True, on_delete=models.deletion.SET_NULL,
                    related_name="commerce_payments", to="products.product",
                )),
                ("user", models.ForeignKey(
                    on_delete=models.deletion.CASCADE,
                    related_name="commerce_payments", to="accounts.user",
                )),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="commercepayment",
            index=models.Index(fields=["user", "-created_at"], name="products_co_user_id_idx"),
        ),
        migrations.AddIndex(
            model_name="commercepayment",
            index=models.Index(fields=["product", "-created_at"], name="products_co_product_idx"),
        ),
        migrations.AddIndex(
            model_name="commercepayment",
            index=models.Index(fields=["status", "-created_at"], name="products_co_status_idx"),
        ),
        migrations.AddIndex(
            model_name="product",
            index=models.Index(fields=["user", "commerce_slug"], name="products_pr_user_co_idx"),
        ),
        migrations.AddConstraint(
            model_name="product",
            constraint=models.UniqueConstraint(
                condition=models.Q(("commerce_slug__gt", "")),
                fields=("user", "commerce_slug"),
                name="unique_commerce_slug_per_user",
            ),
        ),
    ]
