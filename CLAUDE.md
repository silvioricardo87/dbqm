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
- **Conventional Commits**; scopes `ui|core|models|config|web`. **Never** include
  AI `Co-Authored-By` / AI-attribution lines.
- **Never commit** AI plans/PRDs/planning docs. `docs/plans/` (incl. `BACKLOG.md`),
  `PRD.md`, `.claude/` are gitignored; `AGENTS.md`/`CLAUDE.md`/agent configs are allowed.
- UI labels **intentionally omit accents** — do not "fix" them.
- **English in code and in writing about it** — identifiers, comments,
  docstrings, commit messages, PR titles and bodies, docs. **Portuguese only
  for what the user reads on screen** (and there, without accents). Talking to
  the maintainer in Portuguese is fine; that is conversation, not the repo.
- Windows-first, **no WSL**.
