"""Encryption for OAuth tokens at rest, and hashing for opaque tokens.

Protects a leaked pg_dump or a backup copied somewhere careless. Does NOT
protect against an attacker who can read .env — see docs/09-security-ops.md §29,
which states that boundary rather than overclaiming.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

from cryptography.fernet import Fernet, InvalidToken

from packages.core.config import settings

_fernet = Fernet(settings.token_encryption_key.encode())


def encrypt(plaintext: str) -> bytes:
    """Encrypt a secret for storage in a bytea column."""
    return _fernet.encrypt(plaintext.encode())


def decrypt(ciphertext: bytes) -> str:
    """Decrypt a stored secret.

    Raises InvalidToken if TOKEN_ENCRYPTION_KEY changed — which means the value
    is unrecoverable and the user must re-authorise. Fail loudly.
    """
    try:
        return _fernet.decrypt(bytes(ciphertext)).decode()
    except InvalidToken as exc:
        raise InvalidToken(
            "Could not decrypt. TOKEN_ENCRYPTION_KEY has changed or the value is "
            "corrupt. Affected OAuth connections must be re-authorised."
        ) from exc


def new_token(nbytes: int = 32) -> str:
    """Generate an opaque token — sessions, portal links, API keys."""
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    """Hash a token for storage. Raw tokens are never persisted."""
    return hashlib.sha256(token.encode()).hexdigest()


def verify_token(token: str, stored_hash: str) -> bool:
    """Constant-time comparison — never use == on secrets."""
    return hmac.compare_digest(hash_token(token), stored_hash)
