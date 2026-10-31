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

Assess the change against the project's declared public contract and the
last released version or another explicitly designated compatibility baseline.
Also compare the state immediately before this task with its result: do not
attribute an earlier, already-versioned break to every subsequent task. When
several unreleased changes ship together, evaluate their combined impact
against the release baseline as well as each task's own bump.
The contract can include documented APIs, CLI behavior, supported platforms,
persisted data, configuration and user-facing behavior that the project
promises to preserve. An internal implementation detail is not automatically
public. Identify the actual consumers and promises from documentation, code,
tests and release history; do not invent a contract or assume there are no
consumers merely because none are visible in this repository.

### MAJOR (`X.0.0`) — Breaking Changes

For a stable version (`X >= 1`), increment `MAJOR` when the change is
**backwards-incompatible with a public contract**. After incrementing, reset
`MINOR` and `PATCH` to `0`. A small change that breaks a contract still requires
MAJOR; size does not determine compatibility.

Examples, when an existing supported consumer is actually affected:

- Removing or renaming a supported feature, route, endpoint or public API.
- Changing stored data or a database contract without a compatible migration.
- Changing authentication or authorization in a breaking way.
- Dropping support for a platform, runtime, or client.
- Adding a required input or removing a previously accepted input.

### MAJOR hard gate

Before proposing or applying MAJOR for a stable version, record the following
in the task's reviewable evidence (such as its report or PR):

1. The current version, compatibility baseline and public contract, with a
   concrete source for the promise.
2. A specific previously supported consumer, input, stored-data format or
   workflow; what worked before; and what fails or changes incompatibly after.
3. Evidence from the actual change and, where feasible, a reproducible test or
   contract comparison. State any unverified assumption explicitly.
4. The necessary consumer action or migration, or why none is available, and
   why an automatic migration, compatibility layer or supported old path does
   not preserve the contract.
5. The resulting level, with a concise rationale. For mixed changes evaluate
   each impact and select the highest applicable level.

**Do not propose or apply MAJOR without a demonstrated incompatible public
contract change.** A new feature, large diff, file count, architectural or
technology migration, dependency major, security label, version number of a
dependency, or an optional user action is not proof of a break. A database
schema change, validation change, re-login or data migration is MAJOR only if
it actually breaks a supported contract or requires previously working
consumers to change under the project's compatibility promise. A bug fix can
also be breaking if consumers rely on behavior the project promises; do not
infer compatibility solely from `fix`.

If the contract or impact is genuinely uncertain, inspect more evidence and
run targeted compatibility checks. If it remains unresolved, report the
uncertainty and ask for a decision **before** the bump; do not silently choose
PATCH, MINOR or MAJOR. A major version is not a substitute for investigation.
When the evidence proves a break, do not suppress MAJOR merely because the
change is small or a higher number is inconvenient.

### Initial development (`0.y.z`)

SemVer treats `0.y.z` as initial development and does not promise a stable
public API. This guide's default policy is: incompatible changes increment
MINOR (`0.y.z` → `0.(y+1).0`) and are documented as breaking; compatible new
capabilities also increment MINOR; compatible fixes increment PATCH. An
explicit project policy can impose stronger compatibility guarantees.
Moving from `0.y.z` to `1.0.0` declares a stable public API: it is a separate
release-readiness decision, not the automatic result of a feature or a break.
Follow an explicit project policy or user decision for that transition.
For pre-release versions, use the project's documented pre-release policy;
if none exists, resolve the intended target and sequence before bumping.

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
- Deprecating public API functionality, even while retaining compatibility.
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
- Correcting validation rules without breaking supported inputs.
- Fixing accessibility issues.

## Decision Flowchart

Follow this sequence to determine the correct bump level:

