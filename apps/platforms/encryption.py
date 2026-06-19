"""
Application-level token encryption using Fernet symmetric encryption.

Uses the same HKDF key derivation as django-fernet-fields-v2 for consistency.
Keeps the database column as TEXT (no schema change), storing encrypted values
as base64-encoded Fernet tokens.

Empty/None values pass through without encryption, so DB-level filters
like `refresh_token__gt=""` continue to work correctly.

Multi-key decryption: Railway may run web/worker as separate services with
subtly different env resolution. To handle tokens encrypted by any process,
we collect all plausible keys and try each during decryption.
"""

import hashlib
import logging
import os

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models
from fernet_fields.hkdf import derive_fernet_key

logger = logging.getLogger(__name__)

_primary_fernet = None
_all_fernets = None  # list of (Fernet, key_hash) tuples


def _build_fernets():
    """Build Fernet instances for all plausible encryption keys.

    Railway runs web and worker as SEPARATE services that may resolve
    SECRET_KEY differently (each gets a unique value unless explicitly
    shared).  We collect keys from every source — including an explicit
    FERNET_EXTRA_KEYS env var — so decryption succeeds regardless of
    which process originally encrypted the value.
    """
    global _primary_fernet, _all_fernets

    seen_raw = set()
    raw_keys = []

    def _add(key, source):
        if key and key not in seen_raw:
            seen_raw.add(key)
            raw_keys.append((key, source))

    # 1. FERNET_KEYS from Django settings (primary — used for encryption)
    for k in getattr(settings, "FERNET_KEYS", []):
        _add(k, "settings.FERNET_KEYS")

    # 2. SECRET_KEY from Django settings
    _add(getattr(settings, "SECRET_KEY", ""), "settings.SECRET_KEY")

    # 3. Direct env reads (bypasses django-environ caching)
    _add(os.environ.get("FIELD_ENCRYPTION_KEY", ""), "env.FIELD_ENCRYPTION_KEY")
    _add(os.environ.get("SECRET_KEY", ""), "env.SECRET_KEY")

    # 4. FERNET_EXTRA_KEYS: comma-separated list of additional raw keys.
    #    Use this to add the OTHER service's SECRET_KEY so tokens
    #    encrypted by web can be decrypted by worker and vice-versa.
    extra = os.environ.get("FERNET_EXTRA_KEYS", "")
    for i, k in enumerate(extra.split(","), 1):
        k = k.strip()
        _add(k, f"env.FERNET_EXTRA_KEYS[{i}]")

    instances = []
    for raw_key, source in raw_keys:
        derived = derive_fernet_key(raw_key)
        key_hash = hashlib.sha256(
            derived if isinstance(derived, bytes) else derived.encode()
        ).hexdigest()[:12]
        raw_hash = hashlib.sha256(raw_key.encode()).hexdigest()[:12]
        instances.append((Fernet(derived), key_hash, source, raw_hash))

    _all_fernets = instances
    _primary_fernet = instances[0] if instances else None

    summary = [(h, s, rh) for _, h, s, rh in instances]
    logger.info(
        "Fernet initialised: %d key(s) %s — primary=%s",
        len(instances),
        summary,
        instances[0][1] if instances else "NONE",
    )
    return instances


def _get_primary():
    """Return the primary Fernet instance (for encryption)."""
    if _primary_fernet is None:
        _build_fernets()
    return _primary_fernet[0]


def _get_all():
    """Return all Fernet instances (for multi-key decryption)."""
    if _all_fernets is None:
        _build_fernets()
    return _all_fernets


def encrypt_token(value):
    """Encrypt a token string. Empty/None values pass through unchanged."""
    if not value:
        return value
    return _get_primary().encrypt(value.encode()).decode()


def decrypt_token(value):
    """Decrypt a Fernet token string. Tries all known keys.

    Returns plaintext on success, or the original value if no key works
    (handles legacy unencrypted values).
    """
    if not value:
        return value

    instances = _get_all()
    for fernet, key_hash, source, raw_hash in instances:
        try:
            return fernet.decrypt(value.encode()).decode()
        except InvalidToken:
            continue
        except Exception:
            continue

    # All keys exhausted
    if value.startswith("gAAAAA"):
        hashes = [h for _, h, _, _ in instances]
        logger.error(
            "ALL %d Fernet keys failed to decrypt (len=%d, prefix=%s, keys=%s). "
            "Token is unrecoverable — user must reconnect the platform.",
            len(instances), len(value), value[:10], hashes,
        )
    return value


class EncryptedTokenField(models.TextField):
    """TextField that transparently encrypts/decrypts using Fernet.

    - Column type stays TEXT (no schema migration risk).
    - Empty strings are stored as empty strings (preserves DB-level filters).
    - Non-empty values are stored as Fernet tokens (base64 strings).
    """

    def from_db_value(self, value, expression, connection):
        return decrypt_token(value)

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        return encrypt_token(value)
