# Backend Python — Architecture Guidelines

This document defines the architecture, prescribed stack, and code conventions for Python application projects: services, bots, CLIs and TUIs. It is a stack doc referenced by `TASK-COMPLETION.md` — it declares the concrete build, lint, test, and version commands consumed in the task-completion cycle.

The mandatory core (toolchain, layout, architecture, configuration, errors, logging, async, testing, cycle) applies to every project. The sections marked **conditional** apply only when their stated criterion holds; a project says which ones it adopts in its agent-guidance file.

## Prescribed Stack

Do not add dependencies outside this list without explicit justification.

| Category | Technology | Notes |
|---|---|---|
| Language | Python 3.14 | Floor `>=3.13` in `requires-python`. Exact pin in `.python-version` (`uv python pin`). Adopt a new minor at its `.2` release, not before. |
| Package and environment manager | uv | `uv.lock` committed. Dependency groups per PEP 735 (`[dependency-groups]`). No Poetry, no `requirements.txt`. |
| Build backend | `uv_build` | Pure-Python projects. Switch to hatchling only for build hooks, C extensions or VCS-derived versions. |
| Lint and format | ruff | Pinned to an exact version. Explicit `select`. `ruff format` replaces black and isort. |
| Type checker | mypy | `strict = true`. Per-module ratchet for legacy code (see Adopting). |
| Testing | pytest + pytest-asyncio + pytest-cov | `asyncio_mode = "strict"`. Coverage measured on every run; the floor is project-defined. |
| Property tests | hypothesis | Parsers, serializers, invariants. Optional but preferred over hand-rolled input tables. |
| Configuration | pydantic-settings | One `Settings` object, `extra="forbid"`. |
| Data at the edges | pydantic v2 | Request/response bodies, external payloads, config. Never in the domain. |
| Data in the domain | `dataclasses` | `@dataclass(slots=True, frozen=True)`. |
| HTTP client | httpx | One shared `AsyncClient` per process, created at startup. Never `requests`. |
| Logging | stdlib `logging` | Configured once via `dictConfig`. structlog is conditional (HTTP API). |
| HTTP API (conditional) | FastAPI + uvicorn | See "HTTP API". |
| CLI (conditional) | typer + rich | See "CLI". |
| TUI (conditional) | Textual | See "TUI". |
| Database (conditional) | SQLAlchemy 2.x (async) + Alembic | Raw drivers (`oracledb`, `psycopg`, `pymssql`, `PyMySQL`) as a sub-conditional. See "Database". |
| Integration tests (conditional) | testcontainers | Behind the `integration` marker. See "Database". |
| Container (conditional) | Docker multi-stage with uv | See "Docker". |
| Security scan | `uv audit` + ruff `S` rules | `pip-audit` as fallback while `uv audit` is in preview. No standalone bandit. |

## Development Standards

- **Modern typing, checked.** PEP 695 syntax (`def first[T](items: list[T]) -> T`, `type UserId = int`). `Protocol` for ports, `TypedDict` for wire-shaped dicts, `@typing.override` on every override. Do **not** add `from __future__ import annotations` on 3.14+: PEP 649 makes annotations lazy by default, and the import now opts back into stringified annotations. Every function in `src/` is annotated; mypy enforces it.
- **Constructor injection only.** A service receives its ports as constructor arguments. No module-level singletons that are looked up, no service locator, no registry to fetch a dependency by name — one was built, used, and deleted in a consuming project because everything it exposed already belonged in a service.
- **One composition root.** `__main__.py` (or the module named in `[project.scripts]`) builds `Settings`, wires adapters to services, and starts the loop. Nothing under `src/<pkg>/` imports the composition root.
- **Frozen dataclasses for values.** Anything that crosses a port is `@dataclass(slots=True, frozen=True)`. Mutable dataclasses only where mutation is the point (a builder, a running tally).
- **`pathlib` everywhere.** Never `os.path`. Never build a runtime path by hand — see "Configuration".
- **Subprocesses without a shell.** `asyncio.create_subprocess_exec` / `subprocess.run([...])` with a list. Never `shell=True`.
- **No `print` outside the CLI adapter.** Libraries and services log; the CLI prints. A TUI does neither — it renders.
- **Machine tokens, not prose, for states.** A field that a caller branches on (`reason`, `status`, `db_type`) is an `Enum` or `Literal`, never a free string with the valid values in a comment.
- **Named constants with a measured reason.** A delay, a cap or a threshold is a module-level constant whose comment says what was measured (`SEND_ENTER_DELAY = 0.5  # verified against tool 2.1: a 7-line send stuck with a single write`). A bare number is a rule nobody can revisit.
- **Docstrings say why.** Type hints carry the types. A docstring on a public function or module states the intent, the contract a caller can rely on, or the bug that shaped it. No docstring that restates the signature.
- Solutions must be simple, modern, high-performance, and secure.

## Project Layout

