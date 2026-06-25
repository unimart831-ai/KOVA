"""
Admin dashboard — Onboarding Funnel view.

Surfaces where signups drop out of the onboarding wizard and flags users
whose post-onboarding agency chain appears wedged (celery dropped, LLM
provider outage, etc.). Reads the UserProfile.onboarding_step_timestamps
map populated by apps/accounts/views.py:onboarding_view.

Also surfaces Tier-1/Tier-2 automation adoption — how many users took the
Magic Fill / URL inference / industry pack paths, plus the industry and
country mix of the recent cohort. The instrumentation markers it reads:

    path_choice_sell               user picked "sell products" on intent screen
    path_choice_magic               user picked auto-fill from social
    path_choice_url                 user picked "paste my website"
    path_choice_manual              user picked "set up manually"
    magic_fill_applied:<platform>   profile_audit filled fields, by source
    url_inference_applied           LLM filled fields from a pasted URL
    industry_pack_applied:<ind>     starter pack filled defaults, by industry
"""

from collections import Counter
from datetime import timedelta
from statistics import median

from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.accounts.models import User, UserProfile
from apps.admin_dashboard.decorators import staff_required
from apps.agents.onboarding_tasks import STUCK_AFTER_SECONDS


# Express onboarding funnel — phone → intent → 2 wizard steps → finish.
FUNNEL_STAGES = [
    ("signed_up", "Signed up", None),
    ("phone_collected", "Phone on file", "__phone__"),
    ("path_choice", "Intent / path chosen", "__path_choice__"),
    ("brand_voice_completed", "Brand voice captured", "brand_voice_completed"),
    ("step_1_completed", "Step 1 — About your business (legacy)", "step_1_completed"),
    ("step_2_completed", "Brand confirmed", "step_2_completed"),
    ("step_4_completed", "Finished setup", "step_4_completed"),
    ("intelligence_completed", "Agency chain finished", "intelligence_completed"),
]

_PATH_CHOICE_MARKERS = (
    "discovery_completed",
    "path_choice_magic", "path_choice_url", "path_choice_manual", "path_choice_sell",
    "intent_sell", "intent_grow", "intent_both",
)


def _has_path_choice(profile) -> bool:
    if not profile:
        return False
    stamps = profile.onboarding_step_timestamps or {}
    return any(stamps.get(k) for k in _PATH_CHOICE_MARKERS)


def _user_profile(user):
    try:
        return user.profile
    except UserProfile.DoesNotExist:
        return None


def _aware_step_ts(raw):
    """Parse onboarding step timestamps to timezone-aware datetimes."""
    if not raw:
        return None
    if not isinstance(raw, str):
        raw = str(raw)
    parsed = parse_datetime(raw)
    if parsed is None:
        return None
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed, timezone.utc)
    return parsed


def _aware_dt(value):
    """Ensure a datetime from the ORM is timezone-aware."""
    if value is None:
        return None
    if timezone.is_naive(value):
        return timezone.make_aware(value, timezone.utc)
    return value


