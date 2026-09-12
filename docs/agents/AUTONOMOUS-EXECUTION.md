# Autonomous Execution

## Purpose

This document defines the **execution mode** an AI agent enters once a plan, a task or an objective has been approved and the work must be carried to real completion without supervision: how the plan is sliced, which internal roles act, where the state lives, when the agent stops to ask, and how it avoids loops.

It is a mode, not a third discipline. `AGENT-WORKFLOW.md` still governs how every edit is planned and made; `TASK-COMPLETION.md` still closes every slice through build → lint → test → docs → version → commit → merge. This document sits between them: it turns an approved plan into slices, runs each slice through both, keeps the state in files, and decides when a human is needed. Nothing here redefines the completion cycle or the editing discipline.

## When This Mode Applies

- The conversation or the repository already holds a plan, a task list, a spec or a stated objective, and the user has said to execute it. The plan is the source of work: **do not ask for it again**, do not ask for confirmation to start technical work, and do not build a different project from the one in context.
- It does **not** apply when the user is planning, exploring, or asking a question. Those follow `AGENT-WORKFLOW.md` § Planning, where the output is a plan and the gate is approval.
- The mission is to execute what was planned until it is genuinely done: review the plan, implement, review the implementation, run, test, fix — and stop only when everything is complete or when a decision would change how the system behaves.

## Principles

- **Operational autonomy.** Continue alone through implementation, fixes, tests, lint, file organisation and state updates.
- **Minimal escalation.** Interrupt only when a choice changes behaviour, scope, an API contract, data, security, cost, critical UX, or carries irreversible risk.
- **Evidence over assertion.** Declare something done only with a command executed, a result observed, and the acceptance criterion met.
- **Incrementalism.** One small, testable slice at a time.
- **Fidelity to context.** Invent no features, APIs, dependencies or requirements that are not in the plan or the existing code. Widening the scope is a decision, not a side effect: it goes to `TODO.md` or to "Out of scope", never straight into code.
- **Persistent state.** Progress lives in files, not only in the conversation — that is what survives a context reset.
- **No loops.** Every rework has a limit, a hypothesis, and an exit criterion.
- **No theatrical guard rails.** Do not ask "may I continue?" after every file. Continue. The approval was given once, for the plan; the phase checkpoint of `AGENT-WORKFLOW.md` § Planning becomes a **report** in this mode, not a stop.

## Roles

A single model plays all of them. The active role is named in every `PROGRESS.md` entry, so a reader can tell whether a line records a change, a review verdict or a test result.

| Role | Responsibility |
|---|---|
| MONITOR | Watches progress, detects stagnation, writes `REPORT.md`, forces a change of approach or an escalation. |
| PLANNER | Breaks what is already in context into phases, tasks and verifiable acceptance criteria. Never writes a new plan. |
| IMPLEMENTER | Writes and changes code and configuration. |
| REVIEWER | Reviews the slice plan and the code for correctness, regression, security and simplicity. |
| TESTER | Runs, reproduces failures, validates acceptance and regression. |
| STATE KEEPER | Updates the control files at the end of every slice. |

- **No role hands a deterministic technical task to the user.** Running a command, reading an error, finding a file, re-running a suite: the agent does it.
- The REVIEWER may be a fresh sub-agent with no memory of having implemented the code — independence is the point. It is dispatched with the slice's acceptance criterion and the diff, and retired the moment it reports (`AGENT-WORKFLOW.md` § Orchestrating Sub-Agents).

## Control Files

Four files under `ops/` at the repository root. They are **working papers**: `ops/` is gitignored, created at boot if absent, updated at the end of every slice, and emptied when the work closes (see "Definition of Done"). A committed `ops/` becomes a second backlog that contradicts the canonical documents within a week.

| File | Holds | Written by |
|---|---|---|
| `TODO.md` | Meta, current phase, tasks with acceptance, the active task, recently done, out of scope. Blocked tasks are `[!]` lines with the blocker stated. | STATE KEEPER |
| `PROGRESS.md` | Append-only log: one entry per slice with the active role, the command run, the observed result, and the rollback of any destructive change. | Every role, through STATE KEEPER |
| `DECISIONS.md` | Decisions taken autonomously (what, why, what was rejected) and escalations awaiting an answer, in the escalation format. | MONITOR, REVIEWER |
| `REPORT.md` | The MONITOR's latest report only — overwritten, never appended. The dashboard a human reads to know the state without opening the log. | MONITOR |

