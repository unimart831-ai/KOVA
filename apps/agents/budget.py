"""Per-user LLM token budget enforcement.

The platform pays for every token the agents consume. Without a hard cap,
a single power user (or a runaway feedback loop) could burn through the
month's inference budget on a Starter plan. This module is the single
choke point the LLM layer calls before issuing a request.

Design:
- One ``UserTokenBucket`` row per user per UTC day.
- ``check_budget()`` raises ``PlanLimitExceeded`` if today's consumption
  plus a worst-case estimate for the new call would exceed the plan cap.
- ``record_usage()`` increments the bucket atomically with ``F()`` so
  concurrent agent runs can't race past the cap by one call apiece.

The plan cap lives in ``PLAN_LIMITS[plan]["daily_llm_tokens"]``; missing
plans fall back to the Starter cap so an unknown plan never gets a free
ride. ``user=None`` callers (system / cron) skip enforcement — these
should be migrated as we identify them.
"""
from __future__ import annotations

import logging

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.billing.exceptions import PlanLimitExceeded
from apps.billing.enforcement import get_user_daily_llm_token_cap
from apps.billing.models import get_effective_plan_tier, get_plan_limits, get_user_plan_limits

logger = logging.getLogger(__name__)


def _cost_per_1k(model: str) -> tuple[float, float]:
    from apps.agents.pricing import get_cost_per_1k

    return get_cost_per_1k(model)


def _plan_daily_cap(user) -> int:
    return get_user_daily_llm_token_cap(user)


def _user_plan(user) -> str:
    try:
        return get_effective_plan_tier(user.profile)
    except Exception:
        return "starter"


def check_budget(user, max_tokens: int) -> None:
    """Raise ``PlanLimitExceeded`` if this call would push the user over today's cap.

    The check is intentionally pessimistic — we assume the call will use
    the full ``max_tokens`` we asked the model to produce. That over-counts
    on average but means we never wake up to a surprise bill because a
    response happened to spill over.

    Callers that have no ``user`` context (system tasks, periodic jobs)
    pass ``user=None`` and are not metered. Those callsites should be
    migrated as we find them.
    """
    if user is None or not getattr(user, "is_authenticated", True):
        return

    cap = _plan_daily_cap(user)
    if cap <= 0:
        # Plan with explicit zero cap (treat as disabled). Only flag if a
        # call is attempted at all so we surface the misconfig.
        raise PlanLimitExceeded(
            "AI features are not enabled on your plan. Upgrade to use the agents.",
            limit_type="daily_llm_tokens",
        )

    today = timezone.now().date()
    from apps.agents.models import UserTokenBucket

    bucket = UserTokenBucket.objects.filter(user=user, period_date=today).first()
    used = (bucket.input_tokens + bucket.output_tokens) if bucket else 0

    if used + max_tokens > cap:
        plan = _user_plan(user)
        suggested = _next_plan(plan)
        limits = get_user_plan_limits(user)
        msg = (
            f"You've used {used:,} of your {cap:,} daily AI tokens on the "
            f"{limits.get('label', plan)} plan. "
        )
        if suggested:
            msg += f"Upgrade to {suggested.title()} for a higher daily allowance."
        else:
            msg += "Daily allowance resets at 00:00 UTC."
        raise PlanLimitExceeded(
            msg, limit_type="daily_llm_tokens", suggested_plan=suggested
        )


def record_usage(user, model: str, input_tokens: int, output_tokens: int) -> None:
    """Atomically increment today's bucket for ``user`` after a successful call.

    Cost is computed from ``settings.MODEL_TOKEN_COSTS`` and stored as
    micro-USD so multiple workers can ``F()``-increment without losing
    fractional cents to rounding.
    """
    if user is None or not getattr(user, "is_authenticated", True):
        return
    if input_tokens <= 0 and output_tokens <= 0:
        return

    today = timezone.now().date()
    in_cost, out_cost = _cost_per_1k(model)
    cost_usd = (input_tokens / 1000.0) * in_cost + (output_tokens / 1000.0) * out_cost
    cost_micros = int(round(cost_usd * 1_000_000))

    from apps.agents.models import UserTokenBucket

    # get_or_create is racy under high concurrency, but the unique_together
    # constraint plus the F() update below keeps the math correct: at worst
    # two workers create a row in parallel and one INSERT loses to the
    # IntegrityError; we then fall through to the UPDATE branch.
    with transaction.atomic():
        bucket, created = UserTokenBucket.objects.get_or_create(
            user=user,
            period_date=today,
            defaults={
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd_micros": cost_micros,
                "call_count": 1,
            },
        )
        if not created:
            UserTokenBucket.objects.filter(pk=bucket.pk).update(
                input_tokens=F("input_tokens") + input_tokens,
                output_tokens=F("output_tokens") + output_tokens,
                cost_usd_micros=F("cost_usd_micros") + cost_micros,
                call_count=F("call_count") + 1,
            )


def _next_plan(plan: str) -> str:
    """Return the next plan tier above the current one, or '' if at top."""
    order = ["starter", "growth", "pro", "agency"]
    try:
        idx = order.index(plan)
    except ValueError:
        return "growth"
    return order[idx + 1] if idx + 1 < len(order) else ""