def _has_step(profile, step_key):
    if not profile:
        return False
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
        elif step_stamp == "__phone__":
            count = sum(1 for u in users if (u.phone_number or "").strip())
        elif step_stamp == "__path_choice__":
            count = sum(1 for u in users if _has_path_choice(_user_profile(u)))
        else:
            count = sum(1 for u in users if _has_step(_user_profile(u), step_stamp))
        stage_counts.append({"key": key, "label": label, "count": count})

    phone_missing_users = [
        u for u in users
        if not (u.phone_number or "").strip() and not u.onboarding_completed
    ][:50]
    phone_missing_count = sum(1 for u in users if not (u.phone_number or "").strip())

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
        p = _user_profile(u)
        if not p:
            continue
        started = _aware_dt(p.onboarding_intelligence_started_at)
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
        profile = _user_profile(u)
        if not profile:
            joined = _aware_dt(u.date_joined)
            if joined and joined < abandon_cutoff:
                wizard_abandoners.append({
                    "user": u,
                    "last_step": "(no profile)",
                    "last_stamp": joined,
                    "hours_idle": int((now - joined).total_seconds() // 3600),
                })
            continue
        stamps = profile.onboarding_step_timestamps or {}
        last_step = None
        last_parsed = None
        for step_key in ("step_2_completed", "step_1_completed"):
            parsed_ts = _aware_step_ts(stamps.get(step_key))
            if parsed_ts and (last_parsed is None or parsed_ts > last_parsed):
                last_parsed = parsed_ts
                last_step = step_key
        if last_parsed:
            if last_parsed < abandon_cutoff:
                wizard_abandoners.append({
                    "user": u,
                    "last_step": last_step,
                    "last_stamp": last_parsed,
                    "hours_idle": int((now - last_parsed).total_seconds() // 3600),
                })
        else:
            # Signed up but never submitted step 1 — only flag if >24h old
            joined = _aware_dt(u.date_joined)
            if joined and joined < abandon_cutoff:
                wizard_abandoners.append({
                    "user": u,
                    "last_step": "(never started)",
                    "last_stamp": joined,
                    "hours_idle": int((now - joined).total_seconds() // 3600),
                })
    wizard_abandoners.sort(key=lambda r: r["hours_idle"], reverse=True)

    # ── Tier 1/2 automation adoption ─────────────────────────────────────
    #
    # Each profile carries instrumentation markers in onboarding_step_timestamps
    # so we can count how the new onboarding paths are actually being used.
    path_counts = {"magic": 0, "url": 0, "manual": 0, "sell": 0, "unknown": 0}
    intent_counts = {"sell": 0, "grow": 0, "both": 0}
    magic_provider_counts: Counter = Counter()
    url_success_count = 0
    industry_pack_count = 0

    industry_distribution: Counter = Counter()
    country_distribution: Counter = Counter()

    time_to_complete_seconds: list[int] = []

    for u in users:
        profile = _user_profile(u)
        if not profile:
            path_counts["unknown"] += 1
            continue
        stamps = profile.onboarding_step_timestamps or {}

        # Path-choice: classify into one bucket; if user touched multiple
        # paths, the first one they recorded wins (earliest timestamp).
        path_keys = [
            ("sell", stamps.get("path_choice_sell") or stamps.get("intent_sell")),
            ("magic", stamps.get("path_choice_magic")),
            ("url", stamps.get("path_choice_url")),
            ("manual", stamps.get("path_choice_manual")),
        ]
        earliest = None
        chosen = "unknown"
        for name, ts in path_keys:
            parsed_ts = _aware_step_ts(ts)
            if parsed_ts and (earliest is None or parsed_ts < earliest):
                earliest = parsed_ts
                chosen = name
        path_counts[chosen] += 1

        for intent_key in ("sell", "grow", "both"):
            if stamps.get(f"intent_{intent_key}") or (
                intent_key == "sell" and stamps.get("path_choice_sell")
            ):
                intent_counts[intent_key] += 1
                break

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
        industry = (profile.industry or "").strip()
        if industry:
            industry_distribution[industry] += 1
        country = (profile.country or "").strip().upper()
        if country:
            country_distribution[country] += 1

        # Time-to-complete: signup -> step_4_completed (onboarding finished).
        parsed_s4 = _aware_step_ts(stamps.get("step_4_completed"))
        if parsed_s4:
            joined = _aware_dt(u.date_joined)
            if joined:
                delta = (parsed_s4 - joined).total_seconds()
                if delta > 0:
                    time_to_complete_seconds.append(int(delta))

    automation_summary = {
        "path_counts": path_counts,
        "magic_providers": magic_provider_counts.most_common(),
        "url_success": url_success_count,
        "industry_pack_hits": industry_pack_count,
        # Percent of completed users for each automation path. "completed"
        # here = step_4_completed fired (onboarding finished).
        "completed_count": sum(
            1 for u in users if _has_step(_user_profile(u), "step_4_completed")
        ),
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

    from apps.accounts.setup_mission import get_onboarding_intent, is_commerce_industry
    from apps.products.models import Product

    sell_cohort_total = 0
    sell_with_product = 0
    sell_shop_live = 0
    for u in users:
        p = _user_profile(u)
        if not p:
            continue
        if get_onboarding_intent(p) in ("sell", "both") or is_commerce_industry(p.industry):
            sell_cohort_total += 1
            if Product.objects.filter(user=u, is_active=True).exists():
                sell_with_product += 1
            if p.page_slug and Product.objects.filter(user=u, is_active=True).exists():
                sell_shop_live += 1

    return render(request, "admin_dashboard/users/onboarding_funnel.html", {
        "page_title": "Onboarding Funnel",
        "total_signups": len(users),
        "stage_counts": stage_counts,
        "stuck_users": stuck_users[:50],
        "wizard_abandoners": wizard_abandoners[:50],
        "phone_missing_users": phone_missing_users,
        "phone_missing_count": phone_missing_count,
        "phone_coverage_pct": round(
            100 * (len(users) - phone_missing_count) / len(users)
        ) if users else 100,
        "cohort_days": 60,
        "automation": automation_summary,
        "intent_counts": intent_counts,
        "sell_cohort_total": sell_cohort_total,
        "sell_with_product": sell_with_product,
        "sell_shop_live": sell_shop_live,
        "industry_mix": industry_mix,
        "country_mix": country_mix,
    })


def _industry_label_map():
    """UserProfile.Industry.choices as a dict, for human-readable funnel rows."""
    from apps.accounts.models import UserProfile
    return dict(UserProfile.Industry.choices)
