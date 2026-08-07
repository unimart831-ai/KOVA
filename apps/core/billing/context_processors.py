from apps.core.billing.models import get_sidebar_plan_display
from apps.core.billing.plan_limit_ui import pop_plan_limit_notice


def plan_limit_notice(request):
    return {"plan_limit_notice": pop_plan_limit_notice(request)}


def user_plan_sidebar(request):
    """Current plan label for app sidebar profile section."""
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {"user_plan_sidebar": {"label": "", "variant": "none", "is_staff": False}}
    return {"user_plan_sidebar": get_sidebar_plan_display(user)}