Their language follows the cascade in `COMMITS.md`, like every other project document. Do not replace them with long chat messages: the chat summarises and points to the file.

### TODO.md format

```markdown
# TODO

## Meta
One paragraph: what "done" means for this work, derived from the context.

## Current phase
Phase:
Phase objective:
Phase acceptance:

## Tasks
[ ] ID | phase | description | verifiable acceptance | owner | status

## Now
Active task:
Current hypothesis:
Next action or command:

## Recently done

## Out of scope
What must not be done in this run.
```

- Statuses: `pending`, `in_progress`, `review`, `testing`, `done`, `blocked`. Marks: `[>]` in progress, `[x]` done, `[!]` blocked.
- **One task in progress at a time**, except trivial subtasks of the same slice.
- **`done` requires evidence** — the `PROGRESS.md` entry that proves it.
- **Everything that appears mid-way becomes a task.** A defect noticed in passing, a missing test, a doc that lied: it is written down, not fixed silently and not forgotten.
- **A task that grows is split before continuing.**
- The list is extracted from the context and the repository. It is never requested from the user.

## Boot — First Action

1. **Read the project's agent-guidance file** (`AGENTS.md`), the plan in context, and the repository state (`git status`, the backlog if one exists).
2. **If `ops/` exists, resume.** `TODO.md` § Now is the position; the last `PROGRESS.md` entry is the evidence of where things stood. This is the path taken after a context reset — the files exist so that a new context can pick up without re-deriving anything.
3. **If it does not, create it.** PLANNER turns the context into phases, tasks and acceptance criteria and writes `TODO.md`; STATE KEEPER creates the other three files empty; `ops/` is added to `.gitignore` if it is not there.
4. **If a genuinely blocking decision exists at the start**, ask exactly one question in the escalation format. Otherwise, start the first phase immediately.
5. Enter the slice cycle for the first task and leave it only through the escalation rules or through completion.

Never ask for confirmation to boot. Never ask for the plan.

## The Slice Cycle

Every task runs through these steps in order.

**A. Plan the slice** (PLANNER)
- Restate the objective in a few lines.
- List the files to be touched — at most five per slice (`AGENT-WORKFLOW.md` § Planning); more means the slice is two slices.
- Define the verifiable acceptance: a command, an observable behaviour, or a test case.
- Name the risk and the rollback.

**B. Review the plan** (REVIEWER)
- Is it the shortest path?
- Is there a hidden dependency?
- Is there an open product or architecture decision? Then **block and escalate**. Otherwise continue.

**C. Implement** (IMPLEMENTER)
- Change only what is necessary. Simple, explicit, testable.
- No dead code, no debug output, no `TODO` comment in the code that is not mirrored as a task in `TODO.md`.
- The slice's test is written with the behaviour, not after it.

**D. Review the implementation** (REVIEWER)
- Does the code meet the acceptance?
- Any obvious regression? Any broken contract or API?
- Any silenced error? Any hardcoded secret?
- Any unjustified complexity? Does the style follow the repository?
- Does the new or changed behaviour have enough test coverage?
- The mindset is `AGENT-WORKFLOW.md` § Code Quality Bar; the specifics are the stack document's. **If the review fails, back to C.** Nothing is marked done.

**E. Run and verify** (TESTER)
- Run the real path through `TASK-COMPLETION.md` Steps 1–3: build, lint, test, plus the slice's own acceptance command. The test scope follows the reach of the change, as `TASK-COMPLETION.md` defines it.
- Record the command and the observed result in `PROGRESS.md`.
- On failure: the failure protocol below. **If it did not run, it is not done.**

**F. Close the slice** (STATE KEEPER, then the cycle)
- Complete `TASK-COMPLETION.md` Steps 4–6: docs sync, version, commit in the `COMMITS.md` format. One slice, one commit — never a WIP.
- Update `TODO.md` (status, evidence, recently done), `PROGRESS.md` (the closing entry), `DECISIONS.md` if a choice was made.
- Move to the next task of the same phase. **When a phase closes, verify the phase acceptance end to end** before opening the next one, and the MONITOR reports.

Repeat until everything derived from the context is done.

## When to Stop and Ask

Stop and ask one objective question **only** if:

- Two or more valid options differ in behaviour, data, security, cost or UX.
- The requirement is contradictory or incomplete and inferring is risky.
- The next step deletes data, runs a destructive migration, exposes a public endpoint, changes authentication, or alters a contract already in use.
- An external constraint blocks the work: a credential, a paid service, a permission, an unreachable environment.
- The same technical blocker persists past the attempt limit.

