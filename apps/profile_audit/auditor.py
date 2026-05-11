"""
Profile audit orchestration — the glue between providers, suggestion engine,
and the model layer.

Two public entry points:
  - audit_social_account(account) → ProfileAudit  : Phase 1 (read + score)
  - apply_suggestion(suggestion)   → bool          : Phase 3 (write)

The Celery task `run_profile_audits` in tasks.py calls these in a loop.
"""
from __future__ import annotations

import logging
from typing import Optional

from django.utils import timezone

from apps.platforms.encryption import decrypt_token
from apps.platforms.providers.base import (
    PlatformAuthError, ProfileSnapshot, ProfileUpdateResult,
)
from apps.platforms.providers.registry import get_provider

from apps.profile_audit.models import ProfileAudit, ProfileUpdateSuggestion
from apps.profile_audit.suggester import generate_suggestion

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────
# Audit (Phase 1) + Suggest (Phase 2)
# ──────────────────────────────────────────────────────────────────────────
def audit_social_account(account, *, generate_suggestions: bool = True) -> Optional[ProfileAudit]:
    """Run a profile audit on one SocialAccount.

    Creates a ProfileAudit row (never updates an existing one — audits are
    immutable snapshots). If `generate_suggestions=True` (Phase 2), also
    generates ProfileUpdateSuggestion rows for every missing/thin field.

    Returns the ProfileAudit instance (or None on irrecoverable failure).
    """
    provider = get_provider(account.platform)
    if not provider:
        logger.warning("No provider for %s (account %s)", account.platform, account.id)
        return None

    try:
        access_token = decrypt_token(account.access_token) if account.access_token else ""
    except Exception as exc:
        logger.warning("Token decrypt failed for account %s: %s", account.id, exc)
        access_token = ""

    if not access_token:
        return ProfileAudit.objects.create(
            social_account=account, user=account.user,
            error="No access token stored — account needs re-authentication.",
        )

    # Provider-specific kwargs (page_id for FB, ig_user_id for IG, org_urn for LinkedIn)
    kwargs = _audit_kwargs_for(account)

    snap: ProfileSnapshot
    try:
        snap = provider.audit_profile(access_token, **kwargs)
    except PlatformAuthError as exc:
        logger.info("Auth error auditing account %s: %s", account.id, exc)
        return ProfileAudit.objects.create(
            social_account=account, user=account.user,
            error=f"Authentication failed — reconnect this account. ({exc})",
        )
    except Exception as exc:
        logger.exception("Audit crashed for account %s", account.id)
        return ProfileAudit.objects.create(
            social_account=account, user=account.user,
            error=f"Audit failed: {exc}",
        )

    audit = ProfileAudit.objects.create(
        social_account=account,
        user=account.user,
        completeness_score=snap.completeness_score,
        fields_present=snap.fields_present,
        fields_missing=snap.fields_missing,
        fields_thin=snap.fields_thin,
        raw_profile=snap.raw_profile,
        error=snap.error,
    )

    if generate_suggestions and not snap.error:
        _generate_suggestions_for_audit(audit)

    account.last_synced_at = timezone.now()
    account.save(update_fields=["last_synced_at", "updated_at"])
    return audit


def _audit_kwargs_for(account) -> dict:
    """Provider-specific identifiers passed to audit_profile / update_profile.

    Stored in SocialAccount.metadata at OAuth time. We mirror them here so
    providers don't need to re-query."""
    md = account.metadata or {}
    if account.platform == "facebook":
        return {
            "page_id": md.get("page_id") or account.platform_user_id,
            "platform_user_id": account.platform_user_id,
        }
    if account.platform == "instagram":
        return {
            "ig_user_id": md.get("ig_user_id") or account.platform_user_id,
            "platform_user_id": account.platform_user_id,
        }
    if account.platform == "linkedin":
        return {
            # org_urn is set when the user has connected an organization page
            "org_urn": md.get("org_urn") or md.get("organization_urn"),
            "organization_id": md.get("organization_id"),
        }
    return {}


