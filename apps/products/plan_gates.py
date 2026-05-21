"""Plan limit helpers for Products features."""

from apps.billing.models import get_plan_limits


def product_plan_context(user):
    profile = getattr(user, "profile", None)
    plan = getattr(profile, "plan", "starter") if profile else "starter"
    limits = get_plan_limits(plan)
    return {
        "plan": plan,
        "max_products": limits.get("max_products", 5),
        "quantity_tracking": bool(limits.get("product_quantity_tracking")),
        "csv_import": bool(limits.get("product_csv_import")),
    }
