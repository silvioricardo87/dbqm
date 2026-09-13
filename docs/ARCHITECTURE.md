# ARCHITECTURE — how dbqm is built

The structure of the code, the rules that keep it that way, and the debt that is
recorded on purpose. Read this before changing anything under `dbqm/`.

`AGENTS.md` is the canonical instruction file and points here; it carries the
process rules (workflow, commits, versioning, language) and deliberately does
not restate any of this. The README describes what the program *does* for a
user and carries no internal structure at all — it is the package's PyPI page.

> A note on the debt section at the end: entries there were **measured**, and
> several were re-measured and struck through when they stopped reproducing. Read
> the note beside an entry before treating it as a fact about today's code.

---

## Layout and layering

```
dbqm/
├── main.py            # App bootstrap (console-script target: dbqm.main:main)
├── __main__.py        # `python -m dbqm` — routes to CLI or TUI
├── cli/               # Non-interactive CLI (sql, run, run-group, connection, list, ...)
│   ├── __init__.py     # run_cli, build_parser, COMMAND_MAP — the public API
│   ├── deps.py         # What the CLI consumes from core/ and models/, in one place
│   ├── envelope.py     # ok()/fail() — the single JSON shape
│   ├── errors.py       # ExitCode (IntEnum) and the token -> exit-code table
│   ├── render.py       # table / csv / raw output
│   ├── params.py       # _parse_params, resolve_password
│   └── commands/       # One module per group: query, connection, inspect, config_bundle
├── _version.py        # __version__ (SemVer; read by pyproject.toml)
├── design/            # Design tokens (colors, contrast floors); imports nothing from dbqm
│   └── tokens.py       # TOKENS_CLARO / TOKENS_ESCURO / TEMAS, one source for TUI + CLI + HTML report
├── core/              # Business logic (no UI imports)
│   ├── db_manager.py          # Connection dispatcher for all 4 DBs; NLS_LANG=.AL32UTF8; Oracle thick mode;
│   │                          #   open_connection() is the driver-handle lifetime the CLI's
│   │                          #   objects/describe/rows commands hold open across calls
│   ├── query_engine.py        # SQL classification (classify_sql), execution (execute_adhoc/query/explain)
│   ├── group_engine.py        # Multi-connection comparison runs
│   ├── object_browser.py      # Metadata browsing (tables/views/routines) per DB
│   ├── table_browser.py       # Row browsing with FK label resolution + pagination
│   ├── ddl_extractor.py       # Oracle DDL extraction; ddl_pg.py / ddl_mysql.py for PG/MySQL
│   ├── package_editor.py      # PL/SQL package editing helpers
│   ├── template_engine.py     # Parameterized query templates
│   ├── exporter.py            # CSV/JSON/TXT exports + IDE-style DBMS execution evidence
│   ├── html_report.py         # HTML report generation
│   ├── history.py / audit.py  # Execution history and audit log
│   ├── crypto.py              # Fernet password encryption
│   ├── connection_builder.py  # Connection rules: validation, per-engine defaults,
│   │                          #   encryption, create-vs-update. Shared by TUI + CLI
│   ├── config_portability.py  # Import/export of config bundles
│   ├── oracle_client_installer.py  # Oracle Instant Client bootstrap
│   └── paths.py               # CONFIG_DIR / SETTINGS_FILE resolution (honors DBQM_HOME)
├── models/            # Data models with JSON persistence
│   ├── connection.py  # db_type ∈ {oracle, sqlserver, postgresql, mysql}
│   ├── query.py  group.py  settings.py  template.py
└── ui/                # Textual TUI (imports core; core never imports ui)
    ├── app.py         # Main App: single tabbed shell (TabbedContent), routing,
    │                  #   keybindings; `AbasPrincipais` keeps focus from switching tabs
    ├── theme.py  utils.py
    ├── screens/       # One Vertical-widget screen per feature (adhoc, query_exec,
    │                  #   group_exec, group_run, browser, connections, history,
    │                  #   ferramentas, exec_routine, package_editor, settings, ...)
    ├── widgets/       # Reusable components (panel, templates_sidebar, result_table,
    │                  #   action_bar, lista_hierarquica, sql_viewer, status_bar,
    │                  #   progress, dialog, empty_state, veredito, esqueleto, ...)
    └── modals/        # Dialog screens (confirm, param_input, export_picker,
                       #   export_dir_setup, column_maps, error, help, ...)
```