def _generate_suggestions_for_audit(audit: ProfileAudit) -> int:
    """For each missing or thin field, ask the suggester for a value.
    Skips fields where the suggester returns None (e.g., 'hours')."""
    count = 0
    candidate_fields = list(audit.fields_missing) + list(audit.fields_thin)
    seen = set()
    for field_name in candidate_fields:
        if field_name in seen:
            continue
        seen.add(field_name)
        try:
            suggestion = generate_suggestion(audit, field_name)
        except Exception:
            logger.exception("generate_suggestion crashed for %s/%s", audit.id, field_name)
            continue
        if not suggestion:
            continue
        current_value = audit.fields_present.get(field_name, "") if isinstance(audit.fields_present, dict) else ""
        ProfileUpdateSuggestion.objects.create(
            audit=audit,
            user=audit.user,
            social_account=audit.social_account,
            field_name=field_name,
            current_value=current_value or "",
            suggested_value=suggestion["value"],
            reasoning=suggestion.get("reasoning", ""),
        )
        count += 1
    return count


# ──────────────────────────────────────────────────────────────────────────
# Apply (Phase 3)
# ──────────────────────────────────────────────────────────────────────────
def apply_suggestion(suggestion: ProfileUpdateSuggestion) -> bool:
    """Push a single approved suggestion to the platform.

    Updates the suggestion row in-place with applied_at / applied_value
    / error_message / api_response. Returns True on success."""
    account = suggestion.social_account
    provider = get_provider(account.platform)
    if not provider:
        suggestion.status = ProfileUpdateSuggestion.Status.FAILED
        suggestion.error_message = f"No provider for {account.platform}."
        suggestion.save(update_fields=["status", "error_message", "updated_at"])
        return False

    try:
        access_token = decrypt_token(account.access_token) if account.access_token else ""
    except Exception as exc:
        suggestion.status = ProfileUpdateSuggestion.Status.FAILED
        suggestion.error_message = f"Token decrypt failed: {exc}"
        suggestion.save(update_fields=["status", "error_message", "updated_at"])
        return False

    if not access_token:
        suggestion.status = ProfileUpdateSuggestion.Status.FAILED
        suggestion.error_message = "No access token — account needs reconnection."
        suggestion.save(update_fields=["status", "error_message", "updated_at"])
        return False

    kwargs = _audit_kwargs_for(account)
    updates = {suggestion.field_name: suggestion.suggested_value}

    result: ProfileUpdateResult
    try:
        result = provider.update_profile(access_token, updates, **kwargs)
    except PlatformAuthError as exc:
        suggestion.status = ProfileUpdateSuggestion.Status.FAILED
        suggestion.error_message = f"Auth error: {exc}"
        suggestion.save(update_fields=["status", "error_message", "updated_at"])
        return False
    except Exception as exc:
        logger.exception("apply_suggestion crashed for %s", suggestion.id)
        suggestion.status = ProfileUpdateSuggestion.Status.FAILED
        suggestion.error_message = f"Update crashed: {exc}"
        suggestion.save(update_fields=["status", "error_message", "updated_at"])
        return False

    if not result.success:
        suggestion.status = ProfileUpdateSuggestion.Status.FAILED
        suggestion.error_message = result.error or "Unknown failure."
        suggestion.api_response = result.api_response or {}
        suggestion.save(update_fields=["status", "error_message", "api_response", "updated_at"])
        return False

    suggestion.status = ProfileUpdateSuggestion.Status.APPLIED
    suggestion.applied_at = timezone.now()
    suggestion.applied_value = result.applied_value or suggestion.suggested_value
    suggestion.api_response = result.api_response or {}
    suggestion.error_message = ""
    suggestion.save(update_fields=[
        "status", "applied_at", "applied_value",
        "api_response", "error_message", "updated_at",
    ])
    return True
