"""Phone normalization for signup / onboarding."""

import re


def normalize_phone(raw: str) -> str:
    """Strip formatting; return digits with optional leading +."""
    if not raw:
        return ""
    raw = raw.strip()
    if raw.startswith("+"):
        digits = re.sub(r"\D", "", raw[1:])
        return f"+{digits}" if digits else ""
    return re.sub(r"[\s\-]", "", raw)


def is_valid_phone(phone: str) -> bool:
    if not phone:
        return True
    if phone.startswith("+"):
        digits = phone[1:]
        return digits.isdigit() and 8 <= len(digits) <= 15
    # Kenyan local 10-digit
    if re.match(r"^0[127]\d{8}$", phone):
        return True
    # Generic international digits
    return phone.isdigit() and 8 <= len(phone) <= 15


def phone_to_whatsapp_digits(raw: str) -> str:
    """Convert stored phone to bare E.164 digits for Meta WhatsApp API (no +)."""
    phone = normalize_phone(raw)
    if not phone:
        return ""
    if phone.startswith("+"):
        digits = phone[1:]
        return digits if digits.isdigit() else ""
    if phone.startswith("0") and len(phone) == 10:
        return "254" + phone[1:]
    return phone if phone.isdigit() else ""


def user_has_phone(user) -> bool:
    return bool((getattr(user, "phone_number", "") or "").strip())


def user_needs_phone(user) -> bool:
    return not user_has_phone(user)


def apply_phone_to_user(user, phone: str):
    """Set timezone/country hints from phone when appropriate."""
    profile = getattr(user, "profile", None)
    if not phone:
        return
    user.phone_number = phone
    update_fields = ["phone_number"]
    if phone.startswith("0") and len(phone) == 10:
        user.timezone = "Africa/Nairobi"
        update_fields.append("timezone")
        if profile is not None:
            profile.mpesa_phone = phone
            profile.country = profile.country or "KE"
            profile.save(update_fields=["mpesa_phone", "country"])
    elif phone.startswith("+"):
        if profile is not None and not profile.mpesa_phone:
            profile.mpesa_phone = phone.lstrip("+")
            profile.save(update_fields=["mpesa_phone"])
    user.save(update_fields=update_fields)
