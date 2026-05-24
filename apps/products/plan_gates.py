"""Plan limit helpers for Products features."""

from apps.billing.models import get_effective_plan_tier, get_user_plan_limits
from apps.products.photoroom import studio_polish_unavailable_message


def product_plan_context(user):
    profile = getattr(user, "profile", None)
    plan = get_effective_plan_tier(profile) if profile else "starter"
    limits = get_user_plan_limits(user)
    from apps.billing.visual_credits import get_visual_credit_usage

    return {
        "plan": plan,
        "max_products": limits.get("max_products", 5),
        "quantity_tracking": bool(limits.get("product_quantity_tracking")),
        "csv_import": bool(limits.get("product_csv_import")),
        "shopify_integration": bool(limits.get("shopify_integration")),
        "mpesa_commerce": bool(limits.get("mpesa_commerce")),
        "visual_credits": get_visual_credit_usage(user),
        "visual_enhance_premium": bool(limits.get("visual_enhance_premium")),
        "plus_max_variants_per_product": limits.get("plus_max_variants_per_product", 3),
        "studio_polish_notice": studio_polish_unavailable_message(),
    }