**Escalation format** — written to `DECISIONS.md` and summarised in the chat:

1. Context in a few lines.
2. What was already tried.
3. Options A, B, C with pros, cons and a recommendation.
4. Impact of each choice.
5. One closed question.
6. **What continues meanwhile.** Everything that does not depend on the answer keeps going; only the dependent task is `[!]`.

Do not ask several open questions. Do not stop over an aesthetic preference. Do not ask for the plan, the stack or the next task when they are in the context or the repository.

## Monitor

The MONITOR acts **after every completed task, or every three fix cycles, whichever comes first**, and overwrites `REPORT.md` with:

- Current phase and task.
- A conservative percentage of the phase.
- What changed since the last report.
- Build and test evidence (the commands and their results, not "tests pass").
- Blockers.
- Risk of a loop or of scope growth.
- The next concrete action.
- Cycles spent on the current task.
- Verdict: `ON_TRACK`, `SLOW`, `STUCK` or `NEEDS_DECISION`.

Rules:

- A task in progress for **more than three fix cycles without measurable progress** is `STUCK`: change the approach or split the task.
- The **same error appearing three times** ends the repetition of the same patch: the hypothesis changes.
- An IMPLEMENTER adding a feature outside `TODO.md` is cut back to scope.
- REVIEWER and IMPLEMENTER going in circles: the MONITOR picks the simplest option that satisfies the acceptance and records it in `DECISIONS.md`.
- **No report may say only "continuing".** It carries a new fact or a reason for stagnation.

## Anti-Loop

Limits, reconciled with `AGENT-WORKFLOW.md` § Self-Correction:

- **Second failure of the same fix:** stop, read the whole relevant section top-down, and write in `PROGRESS.md` where the mental model was wrong before trying again.
- **Third attempt** is made with the corrected model. **On the fourth, change strategy or escalate.**
- **At most five IMPLEMENTER–TESTER cycles on one task.** Then reduce the slice or block it with a decision.
- No refactor outside the active task unless the build or a test demands it.
- No new library when the repository already solves the problem adequately.
- No abstraction for the future.
- No rewriting a whole file to change a few lines.
- No cosmetic formatting while the functional acceptance is still failing — unless a repository hook blocks the flow.
- **No running tools in a loop "just to be sure".** One relevant suite and the slice's happy path are enough; the reach-of-change rule in `TASK-COMPLETION.md` sets the scope.
- **If the environment cannot run something, say so**, prepare the command or the test, and do not pretend it ran. A gap declared is a task; a gap hidden is a lie in `PROGRESS.md`.

**Failure protocol:**

1. Reproduce.
2. Reduce to the smallest case.
3. Formulate a hypothesis.
4. Apply the smallest patch.
5. Re-run the same test that failed.
6. If it passes, run the nearby regression.
7. Record the result.

**If it does not reproduce, do not fix in the dark.**

## Quality Floor

Transversal minimums; the stack document adds the specifics.

- Follow the style and architecture already in the repository.
- Handle errors for real. Never swallow an exception.
- Validate at the edges: input, I/O, API.
- No secret in code.
- The slice's test is born with the behaviour.
- Prefer a small diff and stable names.
- Document only what a developer needs to run the result and understand the contract.

## Definition of Done

**A task** is done when: the code is in the right place; the internal review passed; the acceptance ran and passed; no known regression; `TODO.md` and `PROGRESS.md` are updated; no critical `[!]` remains on it.

**A phase** is done when: every task of the phase is `done`; the phase acceptance was verified end to end; the last `REPORT.md` has no open `NEEDS_DECISION`.

**The work** is done when:

- Every phase derived from the context is done and the main flow works.
- The relevant tests pass, with the commands recorded.
- Run instructions are updated if the result needs them to be used.
- `TODO.md` has no `in_progress` or `blocked` item.
- The last slice closed through `TASK-COMPLETION.md`, including Step 7 when the work is merged: changelog entry, backlog reconciled, design specs deleted.
- **`DECISIONS.md` was promoted and `ops/` emptied.** Every decision still worth knowing moves to the project's canonical documents — the agent-guidance file, the changelog, the backlog. What stays in `ops/` is not read again.

## Git and Safety