`src/` layout is mandatory: tests run against the installed package, not the working tree, so an import that works only because the repo root is on `sys.path` fails early.

```
pyproject.toml            # metadata, dependencies, every [tool.*] section
uv.lock                   # committed
.python-version           # exact interpreter, from `uv python pin`
AGENTS.md                 # the project's rules; CLAUDE.md is a pointer stub
src/<pkg>/
├── __init__.py
├── __main__.py           # composition root: Settings, wiring, run
├── core/
│   ├── config.py         # Settings (pydantic-settings)
│   ├── paths.py          # every runtime path, one root, one env override
│   └── logging.py        # configure() + get_logger()
├── domain/
│   ├── models.py         # frozen dataclasses, enums
│   ├── ports.py          # Protocols the application depends on
│   └── exceptions.py     # AppError hierarchy
├── application/          # services / use cases; import domain only
└── adapters/
    ├── inbound/          # api/, cli/, tui/, bot/ — one per entry surface
    └── outbound/         # persistence/, http/, filesystem/ — one per port family
tests/
├── conftest.py           # autouse isolation of all real state
├── unit/                 # one file per module under src/
├── e2e/                  # whole flows, faked only at the edges
└── live/                 # opt-in: real endpoints, real credentials
```

`in` is a keyword, so the adapter packages are `inbound` and `outbound`. A small project may collapse `application/` into `domain/`; it may not put an adapter there.

Entry points are declared, never implied:

```toml
[project.scripts]
myapp = "myapp.__main__:main"
```

`python -m myapp` must also work — `__main__.py` guards its own `main()` call.

## Lint and Type Configuration

Every `[tool.*]` section lives in `pyproject.toml`. ruff's rule set is explicit, because a ruff upgrade changes the defaults (0.16 went from 59 to 413 default rules) and a floating default is a CI break on someone else's schedule:

```toml
[tool.ruff]
line-length = 100
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "B", "C4", "SIM", "RUF", "S", "ASYNC", "DTZ", "LOG", "PTH", "TID", "PL"]
ignore = ["E501"]                      # the formatter owns line length; long URLs and f-strings stay
[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101", "PLR2004"]       # assert and magic numbers are the point of a test

[tool.mypy]
strict = true
warn_unreachable = true
packages = ["myapp"]
```

Every `ignore` and `per-file-ignores` entry carries a one-line reason. An unexplained ignore is a rule that was switched off, not a decision.

## Architecture

Hexagonal architecture, kept light. The rule is the dependency direction; the folders exist to make it visible.

- **`domain/` imports the standard library only.** No pydantic, no framework, no driver.
- **`application/` imports `domain/`.** It orchestrates ports; it never knows which adapter is behind one.
- **`adapters/` import `application/` and `domain/`.** An inbound adapter translates a request, a key press or a message into a service call. An outbound adapter implements a port.
- **Nothing imports the composition root, and nothing in `domain/` or `application/` imports `adapters/`.** A policy test asserts this (see Testing).

**Ports are `Protocol`, and every implementation is contract-tested.** Adapters need no inheritance, and a test that iterates the registered implementations and checks `isinstance` against the `@runtime_checkable` protocol catches a renamed method on the day it is renamed:

```python
@runtime_checkable
class Notifier(Protocol):
    def send(self, recipient: UserId, text: str) -> DeliveryReceipt: ...

def test_every_notifier_satisfies_the_contract() -> None:
    for adapter in NOTIFIERS:
        assert isinstance(adapter, Notifier), adapter
```

**One dispatch chokepoint per external tool.** When several callers drive the same subprocess, API or protocol, they go through one function with one stable return contract (`run(*args) -> str`), so the parsers and detectors are written once and the e2e fakes replace one seam. Callers that reach around it duplicate the parsing and drift.

**Third-party coupling lives in one module with an audit trigger.** Everything that depends on a vendor's schema, CLI output or version (`integrations/<vendor>_schema.py`) is in one file, the version bump is announced somewhere a human sees it, and the `live` tests name the field that moved. Drift spread across modules is silent and surfaces days later as a detector that quietly stopped firing.

**"Cannot tell" is a value, never "no".** A probe that has no reliable way to answer returns `None` (`signed_in() -> bool | None`), and an empty tuple of markers means "unknown, do nothing", not "not blocked". Collapsing uncertainty into `False` turns a blind spot into a wrong decision.

## Configuration

**One `Settings`, built once, passed down.** pydantic-settings with `extra="forbid"`, so a typo'd environment variable fails at boot instead of silently using the default:

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8-sig",
        env_nested_delimiter="__", extra="forbid",
    )
    bot_token: SecretStr
    allowed_user_id: int
    log_level: str = "INFO"
