# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Releases before 1.18.0 predate this file; their history is in the git log.

## [1.23.0] — 2026-09-12

### Added

- **A password can now be cleared from the TUI.** Until now a blank field meant
  "keep the stored one", so the screen could change a password but never remove
  one — the CLI had `--no-password` and the form had no equivalent. No new
  widget was needed: loading a connection already decrypts its password into
  the field, so the box shows what is stored and emptying it means emptying it.
  Two cases keep their old meaning, because there the box is not showing that
  connection: typing an existing name into a blank form, and a stored password
  that will not decrypt. Neither is wiped by a save.

### Fixed

- **The release workflow no longer runs on Node 20.** `actions/checkout` and
  `actions/setup-python` are on `@v7`; both were being forced onto Node 24 with
  a deprecation warning.
- **The empty-stdin error no longer names a flag the command lacks.** It pointed
  every caller at `--no-password`, which `export-config` and `import-config` do
  not have. The hint is derived from the parser now.

## [1.22.2] — 2026-09-11

Nine of the ten open bugs, closed in one pass. No new commands; no behaviour
change to any command that already worked.

### Fixed

- **SQL Server ad-hoc execution, broken two ways and silent about both.**
  `EXEC`/`EXECUTE`/`CALL` was rewritten into Oracle PL/SQL for every engine, so
  `EXEC dbo.PROC @p='1'` reached SQL Server as `BEGIN dbo.PROC @p='1'; END;` —
  the reason the driver answered `Incorrect syntax near 'dbo'`. And a T-SQL
  batch's result sets were never read, so a batch ending in `SELECT @n, @m`
  printed only `Bloco PL/SQL executado` and dropped the answer. Both are now
  engine-aware, and the outcome is labelled in the dialect that ran it.
  Verified against a real SQL Server, with Oracle re-checked in the same pass.
- **A connection saved without a password no longer fails with an empty
  message.** `decrypt("")` returns `""`; `str(InvalidToken())` is the empty
  string, which reached the user as `Erro ao conectar:` and nothing else. A
  stored password that will not decrypt now names `.dbqm_key` and the command
  that repairs it.
- **The history list gets the room the detail panel was taking.** At 80x24 the
  table had a three-row viewport — 2 of 30 entries visible. Measured in the
  real app: now five rows there, and 19 against a 9-row detail at 120x40.
- **The result-set walk is bounded**, so a driver that never reports the end
  cannot hang the process.

### Removed

- **`Breadcrumb`** — zero instances anywhere, while `package_editor` queried it
  on every package open and every call raised into a bare `except`.
- **PNG export** — unreachable by construction: every call site disabled it,
  no writer survived the removal of the Rich UI layer, and `Pillow` is in no
  dependency list.
- **`Connection.windows_auth`** — never read or written, and unreachable
  anyway: `pymssql` takes no trusted-connection parameter. An older
  `connections.json` carrying the key still loads.

### Internal

- Two Oracle Instant Client tests read the developer's real `~/.dbqm` and
  failed on any machine that set `oracle_client_dir`; they are isolated now.
- The navigating-button layout guard had an `if/elif` hole that let a branch
  inherit a sibling's exemption in silence. Closed, and break-tested both ways.
- The app is proven to boot when `settings.json` names a theme it does not
  know — the failure class that made a 1.17.x rollback fail.

## [1.22.1] — 2026-09-10

### Added

- **`PYPI.md`** — a short, audience-specific page for PyPI, now the package's
  `long_description`. `README.md` stays the repository's page on GitHub. Every
  link in `PYPI.md` is an absolute GitHub URL, because PyPI does not resolve
  relative links.
- **`docs/ARCHITECTURE.md`** and **`docs/ROADMAP.md`** — the architecture
  reference and the prioritised backlog, split out of `AGENTS.md`, which had
  grown to three documents in one. The roadmap puts bugs in a tier above every
  feature.
- **`docs/agents/`** — the shared house guides (agent workflow, task completion,
  Python standards, versioning, commits), copied byte-identical to their source
  up to a `## Deviations in this project` heading, so `diff` remains a working
  drift check.