- Commit **per slice**, in the `COMMITS.md` format, through `TASK-COMPLETION.md` Step 6. No WIP commits, no squash of unrelated slices.
- Never commit a secret, a `.env`, a heavy artifact or a useless generated file. `ops/` stays ignored.
- No force push on a shared branch.
- Before any destructive change, write the rollback in `PROGRESS.md`.
- No AI attribution anywhere — commits, pull requests, changelog (`COMMITS.md`).

## Communication

Between slices, speak short:

- Done.
- Evidence.
- Task now.
- Next step.
- Decision needed: yes or no.

Do not dump a log. Summarise and point to the state file. During a long implementation, **the MONITOR speaks for the team**; the IMPLEMENTER does not narrate every change. Progress cadence for long-running work follows `AGENT-WORKFLOW.md` § Execution & Progress.

## See Also

- `AGENT-WORKFLOW.md` — The discipline every edit follows inside this mode: planning phases, context management, edit safety, self-correction, sub-agents.
- `TASK-COMPLETION.md` — The cycle every slice closes through (build → lint → test → docs → version → commit → merge), including the reach-of-change test scope and Step 7.
- `COMMITS.md` — Message format for the per-slice commit and the language cascade the control files follow.
- `VERSIONING.md` — Bump-level rules applied at every slice's Step 5.
- Stack documentation of the consuming project — The concrete commands and quality specifics the slice cycle runs.

## Deviations in this project

The mode applies as written. What follows is what dbqm's own shape does to it,
and one standing instruction from the maintainer that overrides the default
cadence.

### Reporting cadence — the maintainer's instruction

The MONITOR section has this mode reporting after every completed task. **dbqm's
maintainer asked for the opposite**, for a tier of work: *"siga de forma
autonoma, ajustando, testando, revisando e validando"* and, on the tier before
it, *"somente após finalizar tudo, me informe"*.

So: the per-slice state still goes to the control files — that part is not
optional, it is what survives a context reset — but the **chat** carries one
report at the end of a tier, not one per task. Escalations are the exception
and interrupt immediately, in the escalation format. A `REPORT.md` is still
written; it is simply not narrated.

### Slice cycle, in dbqm's terms

- **Step E (run and verify) has no lint command.** `TASK-COMPLETION.md` Step 2 is
  a documented no-op here until ruff lands; see `BACKEND-PYTHON.md`.
- **Never run two pytest instances at once**, and never run the whole suite
  during a slice. Two full Textual suites in parallel exhausted the maintainer's
  machine and the OS killed both runs. A slice runs the file covering the change;
  a tier ends with the suite run in slices, sequentially, in the foreground:
  `tests/core`, `tests/models`, `tests/design`, the three `tests/test_cli*.py`,
  then `tests/ui` by file. `test_app.py` and `test_screens.py` take about 75s and
  100s; wrap each run in `timeout` so a hang is bounded rather than silent.
- **Step F closes with a local `--no-ff` merge into `main`.** Publishing is not
  part of the cycle: it happens when a `v*` tag is pushed, and the tier's fixes
  reach nobody until then.

### Control files against the ones already here

`ops/` is added to `.gitignore` and is for the *execution* state of a run in
progress. It does not replace what dbqm already keeps:

| Path | Holds | Committed |
|---|---|---|
| `ops/` | State of the run in progress — TODO, PROGRESS, DECISIONS, REPORT | no |
| `docs/ROADMAP.md` | **The** backlog, ordered by importance and theme | yes |
| `docs/ARCHITECTURE.md` | Structure, patterns and the measured known debt | yes |
| `docs/plans/`, `docs/superpowers/` | Specs, plans, execution logs | no |

"Promote `DECISIONS.md` and empty `ops/`" therefore means: a decision that
changes how the code is built goes to `docs/ARCHITECTURE.md`; one that changes
what gets built goes to `docs/ROADMAP.md`; one that changes how an agent works
goes to `AGENTS.md`.

### Two escalation rules this project paid for

- **"Do not stop over an aesthetic preference" has a limit here.** A change that
  alters what the maintainer *looks at* is an escalation even when it is
  technically the only option that fits. Measured four variants of the tab strip,
  picked the only one that fit at 80 columns, and it was rejected on sight — the
  emoji were identity, not decoration. Show a rendering before committing to a
  visible change, and prefer a screenshot over a description.
- **A premise can be wrong, and checking it is cheaper than the fix.** Two Tier 0
  bugs dissolved that way: a token-limit report that a later commit had already
  fixed, and "the TUI cannot clear a password", which needed no new widget once
  it was noticed that the form already shows the stored password. Re-measure the
  complaint before implementing against it.
