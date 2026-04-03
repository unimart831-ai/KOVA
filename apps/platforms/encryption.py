"""
Application-level token encryption using Fernet symmetric encryption.

Uses the same HKDF key derivation as django-fernet-fields-v2 for consistency.
Keeps the database column as TEXT (no schema change), storing encrypted values
as base64-encoded Fernet tokens.

Empty/None values pass through without encryption, so DB-level filters
like `refresh_token__gt=""` continue to work correctly.
"""

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models
from fernet_fields.hkdf import derive_fernet_key


def _get_fernet():
    """Build a Fernet instance from the configured encryption key."""
    keys = getattr(settings, "FERNET_KEYS", [settings.SECRET_KEY])
    return Fernet(derive_fernet_key(keys[0]))


def encrypt_token(value):
    """Encrypt a token string. Empty/None values pass through unchanged."""
    if not value:
        return value
    return _get_fernet().encrypt(value.encode()).decode()


def decrypt_token(value):
    """Decrypt a Fernet token string. Returns plaintext for legacy unencrypted values."""
    if not value:
        return value
    try:
        return _get_fernet().decrypt(value.encode()).decode()
    except (InvalidToken, Exception):
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
