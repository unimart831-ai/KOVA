"""
Encrypt existing OAuth tokens in-place.

This migration:
1. Reads existing plaintext access_token and refresh_token values
2. Encrypts them using Fernet (via apps.platforms.encryption)
3. Writes the encrypted values back to the same text column

The column type does NOT change (stays TEXT). EncryptedTokenField handles
transparent encrypt/decrypt at the application level.

Reversible: the reverse operation decrypts tokens back to plaintext.
"""

from django.db import migrations

from apps.platforms.encryption import EncryptedTokenField


def encrypt_existing_tokens(apps, schema_editor):
    """Encrypt all existing plaintext tokens using Fernet."""
    from apps.platforms.encryption import encrypt_token

    connection = schema_editor.connection
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, access_token, refresh_token FROM platforms_socialaccount"
        )
        for row in cursor.fetchall():
            pk, access, refresh = row
            new_access = encrypt_token(access) if access else access
            new_refresh = encrypt_token(refresh) if refresh else refresh
            if new_access != access or new_refresh != refresh:
                cursor.execute(
                    "UPDATE platforms_socialaccount "
                    "SET access_token = %s, refresh_token = %s "
                    "WHERE id = %s",
                    [new_access, new_refresh, pk],
                )


def decrypt_existing_tokens(apps, schema_editor):
    """Reverse: decrypt tokens back to plaintext."""
    from apps.platforms.encryption import decrypt_token

    connection = schema_editor.connection
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, access_token, refresh_token FROM platforms_socialaccount"
        )
        for row in cursor.fetchall():
            pk, access, refresh = row
            new_access = decrypt_token(access) if access else access
            new_refresh = decrypt_token(refresh) if refresh else refresh
            if new_access != access or new_refresh != refresh:
                cursor.execute(
                    "UPDATE platforms_socialaccount "
                    "SET access_token = %s, refresh_token = %s "
                    "WHERE id = %s",
                    [new_access, new_refresh, pk],
                )


class Migration(migrations.Migration):

    dependencies = [
        ("platforms", "0003_alter_socialaccount_platform"),
    ]

    operations = [
        # Step 1: Encrypt existing plaintext data (column is still TEXT)
        migrations.RunPython(
            encrypt_existing_tokens,
            decrypt_existing_tokens,
        ),
        # Step 2: Update Django's field state to EncryptedTokenField
        # (no column change — both are TEXT internally)
        migrations.AlterField(
            model_name="socialaccount",
            name="access_token",
            field=EncryptedTokenField(blank=True),
        ),
        migrations.AlterField(
            model_name="socialaccount",
            name="refresh_token",
            field=EncryptedTokenField(blank=True),
        ),
    ]
