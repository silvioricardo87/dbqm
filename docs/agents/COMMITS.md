# Git Commit Instructions

This document defines the mandatory format for commit messages in projects that consume this guide. It is consumed at **Step 6** of `TASK-COMPLETION.md` and adopts [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/).

## Commit Message Format

```
<type>(<scope>)!: <description>

[optional body]

[optional footer(s)]
```

The type and description are required. The scope and `!` are optional; `!` marks a breaking change. Use a colon and one space before the description. Separate the body and footers from the preceding section with a blank line. Use the body to explain why and record verification evidence when the subject cannot carry it.

Choose one lowercase type for the primary intent:

| Type | Use |
|---|---|
| `feat` | A new capability or a backwards-compatible enhancement that adds capability. |
| `fix` | A correction of incorrect behavior. |
| `perf` | A performance improvement without new capability. |
| `refactor` | Internal restructuring without a behavior change, including simplification. |
| `docs` | Documentation-only changes, including additions and deletions. |
| `test` | Test-only changes. |
| `build` | Build system or dependency changes. |
| `ci` | Continuous integration or delivery configuration. |
| `chore` | Maintenance that fits no more specific type. |
| `revert` | Revert an earlier change; explain what is reverted and why in the body. |

These additional types are project conventions permitted by the specification; `feat` and `fix` have the meanings specified there. A branch prefix and a commit type describe different things: for example, a `feature/` branch may contain a `docs` commit. Automated merge commits may retain the hosting tool's generated message; manually authored work commits follow this format. Do not rewrite existing history to conform.

## Scope and Description

- A scope identifies the affected area, such as `auth`, `api` or `build`; use lowercase ASCII words separated by hyphens. Omit it when no single area is useful.
- Describe what changed in the imperative mood. Explain why in the subject when concise, or in the body when needed. Avoid vague subjects, personal pronouns, emojis, a trailing period, WIP markers and unrelated changes.
- Aim for 50–100 characters in the subject. Use code and configuration identifiers precisely, wrapped in backticks where helpful.
- One commit represents one logical change and one type. Related changes may share a commit; split unrelated changes into separate cycles.

Examples:

```
feat(auth): add email sign-in
fix(api): reject expired credentials
refactor(cache): extract eviction policy
docs(workflow): define branch naming rules
ci: cache dependencies between builds
```

## Breaking Changes

Indicate an incompatible change with `!` before the colon and a `BREAKING CHANGE:` footer describing the impact and required migration. The footer is required by this guide even though the specification permits `!` alone. The bump follows the hard gate and initial-development policy in `VERSIONING.md`, regardless of type.

```
refactor(api)!: replace the legacy endpoint

BREAKING CHANGE: Clients must migrate to the new endpoint.
```

## Language

Type tokens and scopes remain lowercase English. Choose the language of the description, body and footer text by this cascade, stopping at the first clear answer:

1. Predominant language in the last 20 commits.
2. Issue and pull-request labels.
3. Main application documentation (`README`, `CLAUDE.md`, `AGENTS.md`, or equivalent).
4. English as the fallback.

Keep that language consistent within the repository. The `BREAKING CHANGE:` token remains uppercase English as required by the specification.

## Versioning and Completion

`VERSIONING.md` decides the bump at Step 5 from the actual change, including project-specific rules that may differ from release tooling defaults. In general `feat` corresponds to MINOR and `fix` to PATCH; a breaking change requires MAJOR for stable versions, subject to the guide's `0.y.z` policy. Other types do not imply a bump under Conventional Commits itself; this project's completion rules may still require one. Do not infer a release solely from the prefix or enable automated release rules without reconciling them with `VERSIONING.md`.

A work commit follows successful build, lint, test, documentation sync and version bump, except for the closed exceptions in `TASK-COMPLETION.md`. For documentation-only, CI/CD-only or dev-tooling-only work, choose the appropriate type above; the exception waives Steps 1–5, not message rules.

Do not include the version generated at Step 5 in the message. The release-changelog commit (`docs(changelog): release X.Y.Z`) is the exception: the version is what it records. Never include co-authorship, attribution, or mention of AI agents, assistants or automated tools in commit messages, PR titles or PR descriptions.

## See Also

- `TASK-COMPLETION.md` — Orchestrator that consumes this document at Step 6.
- `AGENT-WORKFLOW.md` — Operating discipline before and during the change.
- `AUTONOMOUS-EXECUTION.md` — The unsupervised mode, whose per-slice commit follows these rules.
- `VERSIONING.md` — Source of truth for bump-level rules.
## Deviations in this project

- **Scopes, when used, are a closed set**: `ui`, `core`, `models`, `config`,
  `web`, `mcp` (for `dbqm/mcp/**`, `tests/mcp/**`, `docs/MCP.md`). They map to the directories in
  `docs/ARCHITECTURE.md`. Omit the scope when no single area fits. For example,
  the release-changelog subject is `docs: release X.Y.Z` here.
- **The language cascade resolves to English**, and dbqm states the rule
  explicitly rather than leaving it to inference: identifiers, comments,
  docstrings, test names, assertion messages, commit messages, PR titles and
  bodies, everything under `docs/`, **and what a user reads on screen**.
  Screen text is not written in a widget at all: it lives in `dbqm/i18n/en.py`
  and is reached through `t("key")`. Portuguese is a translation, in
  `dbqm/i18n/pt.py`, still without accents. The full rule is in `AGENTS.md`.
- **Conversation with the maintainer happens in Portuguese** and is exempt —
  the rule governs what gets written into the repository, not how the work is
  discussed. A commit quoting something the maintainer said quotes it verbatim
  in Portuguese; the prose around it stays English.
