"""
Celery tasks for profile audits.

- run_profile_audits: nightly fan-out. For every active SocialAccount,
  fire audit_one_account.
- audit_one_account: per-account audit + suggestion generation.
- apply_one_suggestion: pushes a single approved suggestion to the platform.
"""
from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone

from apps.profile_audit.auditor import apply_suggestion, audit_social_account
from apps.profile_audit.models import ProfileUpdateSuggestion

logger = logging.getLogger(__name__)


@shared_task(name="profile_audit.run_profile_audits")
def run_profile_audits() -> dict:
    """Nightly: audit every active, supported social account."""
    from apps.platforms.models import SocialAccount

    # Phase 1 supports FB, IG, LinkedIn (others return not-supported snapshots)
    supported = ["facebook", "instagram", "linkedin"]
    qs = SocialAccount.objects.filter(is_active=True, platform__in=supported)

    audited = errors = 0
    for account in qs.iterator():
        try:
            audit_one_account.delay(str(account.id))
            audited += 1
        except Exception:
            errors += 1
            logger.exception("Failed to enqueue audit for %s", account.id)
    logger.info("Profile audit fan-out complete: audited=%d errors=%d", audited, errors)
    return {"audited": audited, "errors": errors}


@shared_task(
    name="profile_audit.audit_one_account",
    autoretry_for=(Exception,),
    retry_backoff=120,
    max_retries=2,
)
def audit_one_account(account_id: str) -> dict:
    from apps.platforms.models import SocialAccount

    try:
        account = SocialAccount.objects.get(id=account_id, is_active=True)
    except SocialAccount.DoesNotExist:
        return {"status": "skipped", "reason": "account not found or inactive"}

    audit = audit_social_account(account, generate_suggestions=True)
    if not audit:
        return {"status": "failed"}
    return {
        "audit_id": audit.id,
        "score": audit.completeness_score,
        "missing": len(audit.fields_missing or []),
        "thin": len(audit.fields_thin or []),
        "suggestions": audit.suggestions.count(),
        "error": audit.error or None,
    }


@shared_task(
    name="profile_audit.apply_one_suggestion",
    autoretry_for=(Exception,),
    retry_backoff=60,
    max_retries=2,
)
def apply_one_suggestion(suggestion_id: int) -> dict:
    try:
        suggestion = ProfileUpdateSuggestion.objects.get(id=suggestion_id)
    except ProfileUpdateSuggestion.DoesNotExist:
        return {"status": "skipped", "reason": "suggestion not found"}

    if suggestion.status not in (
        ProfileUpdateSuggestion.Status.APPROVED,
        ProfileUpdateSuggestion.Status.FAILED,
    ):
        return {"status": "skipped", "reason": f"suggestion not actionable ({suggestion.status})"}

    ok = apply_suggestion(suggestion)

    # Post-apply: trigger a fresh audit so the user sees the updated score
    if ok:
        try:
            audit_one_account.delay(str(suggestion.social_account.id))
        except Exception:
            logger.exception("Failed to re-queue audit after apply for %s", suggestion.social_account.id)

    return {
        "suggestion_id": suggestion.id,
        "applied": ok,
        "field": suggestion.field_name,
        "error": suggestion.error_message,
        "completed_at": timezone.now().isoformat(),
    }
