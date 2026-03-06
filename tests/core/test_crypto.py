"""Tests for encryption utilities."""
import pytest
from dbqm.core.crypto import (
    encrypt, decrypt, encrypt_with_password, decrypt_with_password,
    generate_salt, _derive_key_from_password,
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
        with pytest.raises(Exception):
            decrypt_with_password(token, "wrong", salt)

    def test_different_salt_fails(self):
        salt1 = generate_salt()
        salt2 = generate_salt()
        token = encrypt_with_password("secret", "pw", salt1)
        with pytest.raises(Exception):
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
