"""Tests for encryption utilities."""
import pytest
from dbqm.core.crypto import (
    encrypt, decrypt, encrypt_with_password, decrypt_with_password,
    generate_salt, _derive_key_from_password, InvalidToken,
)


class TestPasswordBasedCrypto:
    def test_encrypt_decrypt_round_trip(self):
        salt = generate_salt()
        token = encrypt_with_password("secret123", "mypassword", salt)
        plain = decrypt_with_password(token, "mypassword", salt)
        assert plain == "secret123"

    def test_wrong_password_fails(self):
        salt = generate_salt()
        token = encrypt_with_password("secret", "correct", salt)
        with pytest.raises(InvalidToken):
            decrypt_with_password(token, "wrong", salt)

    def test_different_salt_fails(self):
        salt1 = generate_salt()
        salt2 = generate_salt()
        token = encrypt_with_password("secret", "pw", salt1)
        with pytest.raises(InvalidToken):
            decrypt_with_password(token, "pw", salt2)

    def test_generate_salt_unique(self):
        s1 = generate_salt()
        s2 = generate_salt()
        assert s1 != s2
        assert len(s1) == 16

    def test_derive_key_deterministic(self):
        salt = b"fixed_salt_16byt"
        k1 = _derive_key_from_password("pw", salt)
        k2 = _derive_key_from_password("pw", salt)
        assert k1 == k2

    def test_derive_key_different_passwords(self):
        salt = b"fixed_salt_16byt"
        k1 = _derive_key_from_password("pw1", salt)
        k2 = _derive_key_from_password("pw2", salt)
        assert k1 != k2


class TestMasterKeyCrypto:
    def test_encrypt_decrypt(self, tmp_path, monkeypatch):
        key_file = tmp_path / ".dbqm_key"
        monkeypatch.setattr("dbqm.core.crypto.KEY_FILE", key_file)

        token = encrypt("hello world")
        assert token != "hello world"
        assert decrypt(token) == "hello world"

    def test_decrypt_of_empty_token_means_no_password(self, tmp_path, monkeypatch):
        """A connection saved with --no-password stores "" — not a failure.

        Fernet raises InvalidToken on "", whose str() is empty, which reached
        the user as "Erro ao conectar:" followed by nothing.
        """
        monkeypatch.setattr("dbqm.core.crypto.KEY_FILE", tmp_path / ".dbqm_key")
        assert decrypt("") == ""

    def test_decrypt_of_a_corrupt_token_says_what_is_wrong(self, tmp_path, monkeypatch):
        """The other half: an error the user can act on."""
        import pytest

        monkeypatch.setattr("dbqm.core.crypto.KEY_FILE", tmp_path / ".dbqm_key")
        with pytest.raises(ValueError) as exc:
            decrypt("not-a-fernet-token")
        message = str(exc.value)
        assert message, "the error must not be empty, which was the whole bug"
        assert ".dbqm_key" in message
        assert "--password-stdin" in message

    def test_key_created_on_first_use(self, tmp_path, monkeypatch):
        key_file = tmp_path / ".dbqm_key"
        monkeypatch.setattr("dbqm.core.crypto.KEY_FILE", key_file)
        assert not key_file.exists()
        encrypt("test")
        assert key_file.exists()

    def test_key_reused(self, tmp_path, monkeypatch):
        key_file = tmp_path / ".dbqm_key"
        monkeypatch.setattr("dbqm.core.crypto.KEY_FILE", key_file)
        t1 = encrypt("a")
        key_content = key_file.read_bytes()
        t2 = encrypt("b")
        assert key_file.read_bytes() == key_content  # same key


