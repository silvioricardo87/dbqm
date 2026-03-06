"""Tests for connection model."""
from dbqm.models.connection import Connection, load_connections, save_connections, find_connection, delete_connection


class TestConnection:
    def test_to_dict_oracle_tns(self):
        c = Connection(name="ora", db_type="oracle", user="u", password="p", mode="tns", tns_path="/path", tns_name="MYDB")
        d = c.to_dict()
        assert d["name"] == "ora"
        assert d["db_type"] == "oracle"
        assert d["mode"] == "tns"
        assert d["windows_auth"] is False  # bool default kept (not None)

    def test_to_dict_excludes_none(self):
        c = Connection(name="t", db_type="sqlserver", user="u", password="p", host="h")
        d = c.to_dict()
        assert "tns_path" not in d
        assert "service_name" not in d

    def test_from_dict_ignores_unknown_fields(self):
        c = Connection.from_dict({"name": "t", "db_type": "oracle", "user": "u", "password": "p", "unknown_field": "x"})
        assert c.name == "t"

    def test_from_dict_round_trip(self):
        c = Connection(name="t", db_type="sqlserver", user="u", password="p", host="h", port=1433, database="db")
        c2 = Connection.from_dict(c.to_dict())
        assert c2.name == c.name
        assert c2.host == c.host
        assert c2.database == c.database

    def test_display_target_oracle_tns(self):
        c = Connection(name="t", db_type="oracle", user="u", password="p", mode="tns", tns_name="MYDB")
        assert c.display_target() == "MYDB"

    def test_display_target_oracle_direct(self):
        c = Connection(name="t", db_type="oracle", user="u", password="p", mode="direct", host="h", port=1521, service_name="svc")
        assert c.display_target() == "h:1521/svc"

    def test_display_target_sqlserver(self):
        c = Connection(name="t", db_type="sqlserver", user="u", password="p", host="srv", port=1433, database="db")
        assert c.display_target() == "srv:1433/db"

    def test_display_target_postgresql(self):
        c = Connection(name="t", db_type="postgresql", user="u", password="p", host="pg", port=5432, database="mydb")
        assert c.display_target() == "pg:5432/mydb"

    def test_display_target_mysql(self):
        c = Connection(name="t", db_type="mysql", user="u", password="p", host="my", port=3306, database="app")
        assert c.display_target() == "my:3306/app"


class TestConnectionPersistence:
    def test_save_and_load(self, tmp_config_dir):
        conns = [Connection(name="c1", db_type="oracle", user="u", password="p")]
        save_connections(conns)
        loaded = load_connections()
        assert len(loaded) == 1
        assert loaded[0].name == "c1"

    def test_load_empty(self, tmp_config_dir):
        assert load_connections() == []

    def test_find_connection(self, tmp_config_dir):
        save_connections([
            Connection(name="a", db_type="oracle", user="u", password="p"),
            Connection(name="b", db_type="sqlserver", user="u", password="p"),
        ])
        assert find_connection("a").db_type == "oracle"
        assert find_connection("b").db_type == "sqlserver"
        assert find_connection("c") is None

    def test_delete_connection(self, tmp_config_dir):
        save_connections([Connection(name="x", db_type="oracle", user="u", password="p")])
        assert delete_connection("x") is True
        assert load_connections() == []
        assert delete_connection("x") is False
