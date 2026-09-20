"""`error_text`: a driver's first line, with the connection's password out.

Every `error` the CLI publishes is built from `str(e)` of whatever the
driver raised, and a driver is free to echo the DSN it was given. The
password is the one thing in there that is a secret by the project's own
standard (`connection show` prints the host, never the password), so it is
the one thing masked.
"""
from dbqm.core.crypto import encrypt
from dbqm.core.db_manager import error_text
from dbqm.models.connection import Connection


def _conn(password: str) -> Connection:
    return Connection(name="c", db_type="postgresql", host="db.example.com",
                      user="app", password=encrypt(password) if password else "")


class TestThePasswordNeverTravels:
    def test_a_password_echoed_by_the_driver_is_masked(self, tmp_config_dir):
        conn = _conn("s3cret-pw")
        e = RuntimeError('connection to "db.example.com" failed: password "s3cret-pw" rejected')
        text = error_text(e, conn)
        assert "s3cret-pw" not in text
        assert 'password "***" rejected' in text
        # The host is not a secret: `connection show` prints it too.
        assert "db.example.com" in text

    def test_every_occurrence_is_masked_not_only_the_first(self, tmp_config_dir):
        conn = _conn("s3cret-pw")
        e = RuntimeError("s3cret-pw ... dsn=postgresql://app:s3cret-pw@db/x")
        assert "s3cret-pw" not in error_text(e, conn)

    def test_a_message_without_the_password_is_untouched(self, tmp_config_dir):
        conn = _conn("s3cret-pw")
        e = RuntimeError("ORA-00942: table or view does not exist")
        assert error_text(e, conn) == "ORA-00942: table or view does not exist"


class TestWhatIsDeliberatelyNotMasked:
    def test_a_password_shorter_than_four_characters_is_left_alone(self, tmp_config_dir):
        """Replacing every "1" in "ORA-01017" would destroy the message that
        is supposed to help; a three-character password is not worth that."""
        conn = _conn("1")
        e = RuntimeError("ORA-01017: invalid username/password")
        assert error_text(e, conn) == "ORA-01017: invalid username/password"

    def test_no_connection_means_no_masking(self):
        e = RuntimeError("anything at all")
        assert error_text(e, None) == "anything at all"

    def test_a_connection_saved_without_a_password_is_fine(self, tmp_config_dir):
        assert error_text(RuntimeError("x"), _conn("")) == "x"

    def test_a_token_the_key_cannot_decrypt_does_not_hide_the_error(self, tmp_config_dir):
        """A key mismatch is its own failure, reported elsewhere; it must not
        turn every driver error into a crash inside the error path."""
        conn = Connection(name="c", db_type="postgresql", host="h", user="u",
                          password="gAAAAA-not-a-real-token")
        assert error_text(RuntimeError("driver said no"), conn) == "driver said no"


class TestOneLineCapped:
    def test_only_the_first_line_survives(self):
        e = RuntimeError("the failure\nTraceback (most recent call last):\n  ...")
        assert error_text(e) == "the failure"

    def test_the_limit_is_honoured(self):
        e = RuntimeError("x" * 900)
        assert len(error_text(e)) == 500
        assert len(error_text(e, limit=200)) == 200
