"""Encryption utilities for password storage."""
from __future__ import annotations

import base64
import os
from pathlib import Path

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

KEY_FILE = Path(__file__).resolve().parent.parent.parent / ".dbqm_key"


def _get_or_create_key() -> bytes:
    if KEY_FILE.exists():
        return KEY_FILE.read_bytes()
    key = Fernet.generate_key()
    KEY_FILE.write_bytes(key)
    return key


def encrypt(text: str) -> str:
    f = Fernet(_get_or_create_key())
    return f.encrypt(text.encode()).decode()


def decrypt(token: str) -> str:
    f = Fernet(_get_or_create_key())
    return f.decrypt(token.encode()).decode()


def _derive_key_from_password(password: str, salt: bytes) -> bytes:
    """Derive a Fernet key from a user password using PBKDF2."""
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=480_000)
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))


def generate_salt() -> bytes:
    return os.urandom(16)


def encrypt_with_password(text: str, password: str, salt: bytes) -> str:
    key = _derive_key_from_password(password, salt)
    return Fernet(key).encrypt(text.encode()).decode()


def decrypt_with_password(token: str, password: str, salt: bytes) -> str:
    key = _derive_key_from_password(password, salt)
    return Fernet(key).decrypt(token.encode()).decode()