```

- The composition root constructs `Settings()` and hands it (or the fields a service needs) to constructors. The domain never imports settings.
- **Fail fast, fail usefully.** An unusable configuration exits with a multi-line message that names the variable and the file it was expected in. It never surfaces as a `ValidationError` traceback at import time — that is the least helpful possible first contact.
- **`.env` is found by walking up to a marker** (`pyproject.toml`), never by counting `.parent` — a module moved one directory deeper otherwise points the loader at nothing while every unit test stays green on the fake environment.
- **`.env` is read as `utf-8-sig`.** A file written by PowerShell 5.1 carries a BOM and plain `utf-8` turns the first key into `\ufeffBOT_TOKEN`.
- **Secrets come from the environment only.** `.env` is gitignored and never copied into an image; `.env.example` documents every variable with no real value. A password stored at rest is a salted hash (or encrypted with a key file at `0o600`), never plaintext. Comparisons use `hmac.compare_digest`.

**Every runtime path resolves in one module.** `core/paths.py` derives everything from one root, overridable by one environment variable so tests never touch the operator's state:

```python
def home() -> Path:
    return Path(os.environ.get("MYAPP_HOME", Path.home() / ".myapp"))

def config_dir() -> Path: return home() / "config"
def logs_dir() -> Path:   return home() / "logs"

def ensure_dirs() -> None:
    for d in (config_dir(), logs_dir()): d.mkdir(parents=True, exist_ok=True)
```

Paths are **functions, not module-level constants**: a constant copied with `from paths import CONFIG_DIR` is captured at import time, and the test fixture that redirects the root must then re-patch every module that copied it. A grep-based policy test fails any module that spells a runtime path out by hand.

**Migrations of user state are non-destructive and per-entry.** Move if absent, never overwrite; let one locked file cost only that entry; never migrate open log files (Windows refuses to move them, and one refusal must not abort everything after it).

## Exception Handling

**An exception exists when a caller can act differently because of it.** Everything else is a return value. There is no exception for "not found" or "unavailable" in general — a codebase is full of places where "we could not tell" is a legitimate answer that must not become a failure.

```python
class AppError(Exception):
    """Root. A caller can act on any subclass; everything else is a return value."""

class ConfigError(AppError): ...
class DomainError(AppError): ...          # a business rule was violated

class InfrastructureError(AppError):      # an adapter failed
    def __init__(self, reason: Reason, *, detail: str = "") -> None:
        super().__init__(detail or reason)
        self.reason = reason              # machine token: UNREACHABLE, TOKEN_EXPIRED, HTTP_503
```

- **Reasons are tokens, messages are for humans.** A caller branches on `reason`; the UI renders `detail`. Tokens are an `Enum`/`Literal`, so a new one is a type error until every branch handles it.
- **Result objects at the UI boundary.** An engine function that a screen calls returns a result (`success: bool`, `error: str`, `rows: list[...]`) so the happy and sad paths share one type; error text is truncated at that boundary (first line, ≤ 500 characters). Raising across the UI boundary means every screen writes its own `try`.
- **`raise ... from e`** whenever an exception is translated. An `ImportError` from a missing driver becomes an `InfrastructureError(Reason.DRIVER_MISSING)` with a platform-aware message, chained.
- **Broad `except Exception` only at an I/O or third-party boundary, with a documented degradation and a visible signal.** `except Exception: pass` is forbidden: a swallow that logs nothing and shows nothing is a bug that will be found from scratch later. Log at `warning` with `exc_info=True`, or route to the UI's error surface.
- **Framework exceptions never leave the adapter.** The domain does not know `HTTPException`; the HTTP adapter maps `DomainError` → 4xx and `InfrastructureError` → 5xx in one handler.
- **The top-level handler logs, then re-raises.** In a supervised process, `log.critical("crashed", exc_info=True)` followed by `raise` keeps the traceback in the log *and* lets the supervisor see the exit and relaunch. Swallowing at the top hides the crash and stalls the restart.
- `except*` / `ExceptionGroup` where they arise naturally — from a `TaskGroup` — not as a general style. No `Result` type libraries: exceptions are the Python answer.

## Logging

stdlib `logging`, one logger per module, one configuration function:

```python
def configure(level: str = "INFO") -> None:
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)   # logs every URL at INFO, leaks the token
    logging.getLogger("httpcore").setLevel(logging.WARNING)

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)   # pass __name__
```

- **`log = get_logger(__name__)` at the top of every module.** One root logger works while there is one module; it stops working the moment services live in their own files, because the output no longer says which part of the system spoke.
- **`configure()` is idempotent** and called from every entry point (main, CLI, worker). A library never configures logging; it attaches a `NullHandler` at most.
- **Mute chatty third parties at startup**, by name, with the reason in a comment. Token leakage through a vendor's request log is the usual one.
- **Never log secrets or PII.** Tokens, passwords, cookies, message bodies of other users.
- **Supervised processes log to stdout.** The supervisor redirects to the file; that is what keeps `Get-Content -Wait` / `tail -f` working and what kept the log readable when the process itself could not start.
- Levels: `debug` for the mechanism, `info` for lifecycle events an operator wants, `warning` for a degradation the process survived, `error` for a failed operation, `critical` only in the top-level handler.
- structlog + JSON rendering is adopted in the HTTP API section when logs ship to a collector. Elsewhere it is weight without a reader.

## Async

- **One event loop per process.** Mounting a second surface (a web UI beside a bot) means mounting it on the same loop, not spawning a second process with a network hop between them.
- **`asyncio.TaskGroup` for concurrency**, never bare `create_task` you forget to await and never `gather` (it leaks tasks on failure). One `asyncio.timeout` around the group so every child shares a deadline:

```python
async with asyncio.timeout(10):
    async with asyncio.TaskGroup() as tg:
        usage = tg.create_task(fetch_usage(client))
        status = tg.create_task(fetch_status(client))
