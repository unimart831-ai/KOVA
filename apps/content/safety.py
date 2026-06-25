"""
Content safety — OpenRouter vision/text moderation with fail-closed publishing gates.

Blocks clearly sexual or sexually explicit images and captions before they reach
social platforms. Incidents are logged for staff review in the admin dashboard.
"""

from __future__ import annotations

import base64
import logging
import re
from dataclasses import dataclass, field
from typing import BinaryIO

from django.conf import settings

logger = logging.getLogger(__name__)

# Sexual/explicit only — violence, hate, drugs, etc. are out of scope for vision moderation.
SEXUAL_POLICY_CATEGORIES = frozenset({
    "adult",
    "sexual",
    "nudity",
    "porn",
})
POLICY_CATEGORIES = SEXUAL_POLICY_CATEGORIES  # backward-compatible alias

POLICY_BLOCK_MESSAGE = (
    "This content violates Kova content policy and cannot be published."
)
SNAP_POLICY_MESSAGE = (
    "This image violates Kova content policy and cannot be used."
)

DEFAULT_HIGH_SEVERITY_THRESHOLD = 85
HIGH_SEVERITY_THRESHOLD = DEFAULT_HIGH_SEVERITY_THRESHOLD  # backward-compatible alias
STRIKE_SUSPEND_THRESHOLD = 3
DEFAULT_SNAP_BLOCK_HOURS = 72

# ── Keyword-based risk signals (fast, no API needed) ─────────────────────────

BLOCKLIST_PATTERNS = [
    r"\b(n[i1]gg[ae]r|f[a@]gg[o0]t|k[i1]ke|sp[i1]c|ch[i1]nk|wetback)\b",
    r"\b(kill\s+(yourself|them|him|her)|bomb\s+threat|i\s+will\s+(shoot|murder|stab))\b",
    r"\b(commit\s+suicide|slit\s+(your|my)\s+wrists|end\s+it\s+all)\b",
    r"\b(porn|xxx|sex\s+tape|nudes?\s+for\s+sale)\b",
    r"\b(send\s+bitcoin|wire\s+transfer|nigerian\s+prince|guaranteed\s+returns)\b",
    r"\b(password|ssn|credit\s+card\s+number)\b",
]

HALLUCINATION_PATTERNS = [
    r"\[insert\s+",
    r"\{insert\s+",
    r"\[your\s+",
    r"\{your\s+",
    r"\[brand\s*name\]",
    r"\[company\s*name\]",
    r"\[product\s*name\]",
    r"as\s+an?\s+ai\b",
    r"i'?m\s+an?\s+ai\b",
    r"language\s+model\b",
    r"openai|chatgpt|claude|gemini|copilot",
]

ENGAGEMENT_BAIT_PATTERNS = [
    r"(?:like|share|retweet)\s+if\s+you\s+agree",
    r"comment\s+\d+\s+if\s+you",
]

_MODERATION_SYSTEM = (
    "You are a content moderation assistant for a business social-media platform. "
    "Your ONLY job is to detect clearly sexual or sexually explicit content. "
    "BLOCK only: clear sexual nudity intended to arouse, pornography, sexually explicit "
    "poses or acts meant to arouse, or overt sexual solicitation. "
    "Do NOT flag: construction sites, architecture, landscapes, industrial or work scenes, "
    "people in normal street or work clothing, news or documentary violence, weapons without "
    "sexual context, drugs or alcohol unless sexualized, swimwear or underwear in catalog or "
    "product context, fitness or sports, non-pornographic art, medical or educational imagery, "
    "breastfeeding in non-sexual documentary context, or generic 'sensitive' scenes. "
    "When uncertain, return safe=true (benefit of the doubt). "
    "Require high confidence before flagging. Respond with JSON only."
)

_MODERATION_JSON_SCHEMA = (
    'Return JSON: {"safe": boolean, "severity": 0-100, '
    '"categories": ["adult"|"sexual"|"nudity"|"porn"], '
    '"reasons": ["short explanation"]}. '
    "Use categories ONLY for sexual/explicit violations — never for violence, gore, hate, "
    "drugs, or non-sexual topics. "
    "Set safe=false only when highly confident of a sexual/explicit violation; "
    "severity must be 85+ to flag. If unsure, set safe=true and severity below 50."
)


