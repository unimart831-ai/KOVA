"""
Human-feeling greeting helpers.

We never want to greet a user as "there" or "Hey there" — the User model
stores names in `full_name` (not Django's default first_name), and many
users fill in a company name instead. This module resolves the right way
to address them.
"""
from __future__ import annotations

import re


# Words to strip from the start of a full_name when extracting first name
_HONORIFICS = {"mr", "mrs", "ms", "miss", "dr", "prof", "sir", "madam"}


def first_name_of(user) -> str:
    """
    Extract a usable first name from a user.

    Resolution order:
      1. user.first_name (Django AbstractUser field — set if signup form filled it)
      2. First word of user.full_name with honorifics stripped
      3. Empty string (caller decides fallback)

    Examples:
      "Iranzi Innocent"      -> "Iranzi"
      "Dr. Marie Uwimana"    -> "Marie"
      "Mr Joseph"            -> "Joseph"
      "iranzi297@gmail.com"  -> ""  (handle in greeting_name)
    """
    if user is None:
        return ""

    explicit = (getattr(user, "first_name", "") or "").strip()
    if explicit:
        return explicit

    full = (getattr(user, "full_name", "") or "").strip()
    if not full:
        return ""

    parts = [p for p in re.split(r"\s+", full) if p]
    # Skip honorifics
    while parts and parts[0].strip(".").lower() in _HONORIFICS:
        parts.pop(0)
    return parts[0] if parts else ""


def greeting_name(user) -> str:
    """
    The name to greet this user with. Never returns "there" or "" — always
    something specific.

    Resolution order:
      1. First name (from first_name_of)
      2. Company name from profile.company_name (some founders prefer brand voice)
      3. Email handle before the @ (e.g. iranzi297 from iranzi297@gmail.com)
      4. Hardcoded "friend" — last-ditch fallback (should be unreachable in
         normal flows since email is required for accounts)

    Use this anywhere user-facing copy needs to address the user by name.
    """
    fn = first_name_of(user)
    if fn:
        return fn

    profile = getattr(user, "profile", None)
    company = (getattr(profile, "company_name", "") or "").strip()
    if company:
        return company

    email = (getattr(user, "email", "") or "").strip()
    if "@" in email:
        handle = email.split("@", 1)[0]
        # Clean common email noise: dots/underscores/digits at the end
        handle = re.sub(r"[._-]+", " ", handle).strip()
        handle = re.sub(r"\d+$", "", handle).strip()
        if handle:
            # Title-case so the greeting feels like a name, not a username
            return handle.split()[0].title()

    return "friend"


def business_or_name(user) -> str:
    """
    For copy where the brand name reads more naturally than a personal name
    (e.g., 'Briquettes Co's website is live' rather than 'Iranzi's website').
    Falls back to greeting_name when no company is set.
    """
    profile = getattr(user, "profile", None)
    company = (getattr(profile, "company_name", "") or "").strip()
    if company:
        return company
    return greeting_name(user)