```

- **Blocking work leaves the loop.** `await asyncio.to_thread(blocking_call, ...)` for drivers, file I/O and subprocess pipes that block. A port whose implementation blocks says so in its docstring (`refresh()` blocks and is run in a thread; `get()` is non-blocking).
- **A cache shared between the loop and a thread takes a `threading.Lock`.** `asyncio.Lock` does not protect the thread side.
- **`asyncio.run` only in the entry point.** Libraries and services expose coroutines; the composition root owns the loop.
- **`CancelledError` is re-raised.** Catch it only to clean up, then `raise`.
- **Async tests are explicit.** `asyncio_mode = "strict"` and `@pytest.mark.asyncio` on each async test. Projects whose stack already ships anyio (FastAPI, httpx) may use the anyio plugin instead — one of the two, never both.

## HTTP API (conditional)

Applies when the project exposes an HTTP interface (REST, webhooks, a web UI backend). A bot, CLI or TUI with no HTTP surface skips this section.

- **FastAPI on uvicorn.** `Depends` is used only at the route boundary to hand in the already-built service; it never constructs anything. The lifespan handler builds the composition (settings, shared `httpx.AsyncClient`, engine) and tears it down.
- **DTOs are pydantic models in the adapter**, mapped to and from frozen domain dataclasses. A domain object is never returned from a route.
- **One exception handler** maps the `AppError` hierarchy to RFC 9457 problem details. Validation errors are 422, `DomainError` 4xx, `InfrastructureError` 5xx with the `reason` token in the body.
- **Pagination on every list endpoint.** No unbounded collections.
- **Server-Sent Events and streaming responses disable proxy buffering** (`X-Accel-Buffering: no`, `Cache-Control: no-cache`) — a policy test asserts it on every stream.
- **Logging here is structlog** rendered as JSON in production and console in development, with request id and user bound via `contextvars`. OpenTelemetry instrumentation for FastAPI, SQLAlchemy and httpx when the platform collects traces.
- Granian or another server is a project deviation justified by a measured server-level bottleneck, not by a benchmark.

## CLI (conditional)

Applies when the project exposes a command-line interface, including a `--version` / `--help` on an otherwise interactive app.

- **typer** for commands (the interface derives from type hints), **rich** for output. No hand-rolled `argv` dispatch.
- **Exit codes are a contract.** `0` success, `1` failure, `2` usage error, `130` on `KeyboardInterrupt`. The top-level `main()` maps `AppError` to a one-line message on stderr and a non-zero exit; a traceback reaches the user only with `--debug`.
- **Output formats are explicit.** `--format table|json|csv|raw`, where `raw` prints values without decoration for piping. JSON output is `ensure_ascii=False`.
- The CLI is a thin inbound adapter: it parses, calls one service, renders. Business rules in a command function are a smell.

## TUI (conditional)

Applies when the project ships a terminal user interface (Textual).

- **Every failure reaches one surface.** Override `App._handle_exception` to push an error modal (falling back to `notify(severity="error")`) and route `on_worker_state_changed` `ERROR` states into the same handler, because all blocking work runs in `@work(thread=True)` workers whose exceptions otherwise vanish. The handler does not re-raise: the app stays alive.
- **Escape Rich markup before rendering user or traceback text** (`text.replace("[", r"\[")`). A stack trace containing `[bold]` is a rendering bug, not a message.
- **Keys that must not be swallowed are handled in `on_key`** with `event.prevent_default()` / `event.stop()`, not in `key_*` methods (which mark the event handled even when they do nothing) and not in `BINDINGS` inside a `TextArea` (which consumes bindings). `check_action` returns `False` while a modal is on the stack so screen shortcuts do not fire through it.
- **Widgets never touch a driver.** A screen calls a service and renders the result object; timestamps and paths are captured in the UI and injected, so the engine stays pure and testable.
- **Tests drive the real app**: `async with app.run_test() as pilot`, `await pilot.press(...)`, assert on `app.query_one(...)`. Screens are mounted inside a minimal host app.
- **Snapshot tests follow the visual-regression rule of the other guides**: the floor is intention (widget state, policy tests); pixel/snapshot baselines only when the suite runs in CI on a fixed image, on deterministic screens, refreshed deliberately in the same commit as the change they reflect.
- **Production code never branches on "am I under test"** (`"pytest" in sys.modules`, `PYTEST_CURRENT_TEST`, a `TESTING` flag). A consuming project shipped one layout to tests and another to users for months; the production layout was simply never tested.

## Database (conditional)

Applies when the project owns a database or talks to one. Choose the default unless the criterion for the sub-conditional holds.

**Default — SQLAlchemy 2.x (async) + Alembic.**

- Typed declarative models: `Mapped[...]` / `mapped_column()`. One `async_sessionmaker`; one session per request or unit of work, opened and closed by the repository adapter, never by the domain.
- Repositories implement a port; the application never sees a `Session`.
- Every schema change is an Alembic migration. Autogenerate is a draft to be read, not a result to be committed. Migrations run in CI against a container.
- Raw SQL is right for analytical queries and bulk operations — `text()` with bound parameters, inside a repository.
- `asyncpg` for PostgreSQL by default; `psycopg` 3 when one driver must serve sync and async.
- SQLModel is rejected: it conflates the persistence model with the API model, which is exactly the coupling the port exists to prevent.

**Sub-conditional — raw drivers.** Applies when the project is a database *tool* (query runner, DDL extractor, multi-vendor client) rather than an application that owns a schema. Then:

- **Import the driver lazily, inside the function that needs it**, and turn `ImportError` into an actionable message that names the platform (`raise InfrastructureError(Reason.DRIVER_MISSING, detail=missing_driver_message("oracledb")) from e`). A top-level import of a wheel-less driver is an import crash on the one platform it matters.
- **Vendor differences go through one dispatcher** on an `Enum` discriminator, and each vendor's dialect (catalog queries, DDL extraction, bind style) lives in its own module. An `if/elif` on a string in twenty places is the alternative, and it is how a vendor gets half-supported.
- **Bind every value.** One converter per bind style (`:name` native for Oracle, rewritten to `%(name)s` for pyformat drivers). When an identifier must be interpolated, it passes through an allowlist that raises:

```python
_IDENT = re.compile(r"^[\w#$.]+$")

