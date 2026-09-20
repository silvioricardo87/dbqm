# CLAUDE.md

**See [AGENTS.md](./AGENTS.md).** It is the single source of truth for AI agents
working on dbqm — project overview, architecture, mandatory development workflow,
commit/versioning conventions, testing, key patterns, git policy, and PyPI
publishing all live there.

Read AGENTS.md before making any change and follow it exactly; those
instructions OVERRIDE default behavior.

## Non-negotiables (full detail in AGENTS.md)

- Follow the mandatory workflow after every change: **build → tests → version
  bump → README → commit → push → PyPI**. Never skip a step; never commit with
  failing tests.
- **Conventional Commits**; scopes `ui|core|models|config|web|mcp`. **Never** include
  AI `Co-Authored-By` / AI-attribution lines.
- **Never commit** AI plans/PRDs/planning docs. `docs/plans/` (incl. `BACKLOG.md`),
  `PRD.md`, `.claude/` are gitignored; `AGENTS.md`/`CLAUDE.md`/agent configs are allowed.
- **No screen text in a widget.** Every string a user reads comes from
  `dbqm/i18n/` through `t("key")` — see "Screen text" in AGENTS.md.
  Portuguese labels **intentionally omit accents**; do not "fix" them.
- **English everywhere in the repo** — identifiers, comments, docstrings,
  commit messages, PR titles and bodies, docs, and the source language of
  the catalogue. Talking to the maintainer in Portuguese is fine; that is
  conversation, not the repo.
- Windows-first, **no WSL**.
