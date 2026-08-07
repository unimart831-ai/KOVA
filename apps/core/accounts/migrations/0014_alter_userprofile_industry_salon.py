from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0013_userprofile_city_userprofile_country_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="userprofile",
            name="industry",
            field=models.CharField(
                blank=True,
                choices=[
                    ("saas", "SaaS / Software"),
                    ("ecommerce", "E-Commerce"),
                    ("agency", "Agency / Marketing"),
                    ("creator", "Creator / Influencer"),
                    ("consulting", "Consulting / Professional Services"),
                    ("nonprofit", "Nonprofit"),
                    ("education", "Education"),
                    ("health", "Health & Wellness"),
                    ("finance", "Finance"),
                    ("real_estate", "Real Estate"),
                    ("food_restaurant", "Food & Restaurant"),
                    ("wholesale_retail", "Wholesale & Retail"),
                    ("salon_beauty", "Salon & Beauty Services"),
                    ("fashion_beauty", "Fashion & Beauty"),
                    ("travel_tourism", "Travel & Tourism"),
                    ("media_entertainment", "Media & Entertainment"),
                    ("agriculture", "Agriculture"),
                    ("logistics_transport", "Logistics & Transport"),
                    ("construction", "Construction & Manufacturing"),
                    ("legal", "Legal Services"),
                    ("other", "Other"),
                ],
                max_length=30,
            ),
        ),
    ]