def checked_identifier(name: str) -> str:
    if not _IDENT.match(name):
        raise DomainError(f"invalid identifier: {name!r}")
    return name
```

- **Caps are constants**: rows per result (`MAX_ROWS = 10_000`, enforced with `fetchmany`), import bundle size, history length.
- **Transactions have one owner.** A function that returns an open connection for the caller to commit says so in its return type and nulls its own reference so `finally` does not close it. Saved queries are `SELECT`-only, checked by classification before execution.
- **Close in `finally`, cursor then connection**, each in its own guarded `try`. No pooling unless measured — a tool opens, runs, closes.
- **Encoding is forced at the source** (`NLS_LANG=.AL32UTF8` for Oracle on Windows), with the symptom it fixes in the docstring, and every JSON written is `ensure_ascii=False`.
- Platform-conditional dependencies carry a marker and an inline comment saying which wheel is missing where (`; sys_platform != 'win32' or platform_machine != 'ARM64'`), mirrored as opt-in extras so `uv sync` never fails on the platform without it.

**Integration tests** for either mode run behind the `integration` marker against testcontainers (session-scoped container fixture), excluded by `addopts`, and skip with a stated reason when Docker is absent. Unit tests never open a connection: mock at the driver boundary, or use in-memory SQLite as an SQL proxy for dialect-neutral logic.

## Docker (conditional)

Applies when the project ships as a container. Multi-stage, uv in the builder only, non-root at runtime:

```dockerfile
FROM python:3.14-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-editable

FROM python:3.14-slim
RUN useradd -m -u 1000 app
COPY --from=builder --chown=app /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
USER app
CMD ["myapp"]
```

Dependencies sync in a layer before the source is copied, so a code change does not re-resolve. `.env` is never copied in; configuration arrives as environment variables.

## Windows-First Projects (conditional)

Applies when the primary runtime is Windows (a desktop tool, a bot supervised by Task Scheduler). Cross-platform projects skip it, but the encoding rules above still hold.

- **`requires-python` has a ceiling with a reason** when a native wheel does not exist above it (`>=3.13,<3.15  # no pywinpty wheel above 3.14`). The installer re-derives the range from `pyproject.toml` and self-tests its own gate; it never re-types it.
- **The documented entry point is a `.cmd`**, not a `.ps1`: execution policy governs `.ps1` files on a fresh box and does not govern `.cmd`. The `.cmd` forwards its arguments untouched to the real script.
- **Path guards compare resolved paths, not strings.** `Path(".").parts == ()` passes every prefix check and then deletes the workspace root; `expanded == Path("/")` is false for `W:\`. "Is root" is `p.parent == p`; "is inside" is `p.resolve().is_relative_to(root.resolve())`.
- **Filenames respect `MAX_PATH`**: cap the generated name so root + name + extension stays under 240 characters, and keep the extension when truncating.
- **`chmod` is best-effort.** Wrap `Path.chmod(0o600)` in `except OSError`; Windows ignores the mode and must not fail the operation.
- **Never assume a drive letter or a user directory.** Derive from `Path.home()` and the `<APP>_HOME` override.
- **Process supervision is a relaunch loop outside Python** (a scheduled task running a supervisor script). The newest supervisor wins on purpose: it kills a pre-existing instance, because two pollers on one bot token is a `Conflict` that neither survives.

## Testing

### General Rules

- Language follows the cascade defined in `COMMITS.md` for test names, test class names, and helper function names.
- Test the code as it behaves now. Do not modify production code while writing tests.
- If incorrect behavior is found during testing, do not fix it silently. Report the issue to the user, describe the observed vs expected behavior, and ask for direction before making any change.
- No comments in test code (`# Arrange`, `# Act`, `# Assert`, `# Helpers` — all forbidden). A docstring on a test is allowed for one purpose: naming the bug that motivated it.
- Helper functions at the bottom of the file, exposed to other modules only as fixtures.

