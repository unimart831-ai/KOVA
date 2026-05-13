"""
Admin dashboard — Onboarding Funnel view.

Surfaces where signups drop out of the onboarding wizard and flags users
whose post-onboarding agency chain appears wedged (celery dropped, LLM
provider outage, etc.). Reads the UserProfile.onboarding_step_timestamps
map populated by apps/accounts/views.py:onboarding_view.

Also surfaces Tier-1/Tier-2 automation adoption — how many users took the
Magic Fill / URL inference / industry pack paths, plus the industry and
country mix of the recent cohort. The instrumentation markers it reads:

    path_choice_magic               user picked "auto-fill from social"
    path_choice_url                 user picked "paste my website"
    path_choice_manual              user picked "set up manually"
    magic_fill_applied:<platform>   profile_audit filled fields, by source
    url_inference_applied           LLM filled fields from a pasted URL
    industry_pack_applied:<ind>     starter pack filled defaults, by industry
"""

from collections import Counter
from datetime import timedelta
from statistics import median

from django.db.models import Q
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_datetime

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

    # ── Tier 1/2 automation adoption ─────────────────────────────────────
    #
    # Each profile carries instrumentation markers in onboarding_step_timestamps
    # so we can count how the new onboarding paths are actually being used.
    path_counts = {"magic": 0, "url": 0, "manual": 0, "unknown": 0}
    magic_provider_counts: Counter = Counter()
    url_success_count = 0
    industry_pack_count = 0

    industry_distribution: Counter = Counter()
    country_distribution: Counter = Counter()

    time_to_complete_seconds: list[int] = []

    for u in users:
        stamps = u.profile.onboarding_step_timestamps or {}

        # Path-choice: classify into one bucket; if user touched multiple
        # paths, the first one they recorded wins (earliest timestamp).
        path_keys = [
            ("magic", stamps.get("path_choice_magic")),
            ("url", stamps.get("path_choice_url")),
            ("manual", stamps.get("path_choice_manual")),
        ]
        earliest = None
        chosen = "unknown"
        for name, ts in path_keys:
            if not ts:
                continue
            parsed_ts = parse_datetime(ts)
            if parsed_ts and (earliest is None or parsed_ts < earliest):
                earliest = parsed_ts
                chosen = name
        path_counts[chosen] += 1

        # Magic-fill provider breakdown — keys look like
        # "magic_fill_applied:facebook".
        for key in stamps:
            if key.startswith("magic_fill_applied:"):
                magic_provider_counts[key.split(":", 1)[1]] += 1

        if "url_inference_applied" in stamps:
            url_success_count += 1

        if any(k.startswith("industry_pack_applied:") for k in stamps):
            industry_pack_count += 1

        # Industry / country distribution — only for users who got past Step 1.
        industry = (u.profile.industry or "").strip()
        if industry:
            industry_distribution[industry] += 1
        country = (u.profile.country or "").strip().upper()
        if country:
            country_distribution[country] += 1

        # Time-to-complete: signup -> step_4_completed (platform connect).
        # Excludes never-finished users so the median doesn't get pulled down
        # by abandoners.
        s4 = stamps.get("step_4_completed")
        if s4:
            parsed_s4 = parse_datetime(s4)
            if parsed_s4:
                delta = (parsed_s4 - u.date_joined).total_seconds()
                if delta > 0:
                    time_to_complete_seconds.append(int(delta))

    automation_summary = {
        "path_counts": path_counts,
        "magic_providers": magic_provider_counts.most_common(),
        "url_success": url_success_count,
        "industry_pack_hits": industry_pack_count,
        # Percent of completed users for each automation path. "completed"
        # here = step_4_completed fired, so the user actually reached the
        # platform-connect step.
        "completed_count": sum(1 for u in users if _has_step(u.profile, "step_4_completed")),
    }
    completed = automation_summary["completed_count"] or 1
    automation_summary["magic_pct"] = round(100 * path_counts["magic"] / completed)
    automation_summary["url_pct"] = round(100 * path_counts["url"] / completed)
    automation_summary["manual_pct"] = round(100 * path_counts["manual"] / completed)
    automation_summary["industry_pack_pct"] = round(100 * industry_pack_count / completed)

    median_seconds = median(time_to_complete_seconds) if time_to_complete_seconds else 0
    automation_summary["median_minutes_to_complete"] = round(median_seconds / 60, 1)
    automation_summary["completion_sample_size"] = len(time_to_complete_seconds)

    # Top-10 industry mix and top-5 country mix for the cohort.
    industry_mix = [
        {"key": key, "label": dict(_industry_label_map())[key] if key in _industry_label_map() else key,
         "count": count}
        for key, count in industry_distribution.most_common(10)
    ]
    country_mix = country_distribution.most_common(5)

    return render(request, "admin_dashboard/users/onboarding_funnel.html", {
        "page_title": "Onboarding Funnel",
        "total_signups": len(users),
        "stage_counts": stage_counts,
        "stuck_users": stuck_users[:50],
        "wizard_abandoners": wizard_abandoners[:50],
        "cohort_days": 60,
        "automation": automation_summary,
        "industry_mix": industry_mix,
        "country_mix": country_mix,
    })


def _industry_label_map():
    """UserProfile.Industry.choices as a dict, for human-readable funnel rows."""
    from apps.accounts.models import UserProfile
    return dict(UserProfile.Industry.choices)