@dataclass
class SafetyResult:
    """Result of a content safety check."""

    safe: bool = True
    reasons: list[str] = field(default_factory=list)
    severity: int = 0
    categories: list[str] = field(default_factory=list)
    api_failed: bool = False

    @property
    def blocked(self) -> bool:
        return not self.safe

    @property
    def is_safe(self) -> bool:
        return self.safe

    @property
    def flags(self) -> list[tuple[str, str]]:
        return [(cat or "policy", reason) for cat, reason in zip(
            self.categories + [""] * len(self.reasons),
            self.reasons,
        )]

    @property
    def risk_score(self) -> int:
        return self.severity

    @property
    def summary(self) -> str:
        if not self.reasons:
            return "Content passed all safety checks."
        parts = []
        if self.categories:
            parts.append(f"categories={','.join(self.categories)}")
        parts.extend(self.reasons[:3])
        return "; ".join(parts)

    def merge(self, other: SafetyResult) -> SafetyResult:
        if not other.safe:
            self.safe = False
        self.severity = max(self.severity, other.severity)
        for reason in other.reasons:
            if reason not in self.reasons:
                self.reasons.append(reason)
        for cat in other.categories:
            if cat not in self.categories:
                self.categories.append(cat)
        self.api_failed = self.api_failed or other.api_failed
        return self


def content_safety_enabled() -> bool:
    """Deploy-time master switch (CONTENT_SAFETY_ENABLED)."""
    return bool(getattr(settings, "CONTENT_SAFETY_ENABLED", False))


def content_safety_staff_paused() -> bool:
    """Staff paused all checks via admin while env safety is on."""
    if not content_safety_enabled():
        return False
    from apps.content.models import SystemSafetyConfig

    config = SystemSafetyConfig.load()
    return not getattr(config, "content_safety_checks_enabled", True)


def content_safety_checks_running() -> bool:
    """Env enabled and staff have not paused moderation."""
    return content_safety_enabled() and not content_safety_staff_paused()


def moderation_model() -> str:
    return getattr(
        settings,
        "CONTENT_SAFETY_MODEL",
        "google/gemini-2.5-flash",
    )


_MODERATION_MODEL_FALLBACKS = (
    "google/gemini-2.5-flash",
    "google/gemini-2.0-flash-001",
    "openai/gpt-4o-mini",
)


def is_publishing_paused(user=None) -> tuple[bool, str]:
    """Return (paused, reason) for global or per-user auto-publish pause."""
    from apps.content.models import SystemSafetyConfig

    config = SystemSafetyConfig.load()
    if config.auto_publish_paused:
        return True, "Platform auto-publish is paused by staff."

    if user is None:
        return False, ""

    profile = getattr(user, "profile", None)
    if not profile:
        return False, ""

    if profile.suspended_for_policy:
        return True, "Account suspended for content policy violation."
    if profile.auto_publish_paused:
        return True, "Auto-publish paused for your account."
    if profile.emergency_pause:
        return True, "Publishing paused — emergency pause is active."

    return False, ""


def _strike_suspend_threshold() -> int:
    return int(getattr(settings, "CONTENT_SAFETY_STRIKE_SUSPEND_THRESHOLD", STRIKE_SUSPEND_THRESHOLD))


def _high_severity_threshold() -> int:
    return int(
        getattr(
            settings,
            "CONTENT_SAFETY_HIGH_SEVERITY_THRESHOLD",
            DEFAULT_HIGH_SEVERITY_THRESHOLD,
        )
    )


def is_sexual_policy_violation(result: SafetyResult) -> bool:
    """True for confident sexual/explicit violations — drives strikes and snap blocks."""
    if result.api_failed or result.safe:
        return False
    if not any(c in SEXUAL_POLICY_CATEGORIES for c in result.categories):
        return False
    return result.severity >= _high_severity_threshold()


def is_snap_blocked(user) -> tuple[bool, str]:
    """Return (blocked, reason) for per-user Snap to Sell policy blocks only."""
    from django.utils import timezone

    profile = getattr(user, "profile", None)
    if not profile:
        return False, ""

    if profile.suspended_for_policy:
        return True, "Your account is suspended for content policy violations."

    if profile.snap_blocked_until and profile.snap_blocked_until > timezone.now():
        return True, (
            "Snap to Sell is temporarily blocked while your recent upload is reviewed."
        )

    if (profile.content_safety_strike_count or 0) >= _strike_suspend_threshold():
        return True, "Snap to Sell is blocked due to repeated content policy violations."

    return False, ""


