"""Encryption utilities for password storage."""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import os
import struct
import time

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

from dbqm.i18n import t
from dbqm.core.paths import KEY_FILE


def _get_or_create_key() -> bytes:
    if KEY_FILE.exists():
        return KEY_FILE.read_bytes()
    key = base64.urlsafe_b64encode(os.urandom(32))
    KEY_FILE.write_bytes(key)
    # Restrict file permissions to owner only (best-effort on Windows)
    try:
        KEY_FILE.chmod(0o600)
    except OSError:
        pass
    return key


def encrypt(text: str) -> str:
    return _encrypt_token(text, _get_or_create_key())


def decrypt(token: str) -> str:
    """Plaintext for a stored token. An empty token means "no password".

    `Connection.password` is `""` for a connection deliberately saved without
    one (`--no-password`, or a blank field on a new connection). Fernet raises
    `InvalidToken` on `""`, and `str(InvalidToken())` is the empty string — so
    the user met `Erro ao conectar:` with nothing after the colon, an error
    carrying no information at all.

    A non-empty token that will not decrypt is a different failure: the key
    file no longer matches the stored password. That one says so.
    """
    if not token:
        return ""
    key = _get_or_create_key()
    try:
        return _decrypt_token(token, key)
    except InvalidToken as e:
        raise ValueError(
            t("crypto.password_unreadable")
        ) from e


def _derive_key_from_password(password: str, salt: bytes) -> bytes:
    """Derive a Fernet key from a user password using PBKDF2."""
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 480_000, dklen=32)
    return base64.urlsafe_b64encode(key)


def generate_salt() -> bytes:
    return os.urandom(16)


def encrypt_with_password(text: str, password: str, salt: bytes) -> str:
    key = _derive_key_from_password(password, salt)
    return _encrypt_token(text, key)


def decrypt_with_password(token: str, password: str, salt: bytes) -> str:
    key = _derive_key_from_password(password, salt)
    return _decrypt_token(token, key)


class InvalidToken(ValueError):
    """A Fernet token could not be authenticated or decoded."""


def _decode_key(key: bytes) -> bytes:
    raw = base64.urlsafe_b64decode(key)
    if len(raw) != 32:
        raise ValueError(t("crypto.invalid_key"))
    return raw


def _encrypt_token(text: str, key: bytes) -> str:
    """Encode the standard Fernet wire format, readable by older dbqm releases."""
    raw_key = _decode_key(key)
    iv = os.urandom(16)
    cipher = AES.new(raw_key[16:], AES.MODE_CBC, iv=iv)
    body = b"\x80" + struct.pack(">Q", int(time.time())) + iv
    body += cipher.encrypt(pad(text.encode(), AES.block_size))
    signature = hmac.digest(raw_key[:16], body, "sha256")
    return base64.urlsafe_b64encode(body + signature).decode()


def _decrypt_token(token: str, key: bytes) -> str:
    raw_key = _decode_key(key)
    try:
        data = base64.urlsafe_b64decode(token.encode())
        # version + timestamp + IV + at least one AES block + HMAC
        if len(data) < 73 or data[0] != 0x80 or (len(data) - 57) % 16:
            raise InvalidToken
        body, signature = data[:-32], data[-32:]
        expected = hmac.digest(raw_key[:16], body, "sha256")
        if not hmac.compare_digest(signature, expected):
            raise InvalidToken
        # Authenticate before decryption or padding validation.
        cipher = AES.new(raw_key[16:], AES.MODE_CBC, iv=data[9:25])
        return unpad(cipher.decrypt(data[25:-32]), AES.block_size).decode()
    except (ValueError, binascii.Error) as exc:
        raise InvalidToken from exc