> Note: there is **no `ui/flows/`** — the old Rich/prompt "flow" layer was
> migrated to Textual `screens/`. Ignore any older doc that references flows.

**Layering rule:** `core/` is UI-agnostic and must never import from `ui/`.
Both the TUI (`ui/app.py`) and the CLI (`cli/`) call into `core/`.
`design/` sits below both: it imports nothing from `dbqm`, and is imported by
the TUI (`ui/theme.py`), the CLI (`cli/render.py`), and the HTML report
(`core/html_report.py`) — one source of color/contrast truth for all three
consumers, none of them importing each other.

---

## Key Patterns

### SQL classification (`core/query_engine.py`)
- `classify_sql` returns `SELECT | INSERT | UPDATE | DELETE | DDL | PLSQL | EXPLAIN | UNKNOWN`.
- It classifies **DDL / PL/SQL / EXPLAIN by the leading keyword first**, before
  calling `sqlparse.parse` — this avoids tokenizing multi-thousand-line
  `PACKAGE BODY` sources (wasteful and historically fragile against sqlparse
  token caps). `sqlparse` is only used to disambiguate SELECT vs DML and to
  resolve `WITH` (CTE → SELECT).
- Leading `--` and `/* */` comments are stripped for *classification only*
  (`_strip_leading_comments`); the original text (comments + trailing `/`) is
  what actually runs.
- Anonymous PL/SQL blocks (`DECLARE`/`BEGIN`) and `EXEC`/`EXECUTE`/`CALL`
  shortcuts are supported; `DBMS_OUTPUT` is captured automatically on Oracle.
- DDL keeps its final `;` (stripping it would leave objects INVALID); after DDL,
  compilation errors are fetched and surfaced.

### Textual TUI
- Screens are `Vertical` widgets loaded into `#screen-area`.
- Arrow keys: use `on_key` with `event.prevent_default()`/`event.stop()` — not
  `key_*` methods (which mark events handled even when not acting).
- Modal focus: `app.check_action()` returns `False` when `screen_stack > 1` so
  modal keys aren't intercepted.
- `DataTable` selection: `cursor_type="row"` for `RowSelected` events.
- Keyboard shortcuts inside `TextArea`: use `on_key`, not `BINDINGS` (TextArea
  consumes bindings).

### Select widget
- `Select.value` is `Select.NULL` (a `NoSelection`) when empty; `Select.BLANK`
  is `False`. Check `isinstance(val, str)` to know a real value is selected.

### Database
- Oracle: thick mode via `oracledb.init_oracle_client()`; DSN via
  `oracledb.makedsn()` (SID vs service_name). `NLS_LANG` is forced to
  `.AL32UTF8` so Oracle error messages come back as UTF-8 (correct accents on
  Windows).
- Connection passwords encrypted with **Fernet** (`core/crypto.py`).
- Non-Oracle DBs share pyformat parameter binding.

### Exports & evidence
- Default export dir is `Path.cwd() / "exports"`, **not** `~/.dbqm/exports`.
- Saving/copying DBMS output produces an **IDE-style execution evidence** record
  (`format_dbms_evidence`): executed SQL + connection + date/time + DBMS_OUTPUT +
  outcome. Timestamp is captured in the UI and injected so the exporter stays pure.

### CLI (`cli/`)
- Non-interactive commands: `sql`, `run`, `run-group`, `test`, `list`, `ddl`,
  `history`, `export-config`, `import-config`, `objects`, `describe`, `rows`,
  and the `connection` group.
- `-f/--format`: `table | json | csv | raw` (`raw` prints values without
  decoration — for extracting CLOB/LONG sources cleanly). `test`, `ddl`,
  `export-config` and `import-config` offer `table | json`.