### Configuration

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra --strict-markers --strict-config -m 'not live and not integration'"
asyncio_mode = "strict"
xfail_strict = true
filterwarnings = ["error"]
markers = [
  "live: hits a real third-party endpoint with this host's credentials (opt-in)",
  "integration: needs a container or a real service on this host (opt-in)",
]

[tool.coverage.run]
source = ["src"]
branch = true
```

`filterwarnings = error` turns a deprecation into a failing test the day it appears, which is the cheapest moment to fix it.

### Layout and Naming

- **`tests/unit/` mirrors `src/`, one file per module.** `tests/e2e/` holds whole flows, faked only at the edges the suite must never touch (the terminal, the network, the vendor endpoint). `tests/live/` is opt-in.
- **Tests are named as sentences about the guaranteed behaviour, especially the negative one.** `test_logs_are_never_migrated`, `test_one_stuck_entry_does_not_strand_the_others`, `test_a_ready_marker_never_overrides_the_trust_gate`. Classes group by unit under test (`class TestClassifySql`).
- **The bug lives in the docstring.** A test written after a defect names the mechanism and, when there is one, the ticket. The next reader learns why the test exists without `git blame`.
- **When the fix is "do not call X", assert X was not called.** Monkeypatch the expensive call to record invocations and assert the list is empty. A test that only checks the output passes again the day someone reintroduces the call.

### Isolation

- **An autouse fixture in the root `conftest.py` redirects all real state** (the `<APP>_HOME` root, the `.env`, the credential files) to a throwaway directory before any test imports the application. No test can touch the operator's machine, and no test needs to monkeypatch a private helper to stay off it.
- **Fixtures, not importable helpers.** Everything in a `conftest.py` is exposed as a fixture; `from conftest import helper` resolves by `sys.path` order and breaks the day a second `conftest.py` appears.
- **`monkeypatch` and small hand-written fakes before `unittest.mock`.** A fake that implements the port is reusable and type-checked; a `MagicMock` accepts every call, including the wrong one. `MagicMock`/`AsyncMock` only at a driver or SDK boundary that has no port.
- **Fakes stay at the edges.** An e2e test replaces the transport, not the handler's own parsing: a handler's 400 on a malformed body is part of what the flow checks.
- **Time is injected**, not frozen: a function that needs "now" takes it as a parameter or a `Clock` port. `time-machine` for the entry points that cannot.

### Live and Integration Tests

- **`live` tests hit a real endpoint with real credentials** and exist to catch schema drift. They **skip, never fail,** on a missing credential, an expired token, a rate limit or an empty wallet — none of those is drift, and failing on them trains everyone to ignore the result.
- **A `live` assertion carries its remediation** in the message: which field moved, which module to update.
- `integration` tests need a container or a local service; they skip with a stated reason when it is absent.
- Both are excluded by `addopts` and run on request: `uv run pytest -m live`, `uv run pytest -m integration`.

### Policy Tests

A rule that every module must follow rots on the 47th module, not the first. Enforce it with a unit test that scans `src/` and fails naming the offender:

```python
def test_domain_and_application_import_no_adapter() -> None:
    offenders = [
        p for p in (SRC / "domain").rglob("*.py")
        if re.search(r"^\s*(from|import) \w+\.adapters", p.read_text("utf-8"), re.M)
    ]
    assert offenders == []
