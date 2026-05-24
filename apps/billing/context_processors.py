from apps.billing.plan_limit_ui import pop_plan_limit_notice


def plan_limit_notice(request):
    return {"plan_limit_notice": pop_plan_limit_notice(request)}