def apply_user_snap_block(user, incident, result: SafetyResult) -> None:
    """Apply a per-user snap block for confirmed sexual policy violations — never global."""
    if not is_sexual_policy_violation(result):
        return

    from datetime import timedelta

    from django.utils import timezone

    profile = getattr(user, "profile", None)
    if not profile:
        return

    hours = int(getattr(settings, "CONTENT_SAFETY_SNAP_BLOCK_HOURS", DEFAULT_SNAP_BLOCK_HOURS))
    profile.snap_blocked_until = timezone.now() + timedelta(hours=hours)
    profile.snap_blocked_incident = incident
    profile.save(update_fields=["snap_blocked_until", "snap_blocked_incident"])


def clear_snap_block_for_dismissed_incident(incident) -> None:
    """Clear snap block when staff dismisses a false-positive incident."""
    from apps.accounts.models import UserProfile

    profile = UserProfile.objects.filter(user=incident.user).first()
    if not profile or profile.snap_blocked_incident_id != incident.pk:
        return

    profile.snap_blocked_until = None
    profile.snap_blocked_incident = None
    profile.save(update_fields=["snap_blocked_until", "snap_blocked_incident"])


def staff_incident_image_url(incident) -> str | None:
    """Resolve a staff-only view URL for flagged media (presigned when private R2/S3)."""
    ref = (incident.image_url or "").strip()
    if not ref:
        return None
    if ref.startswith("data:"):
        return None
    if ref.startswith(("http://", "https://")):
        return ref

    from apps.content.tasks import _public_url_for_file

    return _public_url_for_file(ref.lstrip("/"), for_platform_api=True)


def save_incident_image(uploaded_file) -> str:
    """Persist an uploaded image for staff review; returns storage path."""
    import uuid

    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage

    from apps.products.image_utils import normalize_uploaded_image

    path = f"content_safety/incidents/{uuid.uuid4()}.jpg"
    try:
        content = normalize_uploaded_image(uploaded_file)
    except ValueError as exc:
        logger.warning("Incident image normalize failed (%s) — storing raw bytes", exc)
        if hasattr(uploaded_file, "seek"):
            uploaded_file.seek(0)
        raw = uploaded_file.read() if hasattr(uploaded_file, "read") else b""
        if hasattr(uploaded_file, "seek"):
            uploaded_file.seek(0)
        if not raw:
            return ""
        content = ContentFile(raw, name="incident_upload.bin")

    return default_storage.save(path, content)


def _fail_closed_result(reason: str) -> SafetyResult:
    return SafetyResult(
        safe=False,
        reasons=[reason],
        severity=100,
        categories=["policy"],
        api_failed=True,
    )


def _local_text_checks(text: str, result: SafetyResult) -> SafetyResult:
    if not text:
        result.reasons.append("Post has no content text")
        result.severity = max(result.severity, 30)
        return result

    text_lower = text.lower()

    for pattern in BLOCKLIST_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            result.safe = False
            result.severity = 100
            result.categories.append("policy")
            result.reasons.append(f"Matched blocked pattern")
            return result

    for pattern in HALLUCINATION_PATTERNS:
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match:
            result.reasons.append(f"AI template detected: '{match.group()[:40]}'")
            result.severity = max(result.severity, 40)

    stripped = text.strip()
    if len(stripped) < 10:
        result.reasons.append(f"Content is only {len(stripped)} characters")
        result.severity = max(result.severity, 20)

    for pattern in ENGAGEMENT_BAIT_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            result.reasons.append("Engagement bait detected")
            result.severity = max(result.severity, 15)
            break

    alpha_chars = [c for c in text if c.isalpha()]
    if len(alpha_chars) > 20:
        caps_ratio = sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)
        if caps_ratio > 0.7:
            result.reasons.append(f"Content is {caps_ratio:.0%} uppercase")
            result.severity = max(result.severity, 15)

    if re.search(r"(.)\1{9,}", text):
        result.reasons.append("Excessive character repetition")
        result.severity = max(result.severity, 20)

    if result.severity >= _high_severity_threshold():
        result.safe = False

    return result


