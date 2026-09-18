# CLI reference

Every dbqm operation is available non-interactively — no prompts, no TTY
required — which is what makes it usable from a script, from CI, or from an
AI agent. This is the full surface; the README carries only the handful of
commands worth seeing first.

The authoritative list is the program itself: `dbqm describe-cli -f json`
walks the same parser the CLI dispatches through and reports every command,
subcommand and flag. Nothing here is written down twice.

[← Back to the README](../README.md)

---

## Commands

```bash
# Show version
dbqm --version

# Execute a saved query (parameters are -p CHAVE=VALOR, repeat for each one)
dbqm run <query-name> -p data_inicio=2026-01-01 -p situacao=PAGO

# Execute a query group (parameters are shared by every query in it)
dbqm run-group <group-name> -p data_inicio=2026-01-01

# Run one ad-hoc SQL across several connections and compare the results
# (at least two -c/--connection; --key overrides the join column)
dbqm multi "SELECT * FROM table" -c prod -c homolog
dbqm multi "SELECT * FROM table" -c prod -c homolog -c staging --key id

# Execute ad-hoc SQL (SELECT/CTE, DML with --commit, DDL, PL/SQL anonymous blocks with DBMS_OUTPUT)
dbqm sql "SELECT * FROM table" <connection>
dbqm sql "WITH x AS (SELECT 1 FROM dual) SELECT * FROM x" <connection>

# Show execution plan (Oracle: EXPLAIN PLAN + DBMS_XPLAN.DISPLAY; PostgreSQL/MySQL: native EXPLAIN)
dbqm sql "SELECT * FROM table WHERE col = :v" <connection> --explain -p v=42

# Call a stored procedure or function (Oracle only). A name with a dot is
# PACOTE.ROTINA; a bare name is a standalone routine. Parameters bind by
# name, case-insensitively. Without --commit the run is rolled back.
dbqm call PACOTE.ROTINA <connection> -p p_id=7
dbqm call ROTINA_AVULSA <connection> -p p_id=7 --commit

# Curate a saved query (SQL from --sql or --sql-file; --connection must exist)
dbqm query add faturas-pagas --sql "SELECT * FROM faturas WHERE situacao = :situacao" \
    --connection prod --description "Faturas pagas"
dbqm query update faturas-pagas --folder financeiro
dbqm query show faturas-pagas -f json
dbqm query list --connection prod -f json
dbqm query rm faturas-pagas --yes

# Curate a comparison group (at least two DISTINCT --query, every one must
# exist). --compare-column is optional: with none, run-group compares every
# column the results have in common and reports which ones it picked.
dbqm group add prod-vs-homolog --query faturas-pagas --query faturas-pagas-homolog \
    --join-key id --compare-column valor
dbqm group update prod-vs-homolog --description "Conferencia mensal"
dbqm group show prod-vs-homolog -f json
dbqm group list -f json
dbqm group rm prod-vs-homolog --yes

# Curate a report template (content from --content or --content-file, stored
# verbatim -- whitespace-only content is refused, not silently stripped)
dbqm template add resumo-mensal --content "Total: {{total}}" --description "Resumo mensal"
dbqm template update resumo-mensal --content-file relatorio.txt
dbqm template show resumo-mensal -f json
dbqm template list -f json
dbqm template rm resumo-mensal --yes

# Test connections
dbqm test [connection]

# List resources
dbqm list connections|queries|groups

# Extract DDL
dbqm ddl <object> <connection>

# List objects by type (TABLE, VIEW, PACKAGE, ROUTINE)
dbqm objects <connection> --type TABLE

# Describe one object: columns, keys and indexes (no row count — see below)
dbqm describe <object> <connection>

# Browse a table, paged
dbqm rows <table> <connection> --limit 20 --offset 0

# Export/Import configs
dbqm export-config
dbqm import-config <file.dbqm>

# View history
dbqm history

# Read and write stored settings. Keys come from Settings' own fields and
# themes from the design tokens, both at runtime, so neither list goes stale.
# A bad value is refused, not coerced.
dbqm config list -f json
dbqm config get theme
dbqm config set audit_log_enabled true
dbqm config set theme plano-escuro

# Manage Oracle Instant Client installations (the only command that reaches
# the internet)
dbqm oracle-client available
dbqm oracle-client install 23.26.1.0.0
dbqm oracle-client list -f json
dbqm oracle-client rm instantclient_23_x64 --yes

# Describe dbqm's own CLI surface: every command, recursing into subcommands
# and their arguments -- read live from the parser, nothing hand-typed
dbqm describe-cli -f json

# Create a connection (password read from stdin, never from argv)
# A SQLite file needs nothing but its path. No host, no user, no password.
dbqm connection add local --type sqlite --database ./meu.db --no-password

echo "s3cret" | dbqm connection add prod --type oracle --mode direct \
    --host db.example.com --port 1521 --service ORCL --user admin \
    --password-stdin --test

# Change one field; everything else stays as it was, INCLUDING the password —
# `update` never reads DBQM_PASSWORD, only --password-stdin/--no-password
# change it, and only on this command line
dbqm connection update prod --host db2.example.com
echo "n0v4-s3cret" | dbqm connection update prod --password-stdin

# Inspect and list (the password is redacted)
dbqm connection show prod -f json
dbqm connection list -f json

# Remove (--yes is required when there is no terminal)
dbqm connection rm prod --yes
```