```

- Candidates: the dependency direction above; no module spells a runtime path out by hand; every port implementation satisfies its `Protocol`; every declared gate ships with the answers it needs; every streaming route disables proxy buffering; no production module mentions `pytest`.
- Location: `tests/unit/test_policy_*.py`, one file per rule family. They run with the unit suite — cheap, deterministic, no I/O beyond reading the tree.

### Coverage and Counts

- `pytest-cov` runs on every Step 3 (`--cov=src --cov-report=term-missing`). The floor (`--cov-fail-under`) is project-defined; a project that keeps a scenario-to-test map instead says so in its agent-guidance file, with the same honesty rule: a gap is listed as a gap, not omitted.
- **Never state a test count in prose.** Three documents will give three numbers within a month. State the command that prints it.

## Adopting the Guide in an Existing Codebase

A codebase that grew without a lockfile, a linter or a type checker is not migrated by turning everything on at once — the first run reports thousands of findings and the change is reverted by lunchtime.

**Migration happens in this order, never all at once:**

1. **Lockfile first, changing no code.** `uv init --bare` (or `uv add` from the old `requirements.txt`), commit `uv.lock` and `.python-version`, delete `requirements.txt`. Every following step now runs on a reproducible environment.
2. **ruff with the rules the code already passes**, then widen `select` one family at a time, fixing or justifying (`# noqa: XXX — reason`) each finding. Every `ignore` and `per-file-ignores` entry in `pyproject.toml` carries a one-line justification.
3. **mypy strict with a ratchet.** `strict = true` globally, and an `[[tool.mypy.overrides]]` block listing the legacy modules with `ignore_errors = true`. New modules are strict from their first line; the list only shrinks, and a policy test asserts no module is added to it.
4. **pytest strict configuration** (`--strict-markers`, `filterwarnings = error`, `xfail_strict`), fixing the warnings it surfaces.
5. **CI runs Steps 1–3** on every push. Until it does, the gates are manual and therefore optional.

**Never swap steps 1 and 3.** A type checker run on an environment that resolves differently on each machine reports different errors on each machine, and the ratchet list becomes a negotiation.

## Build, Lint, Test, and Version

This file is the stack doc referenced by `TASK-COMPLETION.md`. It declares the commands consumed in the task-completion cycle:

| TASK-COMPLETION Step | Command | Notes |
|---|---|---|
| Step 1 — Build | `uv sync --locked` | Fails when `uv.lock` is out of date with `pyproject.toml`. Add `uv build` when the project ships a wheel. |
| Step 2 — Lint | `uv run ruff check . && uv run ruff format --check . && uv run mypy` | All three. mypy is part of the lint step — typing is a static gate, not a test. |
| Step 3 — Test | `uv run pytest --cov=src --cov-report=term-missing` | Unit + e2e. `live` and `integration` are excluded by `addopts` and run on request. |
| Step 5 — Version | `uv version --bump <major\|minor\|patch>` | Edits `[project] version` in `pyproject.toml`, the single source. Read at runtime with `importlib.metadata.version("<pkg>")`, never a hand-maintained `__version__`. |

Release is tag-driven per `VERSIONING.md`: the pipeline runs on `v*` tags, guards that the tag equals `[project] version` and fails otherwise, builds with `uv build`, and publishes with the CI secret. A manual `twine upload` from a developer machine bypasses the guard and is not a release.

The rules for choosing the bump level are in `VERSIONING.md`. The cycle orchestration is in `TASK-COMPLETION.md`. This section declares commands only — not workflow rules.

## See Also

- `TASK-COMPLETION.md` — Orchestrator of the cycle: build → lint → test → docs → version → commit → merge.
- `VERSIONING.md` — Rules for choosing the version bump level and the tag-driven release flow.
- `COMMITS.md` — Rules for writing commit messages and the language cascade used in test names.
- `AGENT-WORKFLOW.md` — Operating discipline before and during a change.

## Deviations in this project

dbqm predates this guide and is a **published tool other people install**
(`pip install dbqm`), not a service we deploy. That single fact drives most of
what follows: the floor version, the absence of a lockfile, and the flat layout
are all consequences of shipping a wheel to strangers rather than an image to a
cluster.

**Where the project stands on the adoption ladder:** four of the five
migration steps in "Adopting the Guide in an Existing Codebase" have run
(2.3.1) — 1, 2, 4 and 5. Step 3, mypy, is the one outstanding, deliberately
not part of that slice — see `docs/ROADMAP.md` Tier 2 for the measurement
that makes it its own project. Each item below says whether it is a
deliberate deviation or an unstarted migration, because the two are not the
same debt.

### Toolchain — migration status