def _parse_moderation_response(data: dict) -> SafetyResult:
    severity = int(data.get("severity") or 0)
    categories = [
        c for c in (data.get("categories") or [])
        if c in SEXUAL_POLICY_CATEGORIES
    ]
    reasons = [str(r) for r in (data.get("reasons") or []) if r]

    if categories and not reasons:
        reasons = [f"Detected: {', '.join(categories)}"]

    threshold = _high_severity_threshold()
    unsafe = bool(categories and severity >= threshold)
    safe = not unsafe

    return SafetyResult(
        safe=safe,
        reasons=reasons if not safe else [],
        severity=severity if not safe else min(severity, threshold - 1),
        categories=categories if not safe else [],
    )


def _openrouter_moderate_text(text: str, user=None) -> SafetyResult:
    from apps.agents.llm import _get_openrouter_client, parse_llm_json

    if not getattr(settings, "OPENROUTER_API_KEY", ""):
        if content_safety_enabled():
            return _fail_closed_result("Moderation API unavailable (no API key)")
        return SafetyResult()

    client = _get_openrouter_client()
    prompt = f"{_MODERATION_JSON_SCHEMA}\n\nContent to review:\n{text[:8000]}"
    messages = [
        {"role": "system", "content": _MODERATION_SYSTEM},
        {"role": "user", "content": prompt},
    ]

    last_exc = None
    for model in _moderation_models_to_try():
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=512,
                temperature=0,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content or "{}"
            return _parse_moderation_response(parse_llm_json(content))
        except Exception as exc:
            last_exc = exc
            err = str(exc).lower()
            if "404" in err or "no endpoints found" in err:
                logger.warning("Content safety model %s unavailable, trying fallback", model)
                continue
            logger.error("Content safety text moderation failed: %s", exc)
            break

    if last_exc:
        logger.error("Content safety text moderation failed: %s", last_exc)
        err = str(last_exc).lower()
        if content_safety_enabled() and (
            "404" in err or "no endpoints found" in err
        ):
            return SafetyResult(
                safe=True,
                api_failed=True,
                reasons=["Moderation skipped — model unavailable"],
            )
        if content_safety_enabled():
            return _fail_closed_result(f"Moderation API error: {last_exc}")
    return SafetyResult()


def _moderation_models_to_try() -> list[str]:
    primary = moderation_model()
    seen = {primary}
    models = [primary]
    for slug in _MODERATION_MODEL_FALLBACKS:
        if slug not in seen:
            models.append(slug)
            seen.add(slug)
    return models


def _openrouter_moderate_image(image_url: str, user=None) -> SafetyResult:
    from apps.agents.llm import _get_openrouter_client, parse_llm_json

    if not getattr(settings, "OPENROUTER_API_KEY", ""):
        if content_safety_enabled():
            return _fail_closed_result("Moderation API unavailable (no API key)")
        return SafetyResult()

    client = _get_openrouter_client()
    prompt = (
        f"{_MODERATION_JSON_SCHEMA}\n\n"
        "Review this image ONLY for clear sexual nudity, pornography, sexually explicit "
        "poses meant to arouse, or overt sexual solicitation. "
        "Construction, architecture, work sites, street photography, catalog swimwear, "
        "and normal business product photos are safe. When uncertain, allow."
    )
    messages = [
        {"role": "system", "content": _MODERATION_SYSTEM},
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": image_url, "detail": "low"}},
                {"type": "text", "text": prompt},
            ],
        },
    ]

    last_exc = None
    for model in _moderation_models_to_try():
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=512,
                temperature=0,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content or "{}"
            return _parse_moderation_response(parse_llm_json(content))
        except Exception as exc:
            last_exc = exc
            err = str(exc).lower()
            if "404" in err or "no endpoints found" in err:
                logger.warning("Content safety model %s unavailable, trying fallback", model)
                continue
            logger.error("Content safety image moderation failed: %s", exc)
            break

    if last_exc:
        logger.error("Content safety image moderation failed: %s", last_exc)
        err = str(last_exc).lower()
        if content_safety_enabled() and (
            "404" in err or "no endpoints found" in err
        ):
            return SafetyResult(
                safe=True,
                api_failed=True,
                reasons=["Moderation skipped — vision model unavailable"],
            )
        if content_safety_enabled():
            return _fail_closed_result(f"Moderation API error: {last_exc}")
    return SafetyResult()


