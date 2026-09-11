# Task Completion Workflow

## Purpose

This document is the mandatory orchestrator that runs at the end of every completed logical unit of change. It defines the fixed sequence **build → lint → test → docs → version → commit → merge** and the behavior for every edge case in that sequence. It delegates concrete commands (build, lint, test, version bump) to the stack-specific documentation of the consuming project, and delegates message and bump-level rules to `COMMITS.md` and `VERSIONING.md` respectively.

Any change that reaches the repository history MUST go through this workflow, except for the closed list of exceptions in section "Documented Exceptions".

## Trigger — What Counts as a Completed Task

A **logical unit of change** is a cohesive set of modifications that:

1. Resolves a single intent (a fix, a feature, a contained refactor, a dependency update).
2. Leaves the code in a valid, buildable, testable state.
3. Can be described by a single commit message with a single commit type.

Examples that trigger the cycle:

- Fixing a bug.
- Adding a feature or a deliverable sub-feature.
- Refactoring a contained area of the code.
- Updating a dependency.
- Removing dead code.

Examples that do NOT trigger the full cycle (see "Documented Exceptions"):

- Changes exclusive to documentation files.
- Changes exclusive to CI/CD configuration.
- Changes exclusive to development-tool configuration.

**WIP commits are forbidden.** Every commit in the history must represent either a complete successful cycle or one of the documented exceptions.

## The Mandatory Sequence

Steps 1–6 run in this fixed order. Reordering is not allowed. Step 7 runs only
when the work is merged.

```
┌─────────┐  ┌────────┐  ┌────────┐  ┌────────┐  ┌──────────┐  ┌─────────┐  ┌─────────┐
│ 1 BUILD │─►│ 2 LINT │─►│ 3 TEST │─►│ 4 DOCS │─►│ 5 VERSION│─►│6 COMMIT │─►│ 7 MERGE │
└─────────┘  └────────┘  └────────┘  └────────┘  └──────────┘  └─────────┘  └─────────┘
     │            │           │                                              only when
     │ fail       │ fail      │ fail                                         merged
     ▼            ▼           ▼
   abort, fix, restart from Step 1
```

Any failure at any step aborts the cycle. After fixing the underlying problem, the cycle restarts from **Step 1** — not from the failed step — because the source code has changed and the previous build/lint/test results are no longer valid.

## Step 1 — Build

- The concrete build command is defined by the stack documentation of the project (for example, `BACKEND-JAVA.md`, `BACKEND-PYTHON.md`, `FRONTEND-REACT.md`, or any future stack document).
- Execute the full build declared by the stack doc.
- This step cannot be skipped for any reason, including "the change is small" or "it only touches one file".
- On failure: abort the cycle, fix the underlying problem, restart from Step 1.

## Step 2 — Lint

- The concrete lint command is defined by the stack documentation of the project.
- Execute the linter over the whole project, not only over the files the change touched — a change can break a rule in a file it never edited (an import that is now unused, a symbol that is now dead).
- **Fix every error.** Warnings are allowed unless the project's documentation says otherwise — a project that declares a zero-warning policy treats a warning as an error, and a change that introduces one fails this step.
- **Scope the run to the reach of the change, and treat the whole end-to-end suite as an on-demand gate.** A suite that takes tens of minutes, spins up browsers, consumes shared fixtures or creates throwaway accounts is not free, and running it after every small change trades hours for a signal the change could not have moved. Three levels: a local change with no shared component runs the build, the linter, the unit tests and the specs of the area it touches; a change to a shared component, hook or test harness adds the neighbouring areas; a cross-cutting change (design tokens, a base dialog, navigation, fixtures, test configuration) adds everything its reach actually covers — and then **asks** for the full run rather than starting it. The user, not the agent, decides when the whole suite runs; one full run before a release candidate is what makes it worth its cost.
- **Say what you ran and what you did not.** The pull request records the exact commands executed and states plainly that the full suite was not run, when it was not. A reader must never infer coverage that does not exist.
- This step cannot be skipped.
- On failure: abort the cycle, fix the underlying problem, restart from Step 1 (the build must run again because the code changed).

## Step 3 — Test

- The concrete test command and scope are defined by the stack documentation of the project.
- Execute the full test suite declared by the stack doc.
- **Infrastructure changes are tested too.** A migration, a grant, a policy or a trigger that "should" lock something down is proven by a read-only script that asserts the whole matrix (grants, `search_path`, policies, trigger presence) against the real database and exits non-zero on any deviation. The script is committed and re-run after any later change touching the same objects — defaults re-grant on `DROP` + `CREATE`, so a rule proven once is not proven forever. The stack or companion doc (for example `PERSISTENCE-SUPABASE.md`) says what the script checks.
- This step cannot be skipped.
- On failure: abort the cycle, fix the underlying problem, restart from Step 1 (the build must run again because the code changed).