- **Under `-f json`, stdout carries one envelope and nothing else** — no error,
  no progress line, no warning. `envelope.ok()` writes
  `{"ok":true,"command":...,"data":...}` to stdout; `envelope.fail()` writes
  `{"ok":false,"command":...,"error":{"code","message","exit"}}` to **stderr**
  and leaves stdout empty, so a failure never breaks `| jq`. `table`, `csv` and
  `raw` get no envelope: they are for humans and text pipes.
- **`error.code` is a machine token; `error.message` stays Portuguese without
  accents.** A consumer branches on the token, never on the sentence. The token
  is finer than the exit code — `usage`, `not_found` and `validation` all exit
  2 — and `errors.py` holds both in one table so they cannot drift.
- **Exit codes** (`errors.ExitCode`): 0 success, 1 **a bug in dbqm**, 2 usage /
  not found / validation, 3 connection failed, 4 SQL error, 5 divergent
  comparison, 130 interrupted. `run-group` exiting 5 on divergence is what lets
  a script learn that a comparison *ran and diverged* without parsing text.
- **The `core/` dataclasses own their wire shape** (`to_dict()`), so the CLI
  never invents a second one. `rows` are parallel arrays, not objects keyed by
  column: a repeated column name (`SELECT a.id, b.id`) would silently drop a
  value. `tests/core/test_serialization.py` walks `dbqm.core.*` and fails when
  a dataclass that reaches an output has no `to_dict`.
- Example: `python -m dbqm sql "<sql-or-file>" "<connection name>" -f raw`.
- **`connection add|update|rm|show|list`** is the only CRUD reachable outside
  the TUI. It calls `core/connection_builder.py`, never `upsert` — `add` on an
  existing name and `update` on a missing one must be errors, so the command
  checks existence itself and calls `build` + `save_connections`.
  `update` is **partial**: a flag not passed changes nothing.
- **Passwords never come from `argv`.** `resolve_password(args, env_var, prompt,
  *, required, use_env=True)` resolves them from `--password-stdin`, then
  `--password` (only where the command already had it), then the environment
  variable. `getpass` runs **only** when `sys.stdin.isatty()` — on a pipe it
  blocks forever, which is exactly how an agent hangs. Two rules exist because
  each one was a silent credential loss: `connection update` passes
  `use_env=False` (an ambient `DBQM_PASSWORD` is not something the user said on
  *that* command line), and an **empty read** from `--password-stdin` is always
  an error regardless of `required` (a closed pipe would otherwise create a
  passwordless connection, or clear a stored password).
- **User values are escaped before reaching Rich markup** (`rich.markup.escape`).
  A connection name or `--type` value containing `[` used to raise `MarkupError`
  or vanish from the very message meant to show it.
- Exit codes for `connection`: `0` ok, `2` usage / not found / validation,
  `3` `--test` failed. The project-wide code table is still unbuilt (backlog `X1`).

### UI conventions
- Interactive UI labels **intentionally omit accents** (e.g. `Historico`,
  `conexao`, `Nao`). This is deliberate — **do not "fix" them**.

### Language: English in code, Portuguese only on screen

This is not a style preference — it is the line between *what the program is
made of* and *what the user reads*.

**English** — everything that is code, and everything written *about* it:
- identifiers: modules, classes, functions, constants, fixtures, test names
- design token names and the `$var` references to them
- comments and docstrings
- assertion messages in tests
- **commit messages** (subject and body), **pull request titles and bodies**,
  issue titles and bodies, code-review comments, and release notes
- `README.md`, `CHANGELOG.md`, `AGENTS.md` and anything else under `docs/`

**Portuguese, without accents** — everything the user sees:
- widget labels, panel titles, button text, tab names
- notifications, error and confirmation messages
- CLI output text

The test's *assertion messages* follow the code, not the UI: they are read by
whoever the test failed on, never by a user of the program.

**The conversation is exempt.** Talking to the maintainer in Portuguese is
normal and expected — the rule governs what gets written down in the
repository, not how the work is discussed. When a commit message or a comment
needs to quote something the maintainer said, quote it verbatim in Portuguese:
translating a quotation falsifies the record. Everything around the quotation
is still English.

