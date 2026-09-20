"""`dbqm group add --adhoc-sql`, and `run-group` on what it saves.

An ad-hoc group is what Multi-Exec saves: one statement and a set of
connections, no saved queries, no join key. Until now the CLI could
preserve one on `update` and could not create or run one. `local` and
`local2` share the seed except for one row of `orders` (13: 5.25 vs 6.0),
which is exactly the divergence a comparison exists to find.
"""
from tests.functional.conftest import envelope, invoke

MATCHING = "SELECT id, name FROM customers ORDER BY id"
DIVERGING = "SELECT id, value FROM orders ORDER BY id"


def _add(capsys, name="cmp", sql=MATCHING, *conns, extra=()):
    argv = ["group", "add", name, "--adhoc-sql", sql]
    for c in conns:
        argv += ["--connection", c]
    argv += list(extra)
    return envelope(argv + ["-f", "json"], capsys)


# ---------------------------------------------------------------------------
# Creating one
# ---------------------------------------------------------------------------

def test_it_is_saved_in_the_shape_multi_exec_saves(local2_db, capsys):
    code, body = _add(capsys, "cmp", MATCHING, "local", "local2")
    assert code == 0, body
    assert body["data"] == {"name": "cmp", "created": True}

    code, body = envelope(["group", "show", "cmp", "-f", "json"], capsys)
    assert code == 0
    data = body["data"]
    assert data["adhoc_sql"] == MATCHING
    assert data["connections"] == ["local", "local2"]
    # No queries and no key: the key is derived when it runs.
    assert data["queries"] == []
    assert data["join_key"] == ""


def test_fewer_than_two_connections_is_a_validation_error(local_db, capsys):
    code, body = _add(capsys, "cmp", MATCHING, "local")
    assert code == 2
    assert body["error"]["code"] == "validation"
    assert "at least 2" in body["error"]["message"]


def test_a_repeated_connection_is_named(local_db, capsys):
    """Same rule as `multi -c local -c local`: the results are keyed by
    connection name, and a repeat collapses to one side that can only ever
    agree with itself."""
    code, body = _add(capsys, "cmp", MATCHING, "local", "local")
    assert code == 2
    assert '"local" is repeated' in body["error"]["message"]


def test_an_unknown_connection_is_named(local_db, capsys):
    code, body = _add(capsys, "cmp", MATCHING, "local", "nowhere")
    assert code == 2
    assert 'Connection "nowhere" not found' in body["error"]["message"]


def test_adhoc_sql_wins_over_saved_query_fields_beside_it(local2_db, capsys):
    """A group file can carry both shapes -- `update`'s preservation
    guarantee is tested with exactly that -- so the mix is not refused:
    `adhoc_sql` decides, here and in `run-group`, and the saved-query
    fields ride along untouched."""
    code, body = _add(capsys, "cmp", MATCHING, "local", "local2",
                      extra=["--join-key", "id"])
    assert code == 0, body
    _, body = envelope(["group", "show", "cmp", "-f", "json"], capsys)
    assert body["data"]["adhoc_sql"] == MATCHING
    assert body["data"]["join_key"] == "id"
    code, body = envelope(["run-group", "cmp", "-f", "json"], capsys)
    assert code == 0, body
    assert body["data"]["join_key"] == "id"  # derived, and it agrees


def test_update_keeps_the_ad_hoc_fields_it_is_not_told_about(local2_db, capsys):
    _add(capsys, "cmp", MATCHING, "local", "local2")
    code, body = envelope(["group", "update", "cmp", "--description", "note",
                           "-f", "json"], capsys)
    assert code == 0, body
    _, body = envelope(["group", "show", "cmp", "-f", "json"], capsys)
    assert body["data"]["description"] == "note"
    assert body["data"]["adhoc_sql"] == MATCHING
    assert body["data"]["connections"] == ["local", "local2"]


# ---------------------------------------------------------------------------
# Running one
# ---------------------------------------------------------------------------

def test_run_group_runs_it_and_reports_the_derived_key(local2_db, capsys):
    _add(capsys, "cmp", MATCHING, "local", "local2")
    code, body = envelope(["run-group", "cmp", "-f", "json"], capsys)
    assert code == 0, body
    data = body["data"]
    assert data["group"] == "cmp"
    assert data["all_match"] is True
    # Derived, and therefore reported -- a key chosen by a rule the caller
    # cannot see would turn every count below into a guess.
    assert data["join_key"] == "id"
    assert [c["column"] for c in data["comparisons"]] == ["name"]


def test_a_divergence_exits_five_like_every_other_comparison(local2_db, capsys):
    _add(capsys, "cmp", DIVERGING, "local", "local2")
    code, body = envelope(["run-group", "cmp", "-f", "json"], capsys)
    assert code == 5
    assert body["ok"] is True  # the command did its job; the answer is "no"
    assert body["data"]["all_match"] is False
    [comparison] = body["data"]["comparisons"]
    assert comparison["column"] == "value"
    assert comparison["diff_count"] == 1


def test_the_table_output_names_the_group_not_the_connections(local2_db, capsys):
    _add(capsys, "cmp", MATCHING, "local", "local2")
    code, out, _ = invoke(["run-group", "cmp"], capsys)
    assert code == 0
    assert "cmp" in out


def test_a_connection_that_stopped_existing_is_not_found(local2_db, capsys):
    _add(capsys, "cmp", MATCHING, "local", "local2")
    invoke(["connection", "rm", "local2", "--yes"], capsys)
    code, body = envelope(["run-group", "cmp", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "not_found"
    assert "local2" in body["error"]["message"]


def test_it_is_recorded_in_history_under_the_group_name(local2_db, capsys):
    _add(capsys, "cmp", MATCHING, "local", "local2")
    envelope(["run-group", "cmp", "-f", "json"], capsys)
    code, body = envelope(["history", "-f", "json"], capsys)
    assert code == 0
    groups = [e for e in body["data"] if e["entry_type"] == "group"]
    assert [e["name"] for e in groups] == ["cmp"]