## Step 4 — Documentation Sync

- When the change alters anything user- or developer-facing, update the affected documentation **as part of the same task**, so docs never drift from the code.
- Sync triggers include: new or changed features/behavior; dependency or version changes; new/changed scripts, commands, or env vars; configuration or routes; **database schema** (also regenerate any types the project derives from it); serverless or edge functions; and any counts/metrics/examples referenced in docs.
- Files to keep current: `README.md` (project overview), the agent-guidance file if the project keeps one (`CLAUDE.md`, `AGENTS.md`, or equivalent), the architecture document if the project keeps one, and any specific guide impacted by the change.
- If the change touches nothing documented, this step is an explicit no-op (state it). Do **not** create new documentation files unless the task requests it — update the existing canonical docs.
- **The backlog is documentation too.** If the project keeps one, and this task closed, changed or invalidated an item in it, say so here — and **write down what proves it**, not just a tick. An item marked done without evidence is re-verified by the next person, or worse, trusted when it is no longer true.
- **An item this task discovered but did not solve is opened in the same cycle.** A defect noticed in passing and not written down is a defect found again from scratch later.
- **Per-task sync does not stop drift; schedule a full audit.** Every document drifts toward the milestone where it was last rewritten, and a task only verifies what it touched. Periodically — at a release, after a large refactor, or whenever a reader finds two documents contradicting each other — audit the documentation **claim by claim**: every checkable statement (paths, counts, commands, flags, versions) is verified against the code. Run it with parallel sub-agents, one per document group (`AGENT-WORKFLOW.md`, Context Management), each reporting `file:line — claim → reality (evidence)` with a severity tag. Fix in rounds, source of truth first: the agent-guidance file, then the guides, then test documentation, then external or publishing documents — a downstream document fixed before its source is redone when the source changes.
- Documentation edits are committed together with the change at Step 6 (not as a separate commit). A separate "update docs" commit afterwards splits one logical unit of change across two cycles.

## Step 5 — Version

- The rules for choosing the bump level (`MAJOR`, `MINOR`, `PATCH`) are defined in `VERSIONING.md`.
- The mechanism for applying the bump (which file holds the version, which command updates it) is defined by the stack documentation of the project.
- **Prerequisite:** the project MUST have a version mechanism configured before the first completion cycle. If no mechanism exists, this step fails — see "Failure Handling".
- Version files must never be edited manually. Always use the mechanism declared by the stack doc.

## Step 6 — Commit

- The rules for writing the commit message are defined in `COMMITS.md`.
- The commit message MUST NOT reference the version number generated in Step 5. The single exception is the release-changelog commit described in Step 7, which exists only to name a version.
- The commit message MUST NOT contain any form of co-authorship, attribution, or mention of AI agents or automated tools. The same applies to the **title and description of the pull request** that carries the commit — a "generated with" line in a PR body is the same attribution in a different place.
- One commit per completed task. No WIP, no squash of unrelated changes.

## Step 7 — Merge

Runs **only when the task's work is merged** into the mainline. A task that ends at a commit ends at Step 6.

- **Add the changelog entry now, not at release time.** If the project keeps a changelog, the merge is when someone still remembers what the change does. Written later, from a diff, an entry becomes a list of file names — which is exactly the entry nobody reads.
- **Write it for whoever uses the product**, not for whoever wrote the code: what behaviour changed, and where it is visible. A defect entry says what was going wrong, because that is what tells a reader whether it affected them.
- **Group it under an unreleased heading.** Several tasks usually ship in one release, so the entry lands under a heading such as `[Unreleased]`, which is renamed to the version and date when that release is tagged. Writing entries directly under a version fails as soon as two merges share it.
- **The rename at tag time is a documentation-only commit** (`Update changelog: release X.Y.Z`). It is the one commit allowed to name a version — the version *is* what it records — and it follows the documentation-only exception below.
- **Reconcile the backlog with reality.** Mark what this task closed, with the evidence. Remove what stopped making sense — an item kept out of politeness costs attention every time someone reads the list.
- **Delete the design specs and plans the work was built from.** A working paper left in the repository describes the system as intended, not as shipped, and gets cited as truth later. The changelog entry and the updated guides are the record; whatever reasoning in the spec still matters is moved into them before the file goes.
- Changelog, backlog and spec-removal edits are committed on the branch **before** the merge, so the merge carries them.

## Failure Handling