def encode_uploaded_file(uploaded_file) -> str:
    """Encode an uploaded image file as a base64 data URI."""
    if hasattr(uploaded_file, "read"):
        uploaded_file.seek(0)
        raw = uploaded_file.read()
        uploaded_file.seek(0)
    else:
        raw = uploaded_file

    content_type = getattr(uploaded_file, "content_type", "") or "image/jpeg"
    if content_type == "application/octet-stream":
        name = getattr(uploaded_file, "name", "") or ""
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else "jpg"
        mime_map = {
            "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
            "webp": "image/webp", "gif": "image/gif",
        }
        content_type = mime_map.get(ext, "image/jpeg")

    encoded = base64.b64encode(raw).decode("utf-8")
    return f"data:{content_type};base64,{encoded}"


def resolve_image_for_moderation(url_or_bytes, product=None) -> str | None:
    """Normalize a URL, bytes, file, or storage path into a moderation-ready image URL."""
    if isinstance(url_or_bytes, (bytes, bytearray)):
        encoded = base64.b64encode(url_or_bytes).decode("utf-8")
        return f"data:image/jpeg;base64,{encoded}"

    if hasattr(url_or_bytes, "read"):
        return encode_uploaded_file(url_or_bytes)

    url = str(url_or_bytes or "").strip()
    if not url:
        return None
    if url.startswith("http") or url.startswith("data:"):
        return url

    import base64 as b64mod

    try:
        from django.core.files.storage import default_storage

        if product and product.image and not url.startswith("/"):
            file_path = product.image.path
        else:
            file_path = default_storage.path(url.lstrip("/"))
        with open(file_path, "rb") as f:
            encoded = b64mod.b64encode(f.read()).decode("utf-8")
        ext = file_path.rsplit(".", 1)[-1].lower()
        mime = {
            "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
            "webp": "image/webp", "gif": "image/gif",
        }.get(ext, "image/jpeg")
        return f"data:{mime};base64,{encoded}"
    except Exception as exc:
        logger.warning("Could not resolve image for moderation: %s", exc)
        return None


def check_image_safe(url_or_bytes, user=None, *, product=None) -> SafetyResult:
    """Vision moderation via OpenRouter. Fail-closed when safety is enabled."""
    if content_safety_staff_paused():
        return SafetyResult(safe=True)
    if not content_safety_enabled():
        return SafetyResult()

    image_url = resolve_image_for_moderation(url_or_bytes, product=product)
    if not image_url:
        return _fail_closed_result("Could not load image for safety review")

    return _openrouter_moderate_image(image_url, user=user)


def check_text_safe(text, user=None) -> SafetyResult:
    """Text moderation — local blocklist plus OpenRouter when enabled."""
    if content_safety_staff_paused():
        return SafetyResult(safe=True)
    result = SafetyResult()
    result = _local_text_checks(text or "", result)
    if not result.safe:
        return result

    if not content_safety_enabled():
        return result

    api_result = _openrouter_moderate_text(text or "", user=user)
    return result.merge(api_result)


def check_content_safety(content_text, user=None) -> SafetyResult:
    """Backward-compatible alias used by publish_post."""
    return check_text_safe(content_text, user=user)


def _post_image_urls(post) -> list[str]:
    urls = list(post.media_urls or [])
    for slide in post.carousel_slides or []:
        slide_url = slide.get("image_url") if isinstance(slide, dict) else None
        if slide_url:
            urls.append(slide_url)
    return urls


def check_post_safe(post) -> SafetyResult:
    """Check caption and all attached images."""
    if content_safety_staff_paused():
        return SafetyResult(safe=True)
    result = check_text_safe(post.content_text, user=post.user)

    if not content_safety_enabled():
        return result

    for image_url in _post_image_urls(post):
        img_result = check_image_safe(image_url, user=post.user)
        result.merge(img_result)
        if is_sexual_policy_violation(result):
            break

    return result


def check_uploaded_images_safe(uploaded_files, user) -> SafetyResult:
    """Check all uploaded files before snap/product creation."""
    if content_safety_staff_paused():
        return SafetyResult(safe=True)
    if not content_safety_enabled():
        return SafetyResult()

    combined = SafetyResult()
    for uploaded in uploaded_files:
        data_uri = encode_uploaded_file(uploaded)
        result = check_image_safe(data_uri, user=user)
        combined.merge(result)
        if not combined.safe:
            break
    return combined


