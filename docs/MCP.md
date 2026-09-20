# MCP server

`dbqm mcp` serves dbqm's operations to an AI client over the [Model Context
Protocol](https://modelcontextprotocol.io), on stdio. It is a second front end
over the same `ops/` functions the CLI calls — every tool call returns the
CLI's own JSON envelope, so a client that already understands `dbqm run -f
json` already understands the tool's result.

It is not an HTTP server and it hosts nothing: the process is started by the
client (Claude Code, Claude Desktop, Cursor, VS Code, ...), talks stdio for
its lifetime, and exits when the client disconnects. There is no port to
open, no auth to configure beyond what dbqm already has (the connections in
`~/.dbqm/`), and no separate process to keep running.

[← Back to the README](../README.md)

---

## Install

```bash
pip install "dbqm[mcp]"
# or
uv tool install "dbqm[mcp]"
```

The `mcp` extra is opt-in. It pulls the MCP SDK and its own dependencies
(pydantic, starlette, uvicorn, and on Windows, pywin32) — about 27 MiB on
Windows and 13 MiB on other platforms, measured; pywin32 alone is roughly
half of the Windows figure. Nobody running only the TUI or the CLI needs
any of it, which is why it is not a core dependency.

Without the extra installed, `dbqm mcp` fails on stderr with the install
line above and exits `2` — the same shape as any other `usage` failure, not
a crash.

## Configure a client

**Claude Code:**

```bash
claude mcp add dbqm -- dbqm mcp
```

Add `--scope project` to check the server into the project's own MCP config
instead of your user-level one, so teammates get it too.

**Claude Desktop** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "dbqm": {
      "command": "dbqm",
      "args": ["mcp"]
    }
  }
}
```

If `dbqm` is not on the launching process's `PATH` (Desktop does not always
inherit your shell's), run it through `uv` instead:

```json
{
  "mcpServers": {
    "dbqm": {
      "command": "uvx",
      "args": ["--from", "dbqm[mcp]", "dbqm", "mcp"]
    }
  }
}
```

**Cursor** and **VS Code** take the same `"command"`/`"args"` shape, in their
own MCP config file (Cursor: `.cursor/mcp.json` or the global one from
Settings; VS Code: `.vscode/mcp.json` or the `mcp.servers` entry in
`settings.json`).

`DBQM_HOME` and `DBQM_LANG` are read from the environment the client starts
the server with — set them in the same `mcpServers` entry (an `"env"` key)
if the server should use a config directory or language other than the
default.

## Read-only by default

Every connection the server resolves is forced read-only, regardless of how
it is stored — a tool call cannot write, even to a connection whose own
`read_only` flag is `false`. Start the server with `--allow-write` to let
each connection's own flag decide, exactly as the CLI does.

How "read-only" is enforced depends on the engine, and the difference is
worth knowing before you assume a driver-level guarantee:

| Engine | Enforced by |
|---|---|
| PostgreSQL | Pinned on the server (`SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY`) |
| MySQL | Pinned on the server (`SET SESSION TRANSACTION READ ONLY`) |
| Oracle | Pinned on the server (`SET TRANSACTION READ ONLY`, per transaction) |
| SQLite | Pinned on the server (`PRAGMA query_only = ON`) |
| SQL Server | dbqm's own classifier only (`core/read_only.py`) — there is no server-side read-only pin for this driver |

On the first four, a statement that could write is refused twice over: dbqm's
classifier refuses it before it is sent, and the engine itself would refuse
it even if that guard were bypassed. On SQL Server there is only the first
line — it is still enforced, but it is dbqm refusing the statement, not the
database.

`--connection NAME` (repeatable) limits which connections the server exposes
at all; without it, every configured connection is reachable. `list
connections` and `test_connection` honour the allowlist: a connection not
named on the command line does not appear in `list connections`, and
`test_connection` without an explicit name tries only the exposed ones. A
tool call that names a connection the server was not started with fails with
`not_found` — the server does not distinguish "does not exist" from "exists
but is not exposed."

**The allowlist scopes the rest of the catalogue too** (`policy.py`,
`visible_queries`/`visible_groups`). `list queries` hides a saved query
whose own connection is not exposed. `list groups` hides a group when any
connection it touches is not exposed — every ad-hoc connection it names
directly, and every saved query it runs, through that query's own
connection. A query or group hidden this way is not just unlisted: calling
`run` or `run_group` on it still fails, because the underlying connection
resolves through the same allowlist and raises `not_found` — there is no
back door through a name the agent already knows. **`history` is not
filtered.** It is the machine's own execution history — CLI runs included,
not only MCP ones — so an entry can name a connection the running server
does not currently expose; `history` reports it as recorded rather than
hiding it.

## The tools

| Tool | Parameters | Mirrors |
|---|---|---|
| `list` | `kind: "connections" \| "queries" \| "groups"` | `dbqm list` |
| `test_connection` | `connection: str \| None = None` | `dbqm test` |
| `objects` | `connection: str`, `type: "TABLE" \| "VIEW" \| "PACKAGE" \| "ROUTINE"` | `dbqm objects` |
| `describe` | `connection: str`, `object: str` | `dbqm describe` |
| `rows` | `connection: str`, `table: str`, `limit: int = 100`, `offset: int = 0` | `dbqm rows` |
| `ddl` | `connection: str`, `object: str` | `dbqm ddl` |
| `history` | `limit: int = 20` | `dbqm history` |
| `run` | `query: str`, `params: object \| None = None`, `connection: str \| None = None` | `dbqm run` |
| `run_group` | `group: str`, `params: object \| None = None` | `dbqm run-group` |
| `multi` | `sql: str`, `connections: list[str]`, `params: object \| None = None`, `key: str \| None = None` | `dbqm multi` |
| `sql` | `connection: str`, `sql: str`, `params: object \| None = None`, `commit: bool = False`, `explain: bool = False` | `dbqm sql` |

Every `params` is a JSON object of string values — the same shape as the
CLI's repeated `-p KEY=VALUE`, just a single object instead of a flag
repeated per pair.

`sql` is the one write-capable tool: with the server started `--allow-write`
and a connection whose own `read_only` is `false`, `commit=true` runs DML;
`explain=true` returns the execution plan instead of running the statement
(no plan exists for SQL Server, and the tool says so rather than returning
nothing).

**The envelope** is the CLI's own, unchanged, returned as the tool's
structured content:

- Success: `{"ok": true, "command": "...", "data": {...}}`, with an optional
  `"warnings"` array (compile errors from `ddl`, comparison notes from
  `multi`/`run_group`, or non-SELECT output lines from `sql`).
- Failure: `{"ok": false, "command": "...", "error": {"code", "message",
  "exit"}}`. The `exit` field carries the CLI's exit code for reference; it
  is not a process exit here, since the server itself keeps running.
- **A diverged comparison is a success, not a failure.** Where the CLI would
  exit `5`, `multi` and `run_group` still return `ok: true` — the run
  completed; `data.all_match: false` (and the per-row detail) says the
  databases disagreed. A tool caller checks `all_match`, not `ok`, to learn
  whether the comparison matched.

## Permissions per tool in Claude Code

Claude Code names each tool `mcp__dbqm__<tool>` — the server name (`dbqm`)
and the tool name, double-underscore separated. Use that to allow or deny
individual tools in `settings.json`:

```json
{
  "permissions": {
    "allow": [
      "mcp__dbqm__rows",
      "mcp__dbqm__describe",
      "mcp__dbqm__objects",
      "mcp__dbqm__run"
    ],
    "deny": [
      "mcp__dbqm__sql"
    ]
  }
}
```

This is independent of `--allow-write`: denying `mcp__dbqm__sql` keeps an
agent off ad-hoc SQL entirely even on a server started read-only, while the
four allowed tools above are read-only regardless of how the server was
started.

## Troubleshooting

**Nothing prints to stdout but the protocol.** Under stdio, stdout is the
wire — a stray `print()` anywhere in the call path would corrupt the first
frame the client reads. All of dbqm's own logging goes to stderr, at
`WARNING` and above.

**`dbqm history` shows MCP runs too.** The server calls the same `ops/`
functions the CLI does, so a query run through a tool call is the same kind
of history entry as one run from a terminal — `history` (the tool and the
CLI command) does not distinguish where a run came from.

**Concurrent tool calls are safe for the history and audit files.** The SDK
runs tool functions in worker threads, so two calls can execute at once;
history writes go through a temp file and an atomic replace, audit writes
are lock-serialised appends (`core/history.py`, `core/audit.py`) — different
mechanisms, both safe under concurrent calls. That guarantee is about
dbqm's own files — a database driver that is not thread-safe under
concurrent calls is the driver's own limitation, not something the server
works around.

**Testing by hand.** For an automated test, build the server in-process and
talk to it with the SDK's client over a pair of pipes — `Client(build_server(
options))` — which is what `tests/mcp/` does; that shape is for tests, not
for a real client, since it skips the stdio transport entirely. To check
that a configured client can actually see the server, ask the client:
`claude mcp list` for Claude Code, or the equivalent "list servers" surface
in Desktop/Cursor/VS Code.