| Step    | Failure                                                   | Action                                                       |
|---------|-----------------------------------------------------------|--------------------------------------------------------------|
| Build   | Compilation or build error                                | Abort cycle. Fix. Restart from Step 1.                       |
| Lint    | Lint errors (or warnings, where the project forbids them) | Abort cycle. Fix. Restart from Step 1.                       |
| Test    | One or more tests fail                                    | Abort cycle. Fix. Restart from Step 1.                       |
| Docs    | Docs left inconsistent with the change                    | Update the affected docs before continuing to Step 5.        |
| Version | Project has no version mechanism                          | Abort cycle. Stop and report to the user. Mechanism must be created before any cycle can run. |
| Version | Wrong bump level applied                                  | Revert the bump. Restart from Step 5.                        |
| Commit  | Pre-commit hook or format failure                         | Fix the underlying issue. Restart from Step 1 (the code changed). |
| Merge   | Changelog entry missing after a merge                     | Add it in a follow-up commit on the mainline. Do not wait for the release. |
| Merge   | Backlog left claiming work that is done                   | Correct it with the evidence. A stale backlog is worse than no backlog. |

No commit may exist in history without a successful full cycle, except for the cases in "Documented Exceptions".

## Documented Exceptions

The following cases are the ONLY situations where a commit is allowed without running the full cycle. Each case requires that the changeset touches exclusively the file categories listed — any mix with source code disqualifies the exception and forces the full cycle.

1. **Documentation-only changes.** Changes exclusive to `.md` files or other documentation assets.
2. **CI/CD-only changes.** Changes exclusive to CI/CD configuration files (for example, GitHub Actions workflows, GitLab CI files, pipeline definitions).
3. **Dev-tooling-only changes.** Changes exclusive to development-tool configuration files (for example, `.editorconfig`, `.gitignore`, linter and formatter configuration, IDE settings).

For an exception commit:

- Steps 1 through 5 are skipped (build, lint, test, docs-sync gate, version).
- Step 6 still applies: the commit message must follow `COMMITS.md` rules. Use the `Update` type.
- Mixed changesets (code plus any of the above) are NOT exceptions — run the full cycle.

## Rules

1. Never skip steps, regardless of how small the change appears.
2. Never commit with a failing build, lint errors, or failing tests.
3. Keep documentation in sync — never leave the README, the agent-guidance file, the architecture document, or any guide describing behavior, versions, or schema that no longer match the code.
4. Never edit version files manually.
5. Never add co-authorship, attribution, or any mention of AI or automated tools to commit messages, pull request titles, or pull request descriptions.
6. If the project has no version mechanism configured, stop the cycle and report to the user.
7. On any failure, restart the cycle from Step 1 — never from the failed step.
8. One completed logical unit of change equals one cycle equals one commit.

## See Also

- `AGENT-WORKFLOW.md` — Operating discipline for the work that precedes this cycle (planning, context, edit safety). Hands off to this document once the change is complete.
- `VERSIONING.md` — Rules for choosing the bump level at Step 5.
- `COMMITS.md` — Rules for writing the message at Step 6.
- Stack documentation of the consuming project — Concrete build, lint, test, and version-bump commands.

## Deviations in this project

- **Step 2 (Lint) has no command.** dbqm has no linter and no type checker
  configured — see the deviations section of `BACKEND-PYTHON.md`. The step is a
  documented no-op until ruff lands (adoption step 2 there, tracked in
  `docs/ROADMAP.md`). It is recorded rather than deleted so that the day a
  linter exists, nobody has to rediscover that this step was skipped.
- **Step 1 (Build) is `python -m build`**, and `build` is not a declared
  dependency of the project — install it on a fresh machine before the first
  cycle. Same for `pytest-asyncio`, which lives in the `dev` extra: without it
  327 async tests fail for a reason that has nothing to do with the change under
  test.
- **Step 3 (Test) is `python -m pytest tests/ -x -q`** and takes about 3m10s.
  The scoping rule in Step 2 applies to it as well: a change confined to
  `cli.py` runs `tests/test_cli.py`, and the full suite runs before a release
  candidate or when the change is cross-cutting (`core/`, the design tokens, the
  layout guards, a fixture).
- **Step 5 (Version) is a manual edit** of `dbqm/_version.py`. There is no bump
  command, which `VERSIONING.md` forbids; the tag guard in
  `.github/workflows/publish.yml` is the compensating control.
- **Step 7 (Merge) is a local `--no-ff` merge into `main`** for solo work, not a
  pull request. Publishing is not a step of this cycle at all: it happens when a
  `v*` tag is pushed, which triggers the release workflow. Pushing `main` does
  **not** publish, and a version whose tag was never pushed is not released — the
  PyPI page keeps serving the previous version's README until then.