- **`.gitattributes`** normalising the repository to LF, without which that drift
  check reports differences on line endings alone.

### Fixed

- **A whitespace-only password field in the TUI keeps the stored password**
  instead of overwriting it with whitespace.
- **README corrections** that were public on PyPI: `pip install dbqm` was
  documented nowhere, `dbqm run --param1 value1` is not a flag that has ever
  existed (it is `-p CHAVE=VALOR`), and `Pillow` was listed as a dependency that
  is in no dependency list and imported nowhere. The `Author` metadata read
  "Ricardo" and is now "Silvio Chagas".

## [1.22.0] — 2026-09-10

Connections can now be created and edited from the CLI, without opening the TUI.

### Added

- **`dbqm connection` command group** — `add`, `update`, `rm`, `show` and `list`
  manage connections non-interactively, for scripts, CI and AI agents. `add`
  refuses a duplicate name; `update` changes only the flags you pass and leaves
  the rest as they were; `rm` requires `--yes` when there is no terminal to
  confirm against; `show` never prints the password.
- **Non-interactive passwords** — `--password-stdin` and the `DBQM_PASSWORD`
  environment variable read a connection password without it ever appearing in
  argv or shell history. `export-config` and `import-config` gained the same
  `--password-stdin` and a `DBQM_BUNDLE_PASSWORD` environment variable, so
  neither blocks waiting on a prompt when run without a terminal.
- **`--test`** on `connection add`/`update` tries the connection before saving
  it and refuses to save one that does not answer.

### Changed

- **Connection validation, per-engine defaults and encryption** moved out of
  the TUI's connections screen into `core/connection_builder.py`, a UI-agnostic
  module the CLI now shares with it — both front ends validate and default
  identically instead of each carrying its own copy of the rules.

### Fixed

- **`connection update` no longer reads `DBQM_PASSWORD`** — only
  `--password-stdin` or `--no-password`, given on that command line, change
  the stored password; an ambient environment variable left over from another
  command could otherwise silently replace it.
- **An empty `--password-stdin` read is now always an error** (exit 2, with a
  message pointing at `--no-password`) instead of creating a passwordless
  connection on `add` or silently clearing the stored password on `update`.
- **User-supplied values are escaped before reaching Rich markup**, so a
  connection name, query/group name or bad `--type` value containing `[` or
  `]` can no longer crash the command with a `MarkupError` or vanish from the
  error message it was meant to appear in.
- **A bare `dbqm connection` now prints the command group's help** and exits
  2, instead of a one-line usage reminder.
- **`connection rm` cancellation now respects `-f json`**, emitting
  `{"name": ..., "removed": false}` instead of the plain-text `Cancelado.`,
  which broke JSON consumers.
- **`connection add` validates before asking for a password**, so a bad
  `--type` or missing required field is reported before a terminal user is
  prompted to type a secret.
- **A whitespace-only password field in the TUI keeps the stored password**
  again, instead of overwriting it with whitespace. Moving the rules into
  `core/connection_builder.py` also stopped the screen stripping that field —
  correct for a password that legitimately ends in a space, wrong for one that
  is nothing but spaces. The presence test now strips; the value still does
  not.

## [1.21.0] — 2026-08-23

Structure is now decided once for the whole TUI instead of per screen.

### Added

- **Layout grammar** — four decisions applied across every screen: `Panel` is the
  only section frame and a screen taller than the terminal scrolls instead of
  truncating in silence; navigation follows cardinality (tabs → `Select` with
  counts → `OptionList` → `DataTable`, with `ListView` removed from the
  vocabulary); a list item is a 2–3 line hierarchy (identity / disambiguation /
  context) instead of a concatenated string; a result table pins its key column,
  stripes its rows and scrolls sideways rather than truncating.
- **Six repo-wide guards** (`tests/design/test_inventario_layout.py`) enforcing
  the grammar. Each was verified by breaking the rule it protects, and each
  documents in code what it cannot see.
- Loading skeleton for result tables, shaped from the real median query.