### Read-only connections

Mark a connection so dbqm refuses anything but a query on it:

```bash
dbqm connection update prod --read-only
dbqm connection update prod --no-read-only   # allow writes again
```

A write is refused before it reaches the driver:

```bash
$ dbqm sql "DELETE FROM t" prod -f json
{"ok": false, "command": "sql", "error": {"code": "read_only", "message": "Conexao 'prod' e somente leitura. Use --force-write para enviar assim mesmo.", "exit": 2}}
$ echo $?
2
```

`--force-write` lifts the refusal for that one invocation — but it does
**not** imply `--commit`, so a write still needs both flags:

```bash
dbqm sql "DELETE FROM t" prod --force-write --commit
```

`--force-write` alone still stops on the ordinary `--commit` check that
every DML statement is subject to, protected connection or not.


## Output format and exit codes

Every command accepts `-f/--format`. `run`, `sql` and `rows` offer
`table|json|csv|raw`; **every other command offers `table|json`** —
rather than list them here, where the list has already gone stale twice, ask
the program: `dbqm describe-cli -f json` reports every command, every
subcommand and every flag, read from the parser itself. `raw` prints plain values
with no headers/decoration, handy for piping the body of a view, package, or
procedure to another tool.
`--export csv|json|txt|html` writes the result to a file regardless of `-f`.
`html` writes a standalone report meant to be read in a browser, and is not
available together with `--flat`.

`-f json` wraps every command in one envelope: a success prints
`{"ok": true, "command": "...", "data": {...}}` to stdout; a failure prints
`{"ok": false, "command": "...", "error": {"code", "message", "exit"}}` to
**stderr**, with stdout left completely empty on failure. Pipe `data`, not
the top level:

```bash
dbqm list connections -f json | jq '.data[].name'

dbqm connection show nada -f json    # nothing on stdout; the error goes to
                                      # stderr; the process exits 2
```

Exit codes are stable across every command:

| Code | Meaning |
|---|---|
| `0` | success |
| `1` | a bug in dbqm — not the input, not the database |
| `2` | usage error, name not found, or a value that fails validation |
| `3` | connection failed |
| `4` | SQL error — the statement reached the driver and was rejected |
| `5` | comparison ran to completion and diverged (`run-group`) |
| `130` | interrupted (Ctrl+C) |