**Why it is written down.** It was never written down before, and it held
anyway — until it didn't. A design-system series added ~370 Portuguese comments,
59 Portuguese docstrings, 34 Portuguese identifiers and 15 Portuguese design
tokens across ~70 commits, and every one of them passed review, because the rule
lived only in the code's own consistency. Before that series `main` had 5
Portuguese comments against 215 English and **zero** Portuguese docstrings
against 406. A convention that strong is easy to break precisely because nobody
ever has to state it.

If you are working in Portuguese with the maintainer, the conversation is not
the codebase. Write the code in English anyway.

## Layout grammar (read before touching `dbqm/ui`)

The TUI has a **grammar**, not a per-screen style. Phase 1 fixed color (15
semantic tokens); phase 2 fixed **structure**. Four questions each screen used
to answer on its own are now answered once, and each answer has a guard in
`tests/design/test_layout_inventory.py`.

**1. What is a section?** `Panel` is the *only* section frame (`Dialog` is its
modal twin). Nothing floats loose on the background, and no screen draws its own
box. A screen taller than the viewport **scrolls** — it never truncates in
silence, which is how the Oracle Instant Client section stayed invisible for
weeks (`tests/design/test_vertical_overflow.py`).

**2. How do you navigate a set?** By **cardinality**, not by taste: up to ~7
fixed items → tabs; a variable number → `Select` with counts; choosable things →
`OptionList` with a 2–3 line hierarchy; tabular data → `DataTable`. `ListView`
is out of the vocabulary — it did the same job as `OptionList`.
A list item is **never a concatenated string**: identity (bold, alone),
disambiguation (indented, `$texto-apoio`), context (indented,
`$texto-desabilitado`, optional). Build it with `item_hierarquico`
(`dbqm/ui/widgets/lista_hierarquica.py`).

**3. How dense is a row?** A **result** table never truncates to fit: key column
pinned (`fixed_columns=1` when there is more than one column), zebra stripes,
horizontal scrolling, and the record mode (`V`) that already existed. The reason
is the domain — dbqm exists to *compare*, and a row whose key scrolled out of
sight compares nothing.

**4. Where do actions live?** Anchored to the panel they operate, left-aligned
with its content; destructive actions separated from the rest. Centring a
cluster only makes sense when the cluster **is** the screen — a dialog. And a
**button is an action, never navigation or a menu**.

### The guards, and how far each one reaches

| Guard | Rejects | Enforcement |
|---|---|---|
| `sem_borda_crua` | `border:`/`outline:` outside `Panel`/`Dialog` | mechanical, 1 written exemption |
| `sem_listview` | any mention of `ListView` in `dbqm/ui` | mechanical, no exemptions |
| `sem_cluster_centralizado` | layout centring outside a dialog | mechanical, 5 written exemptions |
| `rotulo_nao_achatado` | list item built as one flat string | mechanical, 1 written exemption |
| `tabela_com_chave_fixa` | result table (columns built from data) without `fixed_columns` | mechanical, no exemptions |
| `botao_nao_navega` | button handler that switches tab or opens a tool | mechanical, **4 written exemptions** |

`botao_nao_navega` deserves a note, because it is the one whose exemption list is
the interesting part. `EmptyState` requires `acao_rotulo`/`acao_id` — the four
parameters are mandatory so that no empty list is ever a dead end. When the
honest way out of an empty screen lives in another tab, honouring that contract
means navigating. **Four** call-to-actions do it today (`history`, `query_exec`,
`group_run`, `templates_sidebar`); they are listed by button id in
`NAVEGACAO_ISENTA` with the reason. Making the action optional would touch 14
call sites and is a flow change, out of scope for the layout phase. The guard's
job until then is the **ceiling**: the fifth navigating button fails the suite,
and a stale exemption (a CTA that stops navigating) also fails it.

Every textual/AST scan **names its own limits in the code**, and those comments
are load-bearing: a false reason in a comment is worse than no comment, because
the next reader takes it for a verified fact. In short, the scans cannot see
markup built at runtime, values assembled in another layer, CSS declarations
split across two lines, or anything outside `dbqm/ui`. Read the limit block next
to each guard before concluding "the guard is green, so the rule holds".

### Two lessons this phase paid for

