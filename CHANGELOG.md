# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Releases before 1.18.0 predate this file; their history is in the git log.

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
