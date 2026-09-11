# Semantic Versioning Guidelines

This document defines how to apply [Semantic Versioning 2.0.0](https://semver.org/) in any project that consumes this skill. It is consumed at **Step 5** of the cycle defined in `TASK-COMPLETION.md`.

This document defines **which level** to bump. It does not define **how** to apply the bump — that is the responsibility of the stack documentation of the consuming project.

## Version Format

```
MAJOR.MINOR.PATCH
```

See [semver.org](https://semver.org/) for the full specification.

## Version Mechanism Requirement

- The consuming project MUST have a version mechanism configured before the first task-completion cycle runs.
- The concrete mechanism (which file holds the version, which command applies the bump) is defined by the stack documentation of the project.
- This document is stack-agnostic and intentionally contains no commands.
- Version files must never be edited manually. Always use the mechanism declared by the stack doc.
- If no mechanism exists, the cycle fails at Step 5 of `TASK-COMPLETION.md` and the mechanism must be created before any cycle can run.

## Version Increment Rules

### MAJOR (`X.0.0`) — Breaking Changes

Increment `MAJOR` when changes are **incompatible** with the previous version. After incrementing, reset `MINOR` and `PATCH` to `0`.

When to use:

- Removing or renaming existing features, pages, or routes.
- Changing a database schema in a way that breaks existing data (dropping or renaming columns or tables).
- Removing or changing a public API contract.
- Changing authentication or authorization in a breaking way.
- Dropping support for a platform, runtime, or client.
- Migrating to a fundamentally different technology stack.
- Any change that requires existing users to take action (re-login, reconfigure, migrate data).

### MINOR (`x.Y.0`) — New Features (backwards-compatible)

Increment `MINOR` when adding **new functionality** that does not break existing behavior. After incrementing, reset `PATCH` to `0`.

When to use:

- Adding a new feature, view, or page.
- Adding a new UI component or screen.
- Adding new non-breaking fields to forms or database tables.
- Adding a new integration.
- Adding new internationalization keys.
- Adding new shared or reusable components.
- Significant enhancements to existing features that add new capability.
- Adding new hooks, services, or utilities.
- Refactoring that restructures multiple files or modules (extracting components from a large file, reorganizing folders).
- Large-scale code reorganization even when functionality is unchanged.

### PATCH (`x.y.Z`) — Bug Fixes and Minor Improvements

Increment `PATCH` for **bug fixes** and small improvements that neither add new features nor break existing ones.

When to use:

- Fixing a bug (incorrect behavior, crash, data error).
- Fixing typos in user-facing text or translations.
- Fixing styling or layout issues.
- Performance optimizations that do not change behavior.
- Small UI adjustments (spacing, color, alignment).
- Updating dependencies to compatible versions.
- Fixing lint errors or code-quality issues.
- Refactors contained within a single file.
- Correcting validation rules.
- Fixing accessibility issues.

## Decision Flowchart

Follow this sequence to determine the correct bump level:

```
1. Does the change break existing functionality or require user action?
   YES → MAJOR
   NO  → continue

2. Does the change add new features or capabilities?
   YES → MINOR
   NO  → continue

3. Does the change restructure or reorganize multiple files or modules?
   YES → MINOR
   NO  → continue

4. Does the change fix a bug or make a small improvement?
   YES → PATCH
   NO  → PATCH (default safe choice)
```

## Relationship to Commit Types

Each commit type defined in `COMMITS.md` maps to a default bump level. This mapping is the single source of truth and is mirrored in `COMMITS.md` so both files stay self-contained.

| Commit Type | Default Bump | Condition for another level       |
|-------------|--------------|-----------------------------------|
| `Add`       | MINOR        | MAJOR if the addition is breaking |
| `Update`    | PATCH        | MINOR if it adds new capability   |
| `Fix`       | PATCH        | —                                 |
| `Refactor`  | PATCH        | MINOR if multi-file or structural |
| `Enhance`   | PATCH        | MINOR if it adds new capability   |
| `Remove`    | PATCH        | MAJOR if removing a public API or user-visible feature |
| `Merge`     | —            | Inherits from the merged commits  |

**Precedence rule:** when a task includes mixed-level changes, always pick the **highest** applicable level.

## Rules

1. Exactly one bump per completed task, applied at Step 5 of `TASK-COMPLETION.md`.
2. On mixed changes, pick the highest applicable level.
3. When unsure between `PATCH` and `MINOR`, use `PATCH`.
4. When unsure between `MINOR` and `MAJOR`, ask the user. Do not guess.
5. Never edit version files manually — always use the mechanism declared by the stack doc.
6. Never skip the bump because "the change is small". Bug fixes are `PATCH`, not nothing.
7. Never bump before a successful build, lint, and test (Steps 1 through 3 of `TASK-COMPLETION.md`).

## Examples

| Change                                                    | Bump  |
|-----------------------------------------------------------|-------|
| Add dark mode toggle to settings                          | MINOR |
| Fix currency format showing wrong decimals                | PATCH |
| Remove legacy migration code (users must re-sync)         | MAJOR |
| Add Kanban board feature                                  | MINOR |
| Fix button alignment on mobile                            | PATCH |
| Refactor large list component into five smaller ones      | MINOR |
| Fix typo in a translation file                            | PATCH |
| Add a new list type to a list-management feature          | MINOR |
| Fix race condition in a real-time subscription            | PATCH |
| Change authentication from email to OAuth only            | MAJOR |
| Optimize list rendering performance                       | PATCH |
| Extract shared hooks from feature modules                 | MINOR |
| Remove a public endpoint from the API                     | MAJOR |
| Update a dependency to a compatible version               | PATCH |

## Release Flow

Bumping the version (Step 5) and releasing are different events. A release is the moment a tagged version reaches users — a store, a registry, a deployment target. These rules keep the two apart and keep the release honest. They are stack-agnostic; the project's CI configuration implements them.

- **A release is driven by a tag, in its own pipeline.** Store and registry releases live in a dedicated workflow triggered by version tags (`vX.Y.Z`) and manual dispatch only. Nothing is built or published because a version-bump commit was merged.
- **The release workflow carries no path filter.** CI systems apply push path filters to tag pushes too, and a tag on an already-pushed commit carries no changed files — a filtered workflow is silently skipped and the release never happens. Path filters belong to the regular pipeline, never to the release one.
- **A green job is not a shipped release.** When a job only hands off to, or polls, an external build system (a store build service, a cloud native build), the job's own status proves nothing. The job asserts the external system's terminal status — complete *and* succeeded — and fails otherwise.
- **Runner selection has a fallback.** If the project uses a self-hosted runner, the workflow detects whether it is online and falls back to a hosted runner when it is not. A release never waits on a machine that happens to be off.
- **Build numbers are derived, monotonic and never hand-edited.** The build code native platforms require (Android `versionCode`, iOS build number) is computed — minutes since a fixed epoch, or the store's latest plus one — not maintained by hand. The user-facing version (`MAJOR.MINOR.PATCH`) lives in one file (`package.json` or the stack's equivalent) and a script every native build runs copies it into the native version files. Two sources for one version is how they diverge.

## See Also

- `TASK-COMPLETION.md` — Orchestrator that consumes this document at Step 5.
- `COMMITS.md` — Commit type definitions and the mirrored mapping table.
- Stack documentation of the consuming project — Concrete mechanism for applying the bump.

## Deviations in this project

- **"Version files must never be edited manually" is not satisfied.** dbqm has no
  bump command: `dbqm/_version.py` is edited by hand and `pyproject.toml` reads it
  through `[tool.setuptools.dynamic]`. The compensating control is the release
  workflow, which refuses to publish when the pushed `v*` tag does not equal that
  file. Adopting uv would bring `uv version --bump`, and this deviation would go
  with it (see `BACKEND-PYTHON.md`).
- **The release flow is otherwise exactly as prescribed**: tag-driven, the
  pipeline guards tag == version, and no release comes from a developer machine.