- **Assert what renders, not the attribute.** `fixed_columns == 1` can stay set
  while the pinned column stops painting; `_actions` was populated on every
  screen while the ActionBar painted on none (the StatusBar covered it). Tests
  that read attributes stayed green through both. Drive the app, read the
  rendered strips or the exported screenshot (`tests/ui/_helpers.py`:
  `texto_renderizado`, `linhas_renderizadas`, `recorte`).
- **Measure in the state where the defect happens.** A list description was
  sized against `content_region.width` measured on a list too short to scroll;
  the real list has a scrollbar and the fix was two columns off. A screen test
  gave `SettingsScreen` 24 rows when the real app gives it 20. Mount the real
  `DBQMApp`, at the real size, with the data that triggers the bug.

### Known debt, recorded on purpose (not fixed here)

> Struck-through entries were re-measured and either fixed or found not to
> reproduce; the note on each says which, and what was measured. They stay
> visible on purpose — a debt entry that quietly disappears teaches the next
> reader nothing about why it was there.

- **`Connection.windows_auth` is dead code.** Declared at
  `models/connection.py:26` and never read or written anywhere in `dbqm/`. The
  TUI form has no widget for it and the CLI has no flag, so SQL Server Windows
  authentication is unreachable despite the field advertising it. Either
  implement it (form field, CLI flag, and the call in
  `get_sqlserver_connection`) or delete the field.
- **The TUI cannot clear a password.** A blank field means "keep the stored
  one" — there is no equivalent of the CLI's `--no-password`. Long-standing, not
  a regression: the screen has behaved this way since before the rules moved to
  `core/connection_builder.py`. A whitespace-only field is also treated as
  blank, deliberately (the presence test strips; the value does not).
- **PNG export is unreachable.** `ExportPickerModal` accepts `include_png` and
  renders a PNG button, but **no caller passes `include_png=True`**, and
  `Pillow` is not in `pyproject.toml` at all. The README claimed both the format
  and the dependency; both claims are now removed. Either wire it up with the
  dependency or delete the parameter and the button.

- ~~On startup (Coleta tab) the ActionBar paints **Conexoes'** actions.~~ **Does not
  reproduce.** Re-measured 9/9 (3 sizes x 3 repeats, config with one connection;
  same result with and without the tab-focus fix): on Coleta the bar is **empty**.
  `AdhocScreen` exposes neither `_set_actions` nor `_set_list_actions`, so
  `on_tabbed_content_tab_activated` clears the bar — which is what the code says.
  With an **empty** config the app opens on Conexoes and shows Conexoes' actions,
  which is right. What remains is a smaller, different thing: the tab that hosts
  the SQL editor announces no action at all until the first execution.
- ~~Every app mount fires a spurious `Subdiretorios por tipo: ativado` toast.~~
  **Fixed** — and there were three, not one. `on_switch_changed` /
  `on_select_changed` now return early when the incoming value already equals the
  stored one. The three: export subdirs on every launch; audit log on every launch
  for anyone with `audit_log_enabled` on; and `Tema alterado: plano-escuro` on the
  first launch after upgrading from 1.17.x — that one was the `github-dark` ->
  `plano-escuro` **rename** announcing itself as a user's choice. Each also
  rewrote `settings.json` (measured: 1 write with a fresh config, 2 with audit on).
- ~~The two Oracle Instant Client tests read the **live user config**.~~
  **Fixed.** An autouse fixture points `dbqm.models.settings.SETTINGS_FILE` at an
  empty temp file for that class. Reproduced first: with `oracle_client_dir`
  populated, `_find_oracle_client_dir` returned the configured path instead of
  either seeded fixture directory. Verified after: the file passes both with the
  setting empty and with it populated via `DBQM_HOME`.
- ~~`Breadcrumb` is **fully dead** and every call raises into a bare `except`.~~
  **Fixed.** The widget, its export and the `package_editor` call site are all
  deleted.
- The connection checklist in `group_exec` is the one flat list label left.
  `SelectionList` paints **only the first line** of a prompt (measured), so
  applying `item_hierarquico` there would delete the target instead of
  clarifying it; the real fix is a different widget.