def check_product_images_safe(product, user, *, source: str = "snap") -> SafetyResult:
    """Check all images on a product (snap / batch flows)."""
    if content_safety_staff_paused():
        return SafetyResult(safe=True)
    if not content_safety_enabled():
        return SafetyResult()

    combined = SafetyResult()
    for image_url in product.all_image_urls:
        resolved = resolve_image_for_moderation(image_url, product=product)
        if not resolved:
            combined.merge(_fail_closed_result("Could not load product image"))
            continue
        result = check_image_safe(resolved, user=user)
        combined.merge(result)
        if not combined.safe:
            break
    return combined


def record_content_safety_incident(
    *,
    user,
    source: str,
    result: SafetyResult,
    image_url: str = "",
    post=None,
    action_taken: str = "",
) -> "ContentSafetyIncident":
    from apps.content.models import ContentSafetyIncident

    incident = ContentSafetyIncident.objects.create(
        user=user,
        post=post,
        source=source,
        image_url=(image_url or "")[:2000],
        reasons=result.reasons,
        categories=result.categories,
        severity=result.severity,
        action_taken=action_taken,
    )

    # Per-user snap block only — never auto-pause platform-wide publishing.
    apply_user_snap_block(user, incident, result)

    if is_sexual_policy_violation(result):
        notify_staff_content_safety_incident(incident)

    return incident


def notify_staff_content_safety_incident(incident) -> None:
    """Email staff/superusers on high-severity incidents."""
    import logging

    from django.conf import settings
    from django.core.mail import send_mail

    from apps.accounts.models import User

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None)
    if not from_email:
        return

    emails = list(
        User.objects.filter(is_superuser=True, is_active=True)
        .exclude(email="")
        .values_list("email", flat=True)[:10]
    )
    override = getattr(settings, "CONTENT_SAFETY_NOTIFY_EMAIL", "").strip()
    if override and override not in emails:
        emails.insert(0, override)

    if not emails:
        return

    subject = f"[Kova] Content safety incident — severity {incident.severity}"
    body_lines = [
        f"User: {incident.user.email}",
        f"Source: {incident.get_source_display()}",
        f"Severity: {incident.severity}",
        f"Categories: {', '.join(incident.categories or [])}",
        f"Reasons: {'; '.join(incident.reasons or [])}",
        "",
        f"Review: /dashboard/content-safety/review/{incident.pk}/",
    ]
    if incident.user_id:
        body_lines.append(
            f"User usage: /dashboard/users/{incident.user_id}/usage/"
        )

    try:
        send_mail(
            subject=subject,
            message="\n".join(body_lines),
            from_email=from_email,
            recipient_list=emails,
            fail_silently=True,
        )
    except Exception as exc:
        logging.getLogger(__name__).warning(
            "Content safety staff email failed: %s", exc,
        )

    try:
        from apps.notifications.models import Notification

        for staff in User.objects.filter(is_staff=True, is_active=True)[:20]:
            Notification.create_for_user(
                staff,
                "system",
                f"Content safety: {incident.user.email} — severity {incident.severity}",
            )
    except Exception:
        pass


def block_post_for_policy(post, result: SafetyResult, *, source: str = "publish") -> None:
    """Set post to blocked status — never reaches Meta."""
    from apps.content.models import Post
    from apps.notifications.models import Notification

    post.status = Post.Status.BLOCKED
    post.publish_error = POLICY_BLOCK_MESSAGE
    post.ai_reasoning = f"SAFETY BLOCKED ({source}): {result.summary}"[:2000]
    post.save(update_fields=["status", "publish_error", "ai_reasoning", "updated_at"])

    record_content_safety_incident(
        user=post.user,
        source=source,
        result=result,
        image_url=(_post_image_urls(post)[0] if _post_image_urls(post) else ""),
        post=post,
        action_taken="post_blocked",
    )

    profile = getattr(post.user, "profile", None)
    if profile and is_sexual_policy_violation(result):
        profile.content_safety_strike_count = (profile.content_safety_strike_count or 0) + 1
        profile.save(update_fields=["content_safety_strike_count"])

    Notification.create_for_user(
        post.user,
        "system",
        f"⚠️ {POLICY_BLOCK_MESSAGE} Open the post to review details.",
        related_post=post,
    )

    logger.warning(
        "SAFETY BLOCKED post %s (source=%s): %s",
        post.pk, source, result.summary,
    )
