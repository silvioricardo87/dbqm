"""Encryption utilities for password storage."""
from __future__ import annotations

from pathlib import Path

from cryptography.fernet import Fernet

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