- ~~`test_f_keys_switch_tabs` / `test_clients_manager_opens_in_a_titled_panel`
  are timing-sensitive under load.~~ **Fixed at the root** — it was not a flaky
  test, it was stock `TabbedContent` treating FOCUS as NAVIGATION
  (`_on_tab_pane_focused` -> `self.active = pane.id`). Since every screen schedules
  its own initial focus, the previous screen's late focus undid the tab switch.
  `AbasPrincipais` (`ui/app.py`) kills the message with `prevent_default()` —
  `stop()` alone is not enough, because Textual dispatches the same message to the
  handler of EVERY class in the MRO (measured: `stop()` changed nothing). Covered
  by `test_focus_in_an_inactive_pane_does_not_switch_tabs` and
  `test_function_key_at_startup_reaches_the_requested_tab`, both of which fail
  deterministically without the fix with the flake's own message
  (`assert 'tab-conexoes' == 'tab-historico'`).
- Fixed-schema tables (`history`, `query_manage`, `template_manage`, …) are out
  of `tabela_com_chave_fixa` by design. The spec's line about giving `history`
  a pinned key and zebra was never implemented; zebra there would blend the
  `marcar_veredito` cells at runtime, invisible to the contrast guard.
- ~~**`history` starves vertically.**~~ **Fixed.** The list panel now takes `2fr`
  against the detail's `1fr` (min 4, max 9). Measured inside the real DBQMApp:
  the table viewport went from **3 rows to 5** at 80x24, and from a 9-row detail
  to 19 table rows at 120x40. A bare harness reported a nine-row viewport for
  the broken layout, which is why it survived — `tests/ui/test_screens.py`
  now measures in the real app.
- **Downgrading the theme breaks 1.17.x, and cannot be fixed from here.** That
  version met `plano-escuro`, did not know the name and raised
  `InvalidThemeError` before the first screen. Recovery is hand-editing one key;
  data and the Fernet key stay readable. What *was* fixed is the class of
  failure going forward: `get_theme` falls back to the default for any unknown
  name, and `test_app_starts_when_settings_name_a_theme_it_does_not_know` proves
  the app boots end to end rather than only unit-testing the fallback.
- ~~**Guard 6 has an `elif`-chain hole.**~~ **Fixed.** `_branch_ids` now skips the
  test of any `If` whose `orelse` it climbed out of — that test governs the branch
  above, not this one — which closes the chain without losing genuinely nested
  handlers. Break-tested both ways: the `elif "zzz-fuga"` beside the exempt
  `"executar-consulta"` in `history.py` escaped before and fails now.
- **Guard 6 accepts the string literal `"action_switch_tab"` as proof of
  navigation.** That is the form the four real CTAs use
  (`getattr(self.app, "action_switch_tab", None)`), but it means gutting the call
  while keeping the `getattr` leaves the guard green with a silent CTA — it proves
  the NAME is written there, not that navigation happens.
- ~~**The tab strip breaks decision 2 of the grammar.**~~ **Closed as not
  applicable — the premise was rejected.** The complaint measured the strip at
  80 columns and found it cut at `⚙️  Confi`, hiding Consultas and Ferramentas.
  The maintainer's ruling: *"deixa como está mesmo, não pretendo trabalhar com
  80 colunas, as resoluções atuais são bem maiores, nem faz sentido se
  preocupar com 80 colunas."* At the widths actually used, all eight labels
  render whole — verified at 120 and 140 columns.

  Two attempts are recorded so they are not repeated. Dropping the emoji and
  shortening two names was the only one of four measured variants that fit at
  80 columns, and it was rejected: the emoji are identity, not decoration.
  Collapsing inactive labels to the emoji alone was prototyped and shown; it
  works, but it trades seven tab names for icons and still leaves eight tabs
  where the grammar asks for about seven.

  **What this decision reaches beyond one bug:** several guards and debt entries
  in this file are calibrated to 80x24 as the reference size. If 80 columns is
  not a target, that calibration is worth revisiting deliberately rather than
  drifting — it is the baseline `tests/design/test_vertical_overflow.py` and the
  history measurement both assume.
- **Two vocabularies for the action row.** `adhoc` uses auto-width buttons anchored
  left; `connections` uses full-width buttons with centred labels — byte for byte
  the "full-width buttons pretending to be a menu" that §7 criticises. It escapes
  the guard because `text-align` is out of the guard's scope.