def test_credentials_work_without_cryptography_installed(tmp_path):
    """Native Windows ARM must not need the unavailable cryptography wheel."""
    import os
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-c", """
import sys
sys.modules['cryptography'] = None
from dbqm.core.crypto import encrypt, decrypt, generate_salt
from dbqm.core.crypto import encrypt_with_password, decrypt_with_password
assert decrypt(encrypt('senha ç 🔑')) == 'senha ç 🔑'
salt = generate_salt()
assert decrypt_with_password(encrypt_with_password('', 'pw', salt), 'pw', salt) == ''
"""],
        env={**os.environ, "DBQM_HOME": str(tmp_path)},
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr


# Published test vectors: https://github.com/fernet/spec (generate.json, invalid.json).
FERNET_KEY = b'cw_0x689RpI-jtRR7oE8h_eQsKImvJapLeSbXpwF4e4='
FERNET_TOKEN = 'gAAAAAAdwJ6wAAECAwQFBgcICQoLDA0ODy021cpGVWKZ_eEwCGM4BLLF_5CV9dOPmrhuVUPgJobwOz7JcbmrR64jVmpU4IwqDA=='


def test_published_fernet_vector_reads_existing_credentials(tmp_path, monkeypatch):
    key_file = tmp_path / ".dbqm_key"
    key_file.write_bytes(FERNET_KEY)
    monkeypatch.setattr("dbqm.core.crypto.KEY_FILE", key_file)
    assert decrypt(FERNET_TOKEN) == "hello"


def test_published_fernet_vector_is_written_identically(tmp_path, monkeypatch):
    from datetime import datetime

    key_file = tmp_path / ".dbqm_key"
    key_file.write_bytes(FERNET_KEY)
    monkeypatch.setattr("dbqm.core.crypto.KEY_FILE", key_file)
    monkeypatch.setattr("dbqm.core.crypto.time.time", lambda: datetime.fromisoformat("1985-10-26T01:20:00-07:00").timestamp())
    monkeypatch.setattr("dbqm.core.crypto.os.urandom", lambda size: bytes(range(size)))
    assert encrypt("hello") == FERNET_TOKEN


@pytest.mark.parametrize("token", ['gAAAAAAdwJ6xAAECAwQFBgcICQoLDA0OD3HkMATM5lFqGaerZ-fWPAl1-szkFVzXTuGb4hR8AKtwcaX1YdykQUFBQUFBQUFBQQ==', 'gAAAAAAdwJ6xAAECAwQFBgcICQoLDA0OD3HkMATM5lFqGaerZ-fWPA==', '%%%%%%%%%%%%%AECAwQFBgcICQoLDA0OD3HkMATM5lFqGaerZ-fWPAl1-szkFVzXTuGb4hR8AKtwcaX1YdykRtfsH-p1YsUD2Q==', 'gAAAAAAdwJ6xAAECAwQFBgcICQoLDA0OD3HkMATM5lFqGaerZ-fWPOm73QeoCk9uGib28Xe5vz6oxq5nmxbx_v7mrfyudzUm', 'gAAAAAAdwJ6xAAECAwQFBgcICQoLDA0ODz4LEpdELGQAad7aNEHbf-JkLPIpuiYRLQ3RtXatOYREu2FWke6CnJNYIbkuKNqOhw==', 'gAAAAAAdwJ6xBQECAwQFBgcICQoLDA0OD3HkMATM5lFqGaerZ-fWPAkLhFLHpGtDBRLRTZeUfWgHSv49TF2AUEZ1TIvcZjK1zQ=='])
def test_published_invalid_fernet_vectors_are_rejected(token, tmp_path, monkeypatch):
    key_file = tmp_path / ".dbqm_key"
    key_file.write_bytes(FERNET_KEY)
    monkeypatch.setattr("dbqm.core.crypto.KEY_FILE", key_file)
    with pytest.raises(ValueError):
        decrypt(token)


@pytest.mark.parametrize("text", ["", "senha ç 🔑", "a" * 16, "a" * 17, "x" * 4096])
def test_fernet_implementations_read_each_others_credentials(text, tmp_path, monkeypatch):
    reference = pytest.importorskip("cryptography.fernet")
    key_file = tmp_path / ".dbqm_key"
    key_file.write_bytes(FERNET_KEY)
    monkeypatch.setattr("dbqm.core.crypto.KEY_FILE", key_file)
    legacy = reference.Fernet(FERNET_KEY)
    assert decrypt(legacy.encrypt(text.encode()).decode()) == text
    assert legacy.decrypt(encrypt(text).encode()).decode() == text


def test_password_bundles_are_compatible_in_both_directions():
    reference = pytest.importorskip("cryptography.fernet")
    kdf = pytest.importorskip("cryptography.hazmat.primitives.kdf.pbkdf2")
    hashes = pytest.importorskip("cryptography.hazmat.primitives.hashes")
    salt = b"0123456789abcdef"
    password = "senha ç 🔑"
    import base64

    key = base64.urlsafe_b64encode(kdf.PBKDF2HMAC(
        algorithm=hashes.SHA256(), length=32, salt=salt, iterations=480_000,
    ).derive(password.encode()))
    legacy = reference.Fernet(key)
    token = legacy.encrypt(b"configuration bundle").decode()
    assert decrypt_with_password(token, password, salt) == "configuration bundle"
    assert legacy.decrypt(encrypt_with_password("bundle", password, salt).encode()) == b"bundle"


@pytest.mark.parametrize("position", [0, 1, 9, 25, -1])
def test_any_modified_authenticated_field_is_rejected(position, tmp_path, monkeypatch):
    import base64

    key_file = tmp_path / ".dbqm_key"
    key_file.write_bytes(FERNET_KEY)
    monkeypatch.setattr("dbqm.core.crypto.KEY_FILE", key_file)
    data = bytearray(base64.urlsafe_b64decode(FERNET_TOKEN))
    data[position] ^= 1
    with pytest.raises(ValueError):
        decrypt(base64.urlsafe_b64encode(data).decode())


@pytest.mark.parametrize("token", ["", "!", "a", "🔑", "g" * 100])
def test_malformed_password_bundle_raises_invalid_token(token):
    with pytest.raises(InvalidToken):
        decrypt_with_password(token, "password", b"0123456789abcdef")
