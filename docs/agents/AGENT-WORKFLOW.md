# Agent Workflow

## Purpose

This document defines the operating discipline an AI agent follows **before and
during** every unit of work: how it plans, keeps its context clean, edits
safely, corrects itself, and communicates. It is transversal — it applies to
every task regardless of stack.

It is the counterpart of `TASK-COMPLETION.md`. `TASK-COMPLETION.md` governs the
**end** of a change (build → lint → test → docs → version → commit → merge);
this document governs
everything that happens **up to** that point. The two never overlap: nothing
here redefines the completion cycle, and nothing there redefines how the work
is planned or edited.

The rules are harness-neutral. Where a concrete mechanism is named (a context
window, a re-read limit, a compaction command), it is an **example** of the
underlying rule, not a dependency on a specific tool. Apply the intent with
whatever equivalents your harness provides.

## Planning

- When asked to plan, output **only** the plan. Write no code until told to
  proceed.
- When given a plan, follow it exactly. Flag real problems and wait for a
  decision — do not silently deviate or "improve" it mid-flight.
- For non-trivial features (three or more steps, or any architectural
  decision), interview the user about implementation, UX, and trade-offs
  before writing code.
- Never attempt a multi-file refactor in a single pass. Break it into phases of
  at most **five files**. Complete a phase, verify it, get approval, then
  continue. Verification here defers to `TASK-COMPLETION.md`. In autonomous
  execution (`AUTONOMOUS-EXECUTION.md`), where the plan was approved up front,
  the phase checkpoint is a report, not a stop — the agent continues unless an
  escalation rule applies.

## Execution & Progress

- Track multi-step work in a visible task list: one entry per step, marked in
  progress or done as you go. The list is the source of truth for what remains
  — do not keep it only in your head.
- Report progress at every meaningful checkpoint (a task finished, a phase
  closed), and for long-running work at a regular interval so the user is never
  left guessing. The interval — and the point at which elapsed time counts as
  "too long" — is set by the user or the project's `CLAUDE.md`/`AGENTS.md`.
  When neither specifies one, choose a threshold appropriate to the task rather
  than defaulting to silence.
- Monitor long-running operations (builds, test suites, background commands,
  sub-agents) instead of waiting blindly. Form an expectation of how long each
  should take. If an operation stalls with no output, or runs well past that
  expectation, stop and investigate — a hang, a prompt waiting on input, a
  wrong command, a runaway loop — instead of assuming it will finish on its own.

## Orchestrating Sub-Agents

- Retire a sub-agent the moment its work is delivered. A finished agent that
  stays registered keeps appearing in the user's task list, showing the time
  since it started rather than the time it has been working — so the list stops
  describing what is actually running and the user cannot tell progress from
  clutter. Stop it explicitly, as part of closing the task.
- Never spawn a background task to wait for something. Waiting is one blocking
  call that returns when the condition is met. A loop that spawns a watcher
  every few seconds multiplies into hundreds of entries and buries the work that
  matters. Put the same prohibition in the brief of every agent you dispatch.
- Stop a watcher when the thing it watches is gone — the branch merged, the
  directory removed. A watcher outliving its target reports nothing and is
  indistinguishable from live work.
- Give every agent its own path for artifacts it writes outside the repository
  (pull-request bodies, notes, logs). A shared scratch filename is silently
  overwritten when two agents run at once, and the second one publishes the
  first one's text.
- Tell each agent what else is running, which resources are taken (ports, test
  accounts, working copies) and which files it must not touch. Parallel agents
  on one machine contend for more than processor time, and a failure caused by
  contention looks exactly like a real defect until someone re-runs it alone.
- Prefer finishing what is in flight over starting more. Past the point where
  the machine or the shared fixtures are saturated, another parallel agent buys
  re-runs, not throughput.

## Code Quality Bar

- Do not default to "the simplest approach" or "don't refactor beyond what was
  asked" when the structure is wrong. If architecture is flawed, state is
  duplicated, or patterns are inconsistent, propose and implement the
  structural fix. Ask: *what would a senior perfectionist reject in code
  review?* Fix that.
- Write code that reads like a human wrote it. No robotic comment blocks.
  Default to no comments; comment only when the **why** is non-obvious.
- Do not build for imaginary scenarios. Simple and correct beats elaborate and
  speculative.

The concrete standards for a given stack (naming, layering, library choices,
test structure) live in that stack's document. This section defines the
**mindset**; the stack docs define the **specifics**.

## Context Management

- Before any structural refactor of a large file, first remove dead props,
  unused exports, unused imports, and debug logs. Commit that cleanup
  separately. Dead code burns context.
- For work touching many independent files, split it across parallel
  sub-agents, each owning a small batch (roughly five to eight files). Sequential
  processing of a large set guarantees context decay partway through.
- After a long exchange, re-read a file before editing it. Context compaction
  may have dropped the details you relied on.
- If you notice signs of context degradation — referencing variables that do
  not exist, misremembering a file's structure — reset proactively (compact,
  fork, or restart) and write the session state to a handoff note so the next
  context can pick up cleanly.
- Read large files in bounded chunks rather than assuming a single read
  captured everything. If a tool result looks suspiciously small or truncated,
  read the full output at its source or re-run with a narrower scope.

## Edit Safety

- Re-read a file immediately before editing it, and again after. Edit tools can
  fail on a stale match without any real change landing — reading closes that
  gap.
- Text search is not an AST. On any rename or signature change, search
  **separately** for each reference form: direct calls, type references, string
  literals, dynamic imports, `require()`/module loads, re-exports, barrel
  files, and test mocks. Assume the search missed something and verify.
- Never delete a file without first verifying that nothing references it.

## Self-Correction

- After a correction from the user, log the pattern as a durable rule (for
  example, a `gotchas.md` the project keeps). Convert mistakes into rules and
  review past lessons at the start of a session.
- If a fix fails twice, stop. Read the entire relevant section top-down and
  state where your mental model was wrong before trying again.
- When testing your own output, adopt a new-user persona: walk through it as if
  you had never seen the project.

## Communication

- When the user says "yes", "do it", or "push", execute. Do not repeat the plan
  back.
- When the user points to existing code as a reference, study it and match its
  patterns exactly. Working code is a better spec than a description of it.
- Work from raw error data. Do not guess. If a report has no output, ask for it.

## See Also

- `AUTONOMOUS-EXECUTION.md` — The mode entered once a plan is approved: slices
  it, runs each slice under this discipline, keeps state in `ops/`, and defines
  when to stop and ask.
- `TASK-COMPLETION.md` — The end-of-change cycle (build → lint → test → docs →
  version → commit → merge) that begins once the work governed here is done.
- `COMMITS.md` — Message rules, referenced when a phase or cleanup is committed.
- `VERSIONING.md` — Bump-level rules for the completion cycle.
- Stack documentation of the consuming project — Concrete code-quality, testing,
  and command standards that this document's mindset is applied through.

## Deviations in this project

None. The planning, context-management, edit-safety and self-correction
discipline in this file applies to dbqm unchanged.

Two project facts this file needs:

- **Working papers live under `docs/superpowers/`** (specs) and `docs/plans/`
  (plans, backlog drafts, execution logs). Both are **gitignored** — never commit
  them. `AGENTS.md`, `CLAUDE.md` and this `docs/agents/` directory are the only
  agent-facing files that belong in the repository.
- **The full test suite takes about 3m10s.** A shell tool with a two-minute
  default timeout will cut it off mid-run and report a truncated result that
  looks like a hang; pass an explicit timeout of at least 400000 ms.
