"""
Admin dashboard — Onboarding Funnel view.

Surfaces where signups drop out of the onboarding wizard and flags users
whose post-onboarding agency chain appears wedged (celery dropped, LLM
provider outage, etc.). Reads the UserProfile.onboarding_step_timestamps
map populated by apps/accounts/views.py:onboarding_view.
"""

from datetime import timedelta

from django.db.models import Q
from django.shortcuts import render
from django.utils import timezone

from apps.accounts.models import User
from apps.admin_dashboard.decorators import staff_required
from apps.agents.onboarding_tasks import STUCK_AFTER_SECONDS


# Funnel stages, ordered. Each key maps to a predicate over UserProfile.
#
# Wizard structure is now 3 UI steps (was 4): Step 1 basics → Step 2 review
# (merged voice + goals) → Step 3 connect platform. The merged Step 2 page
# fires BOTH `step_2_completed` and `step_3_completed` so historical user
# data still maps cleanly onto the funnel. For new users you'll see those
# two stages tied — that's expected, the form saves them together. For users
# who signed up before the merge, `step_2_completed` and `step_3_completed`
# represent two distinct form submits and may show real drop-off between
# them.
FUNNEL_STAGES = [
    ("signed_up", "Signed up", None),
    ("step_1_completed", "Step 1 — Basics", "step_1_completed"),
    ("step_2_completed", "Step 2 — Review (voice saved)", "step_2_completed"),
    ("step_3_completed", "Step 2 — Review (full saved)", "step_3_completed"),
    ("step_4_completed", "Step 3 — Connect platform", "step_4_completed"),
    ("intelligence_completed", "Agency chain finished", "intelligence_completed"),
]


def _has_step(profile, step_key):
    return bool((profile.onboarding_step_timestamps or {}).get(step_key))


@staff_required
def onboarding_funnel(request):
    """Signup → completion funnel with stuck-user triage list."""
    now = timezone.now()

    # Scope to users signed up in the last 60 days so long-dead cohorts
    # don't drag down conversion numbers.
    cutoff = now - timedelta(days=60)
    users = list(
        User.objects.select_related("profile")
        .filter(date_joined__gte=cutoff, is_active=True, is_deleted=False)
        .order_by("-date_joined")
    )

    stage_counts = []
    for key, label, step_stamp in FUNNEL_STAGES:
        if step_stamp is None:
            count = len(users)
        else:
            count = sum(1 for u in users if _has_step(u.profile, step_stamp))
        stage_counts.append({"key": key, "label": label, "count": count})

    # Drop-off between successive stages (relative to previous stage)
    for i, stage in enumerate(stage_counts):
        if i == 0 or stage_counts[i - 1]["count"] == 0:
            stage["retention_pct"] = 100 if stage["count"] else 0
            stage["dropped"] = 0
        else:
            prev = stage_counts[i - 1]["count"]
            stage["retention_pct"] = round(100 * stage["count"] / prev)
            stage["dropped"] = prev - stage["count"]

    # Stuck on the agency chain: dispatched, never completed, >5min elapsed.
    stuck_cutoff = now - timedelta(seconds=STUCK_AFTER_SECONDS)
    stuck_users = []
    for u in users:
        p = u.profile
        started = p.onboarding_intelligence_started_at
        if not started or started > stuck_cutoff:
            continue
        if _has_step(p, "intelligence_completed"):
            continue
        stamps = p.onboarding_step_timestamps or {}
        stuck_users.append({
            "user": u,
            "started_at": started,
            "minutes_stuck": int((now - started).total_seconds() // 60),
            "retried": "intelligence_retried" in stamps,
        })
    stuck_users.sort(key=lambda r: r["minutes_stuck"], reverse=True)

    # Wizard abandoners: onboarding_completed=False + last step_N_completed
    # timestamp > 24h ago. Helps diagnose which step bleeds hardest.
    abandon_cutoff = now - timedelta(hours=24)
    wizard_abandoners = []
    for u in users:
        if u.onboarding_completed:
            continue
        stamps = u.profile.onboarding_step_timestamps or {}
        last_step = None
        last_stamp = None
        for step_key in ("step_1_completed", "step_2_completed", "step_3_completed"):
            ts = stamps.get(step_key)
            if ts and (last_stamp is None or ts > last_stamp):
                last_stamp = ts
                last_step = step_key
        if last_stamp:
            from django.utils.dateparse import parse_datetime
            parsed = parse_datetime(last_stamp)
            if parsed and parsed < abandon_cutoff:
                wizard_abandoners.append({
                    "user": u,
                    "last_step": last_step,
                    "last_stamp": parsed,
                    "hours_idle": int((now - parsed).total_seconds() // 3600),
                })
        else:
            # Signed up but never submitted step 1 — only flag if >24h old
            if u.date_joined < abandon_cutoff:
                wizard_abandoners.append({
                    "user": u,
                    "last_step": "(never started)",
                    "last_stamp": u.date_joined,
                    "hours_idle": int((now - u.date_joined).total_seconds() // 3600),
                })
    wizard_abandoners.sort(key=lambda r: r["hours_idle"], reverse=True)

    return render(request, "admin_dashboard/users/onboarding_funnel.html", {
        "page_title": "Onboarding Funnel",
        "total_signups": len(users),
        "stage_counts": stage_counts,
        "stuck_users": stuck_users[:50],
        "wizard_abandoners": wizard_abandoners[:50],
        "cohort_days": 60,
    })