**`run-group` exits `5` when the comparison does not match**, in `-f json`
and in the default `-f table` output alike. Before 2.0.0 it always exited `0`
regardless of the result, so a script chaining `dbqm run-group ... &&
next-step` ran `next-step` unconditionally. It now stops on divergence, which
is the point of running a comparison in a script — see [CHANGELOG.md](../CHANGELOG.md)
for the full migration notes if you scripted against the pre-2.0 shapes.
`dbqm multi` exits `5` on the same terms: the join column it actually used
— the first column common to every connection, or whatever `--key` named —
is reported alongside the comparison, in the `-f json` envelope's
`join_key` field and in the `-f table` header, since a key chosen by a rule
the caller cannot see would turn every number downstream into a guess. A
connection that fails to answer or has its statement rejected stops the
command with nothing exported, rather than comparing whatever subset did
answer.

`export-config` and `import-config` accept `--password-stdin` and the
`DBQM_BUNDLE_PASSWORD` environment variable too, so neither blocks without a
terminal.


## Schema discovery

`objects`, `describe` and `rows` let a script — or an AI agent — see a
database's shape without hand-written catalogue SQL.

```bash
dbqm objects prod --type TABLE
```

```json
{"ok": true, "command": "objects", "data": {"connection_name": "prod", "obj_type": "TABLE", "objects": ["ACESSO_EXTERNO_LOG", "ACESSO_EXTERNO_USUARIO", "..."]}}
```

(the `objects` array lists every name; truncated above for brevity.)

```bash
dbqm describe ACESSO_EXTERNO_USUARIO prod
```

```
ACESSO_EXTERNO_USUARIO (TABLE)
+--------------------------------------+
| Coluna      | Tipo    | Nulo | Chave |
|-------------+---------+------+-------|
| CD_SUSEP    | varchar | NAO  | PK    |
| CD_CORRETOR | numeric | NAO  | PK    |
| CD_IP       | varchar | NAO  | PK    |
| CD_OPCAO    | numeric | SIM  |       |
+--------------------------------------+

INDICES
  PK_ACESSO_EXTERNO_USUARIO  UNIQUE (CD_CORRETOR, CD_SUSEP, CD_IP)
```

`-f json` carries the same content — columns (each with `data_type`,
`nullable`, `is_pk`, `fk_ref`) and `indexes`, plus `object_type` (`"TABLE"` or
`"VIEW"`) and, for a view, `sql_definition`. **Neither format shows a row
count** — a `COUNT(*)` is a full scan, and a describe is meant to be instant
(`psql \d` shows none either):

```json
{"ok": true, "command": "describe", "data": {"table": "ACESSO_EXTERNO_USUARIO", "columns": [{"name": "CD_SUSEP", "data_type": "varchar", "nullable": false, "is_pk": true, "fk_ref": ""}], "indexes": [{"name": "PK_ACESSO_EXTERNO_USUARIO", "columns": ["CD_CORRETOR", "CD_SUSEP", "CD_IP"], "is_unique": true}], "connection_name": "prod", "object_type": "TABLE"}}
```

```bash
dbqm rows ACESSO_EXTERNO_USUARIO prod --limit 3
```

```
+---------------------------------------------------------+
| cd_susep       | cd_corretor | cd_ip         | cd_opcao |
|----------------+-------------+---------------+----------|
| 00000100370631 | 1026        | 104.41.10.105 |          |
| 00000100617482 | 4031        | 104.41.10.105 |          |
| 00000100617482 | 4031        | 162.144.82.47 |          |
+---------------------------------------------------------+
3 registros em 0.61s
Mostrando 3 de 1607 linhas. Use --offset 3 para as proximas.
```

`rows` are parallel arrays, matching `run`/`sql` since 2.0.0; `-f json` also
carries `total_count`, `limit` and `offset` so a script can page without
parsing the table footer:

```json
{"ok": true, "command": "rows", "data": {"table": "ACESSO_EXTERNO_USUARIO", "connection_name": "prod", "columns": ["cd_susep", "cd_corretor", "cd_ip", "cd_opcao"], "rows": [["00000100370631", "1026", "104.41.10.105", null], ["00000100617482", "4031", "104.41.10.105", null], ["00000100617482", "4031", "162.144.82.47", null]], "row_count": 3, "total_count": 1607, "limit": 3, "offset": 0}}
```

There is deliberately no `--where` on `rows`: `dbqm sql` already takes a
predicate.