### Changed

- **Settings** is now one `Panel` per subject (theme, audit, export, Oracle
  Instant Client, more settings, Fernet key) in two independently scrolling
  columns, replacing a single panel with centred button clusters.
- **Query and group folders** are a `Select` carrying a per-folder count instead
  of a horizontally scrolling tab bar, which did not scale past a handful of
  folders. The shared folder prefix is elided dynamically, so the full path
  returns on its own the day a second folder family appears.
- **Button menus became lists** in Ferramentas and Export/Import — a button is an
  action, never navigation. Back is `Esc`, announced in the action bar.
- Actions are anchored to the panel they operate on, with destructive ones set
  apart, instead of being centred in the middle of a working screen.
- Long paths in Settings are elided in the middle, keeping root and leaf.

### Fixed

- **Three screens were unreachable since 1.17.0.** Export/Import configuration,
  the Oracle Instant Client manager, and Export/Import's own "Voltar" all queried
  a container removed in the tabbed-shell rewrite, so each reported an error and
  opened nothing.
- **The action bar never rendered anywhere in the app.** It and the status bar
  both docked to the bottom edge, and the status bar painted over the action
  bar's text row — so every screen's contextual shortcuts were registered and
  invisible.
- **Focus could change the active tab.** Textual's `TabbedContent` treats a pane
  focus as navigation, so a screen's deferred initial focus undid the user's tab
  switch, including on an already-hidden pane. This also swallowed function keys
  pressed during startup.
- **Connection, query and group lists** no longer run a wrapped description into
  the identity column, where the eye cannot tell a continuation from the next
  entry.
- Two queries or groups sharing a name no longer crash their screen on mount.
- Opening the app no longer emits toasts for settings the user did not touch, nor
  rewrites `settings.json` unprompted. Upgrading from 1.17.x no longer reports
  "Tema alterado" for what is only an internal rename.
- The Oracle "Client em uso" label now follows the client you just chose.
- Empty history no longer shows an empty table's headers beside its empty state.

## [1.20.0] — 2026-08-22

### Added

- **Shared components**, each the single implementation for its job across the
  TUI: `Dialog` (floating-layer chrome, replacing 29 copied frames), `EmptyState`
  (mandatory what / why / first action), `Veredito` and `StatusOperacao`
  (match / diff / absent plus operation-result markup), and `Esqueleto` (loading
  skeleton and distinct disabled and read-only states).
- Component-inventory guards preventing a second hand-rolled copy of any of them.

### Changed

- Group comparison tables carry the verdict colour instead of plain text.

## [1.19.0] — 2026-08-22

### Added

- **"Plano" design system** — 15 semantic colour tokens (surfaces, text, borda,
  identidade, and a verdict axis for OK / DIFF / AUSENTE) in
  `dbqm/design/tokens.py`, shared by the Textual TUI, the Rich-based CLI output
  and the HTML report CSS, so all three stay visually consistent.
- WCAG contrast checking against every surface a token declares as valid, with no
  known debt. Known gap outside that check: Textual's built-in `$text-muted` and
  Rich's `[dim]` sit outside the token layer.
- A literal-colour scan with a ceiling that only ever decreases; it now sits at
  zero.

### Changed

- Dark and light themes were repainted on the token layer. `github-dark` and
  `github-light` were renamed to `plano-escuro` and `plano-claro`; a legacy map
  migrates the saved setting on first launch.
- HTML report badges and row highlights use a border and marker rather than a
  fill, so text keeps its contrast.

## [1.18.0] — 2026-08-22

### Added

- **Oracle Instant Client path in settings.** The client directory is now
  resolved from dbqm's own configuration rather than the system `ORACLE_HOME`,
  and the resolved path, its origin and its architecture are shown in Settings.

### Fixed

- Connections failing for users with an old PL/SQL Developer, whose 32-bit
  Instant Client was set as the system `ORACLE_HOME` while dbqm requires 64-bit.
  Architecture is validated up front and a mismatch is reported plainly instead
  of surfacing as an opaque driver error.