| Guide | dbqm today | Note |
|---|---|---|
| uv, `uv.lock`, PEP 735 groups | Done | `uv.lock` and `.python-version` are committed. `requirements.txt` does not exist — it was already gone before this migration started, not deleted by it; dependencies live in `pyproject.toml`, untouched by this migration. |
| `uv_build` backend | `setuptools>=68` | Not adopted — `pyproject.toml`'s build backend was out of scope for step 1, which was the lockfile only. |
| ruff (lint + format) | Done | `uvx ruff check .` passes over fifteen rule families, chosen by measuring which the code already passed or nearly passed. This is why `TASK-COMPLETION.md` Step 2 now has a command here (see `AGENTS.md`). `ruff format` is not adopted. |
| mypy `strict = true` | **Pending — its own slice.** | Adoption step 3. Measured at the branch this table was last updated from: **464 findings at `--strict`, 76 at default**. That gap is why a per-module ratchet, not a flag flip, is the only viable way in — see `docs/ROADMAP.md` Tier 2. |
| pytest-cov, coverage floor | no coverage measured | Test count is tracked instead (see `AGENTS.md`). A count is not coverage. |
| pytest strict config | Done | `--strict-markers`, `--strict-config`, `filterwarnings = error`, `xfail_strict` are all set. |
| CI running lint + type gates | Done for lint and tests | `.github/workflows/checks.yml` runs the lint gate and the test suite on pull requests and pushes to `main`. It will run mypy too once step 3 lands; today it is separate from the release workflow. |

### Deliberate deviations

- **`requires-python = ">=3.10"`**, not `>=3.13`. Users install this into whatever
  Python their machine has; a 3.13 floor would exclude most of them. The
  consequence is that **`from __future__ import annotations` is correct here** and
  appears in every module — the guide's instruction to drop it applies from 3.14,
  which this project is years from.
- **Flat layout, not `src/`.** The package is `dbqm/` at the repository root, with
  `pythonpath = ["."]` in `[tool.pytest.ini_options]`. Tests therefore run
  against the working tree, which is the risk the guide names; it is accepted
  rather than fixed because moving the package is a breaking change to every
  import path in a published package for no user-visible gain.
- **argparse, not typer.** The CLI is hand-rolled `argv` dispatch in `cli.py`
  with a `COMMAND_MAP`. It predates the guide, it is covered by ~130 tests, and
  typer would rewrite the whole surface. Revisit only if the CLI is restructured
  for another reason.
- **A hand-maintained `__version__`.** `dbqm/_version.py` holds it and
  `pyproject.toml` reads it via `[tool.setuptools.dynamic]`, which the guide
  forbids in favour of `[project] version` read through `importlib.metadata`.
  The release workflow (`.github/workflows/publish.yml`) guards that the
  pushed tag equals this file, so the two cannot silently diverge.
  `VERSIONING.md`'s "never edit version files manually" is therefore **not**
  satisfied: there is no bump command, the edit is manual, and the tag guard
  is the only thing catching a mistake. This stayed a deliberate deviation
  through the 2.3.1 toolchain slice: that guard mechanism has already
  published 2.0.0 and 2.3.0 without incident, so changing the version source
  now would mean editing a working release pipeline to adopt a convention,
  not fixing a defect.
- **Configuration is JSON files plus plain dataclasses** under `~/.dbqm/`
  (`DBQM_HOME` overrides), not pydantic-settings. There is no `Settings` object
  in the guide's sense, and the domain dataclasses (`Connection`, `Query`,
  `Group`) are **mutable and un-slotted** because they are JSON round-tripped and
  edited in place by the TUI.
- **`print` is used in the CLI alongside the Rich `Console`**, deliberately: a
  machine-readable stream (`-f json|csv|raw`) must never carry Rich markup or
  wrapping, so those paths bypass the console entirely. The guide's "no `print`
  outside the CLI adapter" is satisfied — this *is* the CLI adapter.
- **Exit codes are not yet the guide's contract.** `0` and `130` hold globally;
  `2` (usage / not found / validation) and `3` (`--test` failed) exist only in the
  `connection` group. Everything else exits `1`. The project-wide table is
  backlog item `X1` in `docs/ROADMAP.md`.
- **No pydantic, httpx, hypothesis, SQLAlchemy, Alembic, testcontainers, Docker
  or structlog.** None of those sections apply: dbqm makes no HTTP calls, runs no
  server, and talks to databases through the raw drivers the guide already allows
  as a sub-conditional (`oracledb`, `psycopg`, `pymssql`, `PyMySQL`).

### Where the project already complies

Recorded because it is the part a reader should not "fix":

- **Every rule in "TUI (conditional)" holds**, and two were paid for in
  production: the global error modal with the worker-error route
  (`ui/modals/error.py`), and markup escaping before rendering user text — a
  connection name containing `[` used to raise `MarkupError` from the CLI
  (fixed in 1.22.0, `rich.markup.escape` at every interpolation site).
- **No production code branches on "am I under test."**
- **Keys are handled in `on_key` with `prevent_default()`/`stop()`**, never in
  `key_*`, and `check_action` returns `False` while a modal is on the stack.
- **Widgets never touch a driver**; timestamps and paths are captured in the UI
  and injected so `core/` stays pure (`format_dbms_evidence`).
- **Tests drive the real app** (`async with app.run_test() as pilot`).
- **Release is tag-driven**, per this guide and `VERSIONING.md`: pushing `v*`
  runs `.github/workflows/publish.yml`, which guards tag == `_version.py`, builds,
  and publishes with a CI secret. A manual `twine upload` from a developer
  machine is **not** a release here either.