```
1. Is a public contract incompatibly changed, with evidence from the hard gate?
   YES → MAJOR for stable versions; MINOR under the 0.y.z policy
   UNKNOWN → investigate; if unresolved, ask before bumping
   NO → continue

2. Does it add backwards-compatible functionality or deprecate public API?
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

`COMMITS.md` adopts Conventional Commits. Its types describe the change; this guide determines the actual bump at Step 5. A `feat` normally corresponds to MINOR, a `fix` to PATCH, and a breaking change to MAJOR for stable versions or MINOR under the `0.y.z` policy. A `refactor` is PATCH unless it restructures multiple files or modules, when this guide prescribes MINOR. For `perf`, `build`, `test`, `ci`, `docs`, `chore` and `revert`, assess the actual impact using the decision flow above and the exceptions in `TASK-COMPLETION.md`.

The multi-file refactor rule and mandatory per-task bump are project policy, not requirements of Conventional Commits or SemVer. Release automation using only default commit-type mappings may choose a different version; configure it to honor these rules before using it.

**Precedence rule:** when a task includes mixed-level changes, always pick the **highest** applicable level.

## Rules

1. Exactly one bump per completed task, applied at Step 5 of `TASK-COMPLETION.md`.
2. On mixed changes, pick the highest applicable level.
3. When unsure between `PATCH` and `MINOR`, investigate whether a capability or public deprecation was added; if unresolved, ask rather than under-versioning.
4. When compatibility remains uncertain after investigation, ask the user before selecting a level. Do not guess.
5. Never edit version files manually — always use the mechanism declared by the stack doc.
6. Never skip the bump because "the change is small". Bug fixes are `PATCH`, not nothing.
7. Never bump before a successful build, lint, and test (Steps 1 through 3 of `TASK-COMPLETION.md`).

## Examples

These examples assume a stable version (`1.0.0` or later) and the stated
compatibility impact; apply the initial-development policy to `0.y.z`.

| Change                                                    | Bump  |
|-----------------------------------------------------------|-------|
| Add dark mode toggle to settings                          | MINOR |
| Add an optional feature while existing workflows still work | MINOR |
| Replace an internal dependency with no public behavior change | PATCH |
| Migrate stored data automatically without breaking supported clients | PATCH or MINOR, by actual change |
| Deprecate a public endpoint while retaining it            | MINOR |
| Fix currency format showing wrong decimals                | PATCH |
| Remove a supported migration path, forcing existing users to re-sync | MAJOR |
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
| Require an additional input on a supported API call        | MAJOR |
| Add an optional API input without affecting existing calls | MINOR |
| Update a dependency to a compatible version               | PATCH |

Examples of the resulting version: a compatible feature changes `2.4.3` to
`2.5.0`; a compatible fix changes it to `2.4.4`; an evidenced breaking change
changes it to `3.0.0`. Under this guide's initial-development policy, a break
from `0.4.3` produces `0.5.0`, not `1.0.0`.

## Release Flow

Bumping the version (Step 5) and releasing are different events. A release is the moment a tagged version reaches users — a store, a registry, a deployment target. These rules keep the two apart and keep the release honest. They are stack-agnostic; the project's CI configuration implements them.

- **A release is driven by a tag, in its own pipeline.** Store and registry releases live in a dedicated workflow triggered by version tags (`vX.Y.Z`) and manual dispatch only. Nothing is built or published because a version-bump commit was merged.
- **The release workflow carries no path filter.** CI systems apply push path filters to tag pushes too, and a tag on an already-pushed commit carries no changed files — a filtered workflow is silently skipped and the release never happens. Path filters belong to the regular pipeline, never to the release one.
- **A green job is not a shipped release.** When a job only hands off to, or polls, an external build system (a store build service, a cloud native build), the job's own status proves nothing. The job asserts the external system's terminal status — complete *and* succeeded — and fails otherwise.
- **Runner selection has a fallback.** If the project uses a self-hosted runner, the workflow detects whether it is online and falls back to a hosted runner when it is not. A release never waits on a machine that happens to be off.
- **Build numbers are derived, monotonic and never hand-edited.** The build code native platforms require (Android `versionCode`, iOS build number) is computed — minutes since a fixed epoch, or the store's latest plus one — not maintained by hand. The user-facing version (`MAJOR.MINOR.PATCH`) lives in one file (`package.json` or the stack's equivalent) and a script every native build runs copies it into the native version files. Two sources for one version is how they diverge.

## See Also

- `TASK-COMPLETION.md` — Orchestrator that consumes this document at Step 5.
- `AGENT-WORKFLOW.md` — Operating discipline before and during the change.
- `AUTONOMOUS-EXECUTION.md` — The unsupervised mode, which applies a bump at every slice.
- `COMMITS.md` — Conventional Commit message and type definitions.
- Stack documentation of the consuming project — Concrete mechanism for applying the bump.

## Deviations in this project

- **"Version files must never be edited manually" is not satisfied.** dbqm has no
  bump command: `dbqm/_version.py` is edited by hand and `pyproject.toml` reads it
  through `[tool.setuptools.dynamic]`. The compensating control is the release
  workflow, which refuses to publish when the pushed `v*` tag does not equal that
  file. uv is adopted for development, but its version command does not update
  this dynamic version source (see `BACKEND-PYTHON.md`).
- **The release flow is otherwise exactly as prescribed**: tag-driven, the
  pipeline guards tag == version, and no release comes from a developer machine.
