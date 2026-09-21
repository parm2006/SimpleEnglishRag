# How to implement with Terra or Luna

## Start here

Read README.md for order. Give an agent ONE numbered plan, this handbook, CONTRACTS.md and ARCHITECTURE.md. It must read the plan's stated dependencies from the repository; no conversation history is assumed.

Plans are intentionally smaller than the entire product. For complex plans, assign one numbered substep at a time and keep the same task until its gate passes. A plan is DONE only when every substep and its integration checks pass.

Use Luna for fixtures, straightforward components, report formatting and documentation after interfaces are frozen. Use Terra for parsing, contracts, browser worker state, retries/resume logic and storage integration. These are workload suggestions, not guarantees about a model. Keep final design and release decisions with yourself; use a stronger reviewer for unresolved cross-runtime or storage discrepancies.

## Planning baseline and drift check

Planned at 2026-09-15:
- Directory: C:/Users/parth/Projects/SimpleEnglishRAG.
- No Git repository and no code/build/test configuration.
- Sole original file: wikipedia-rag-roadmap.md.
- SHA-256: 5EE0F4408DF5C72C68C773843C8450C5C725677A150C396F832D1B077681119D.
- No existing source exemplar or verified test command. Proposed commands are established by 001, not claimed to work already.

Before 001: list files and verify original roadmap hash; preserve all existing work.
After Git is initialized: each executor records its own start revision with git rev-parse HEAD, runs git status --short, and examines git log -5 --oneline. Record the last completed dependency's commit in the plan completion note. Run git diff <dependency-commit> -- <owned-paths> if those paths have changed since dependency completion. Do not literally pass placeholder angle brackets to PowerShell.
If no commit exists yet, record that and use the inspected file inventory as baseline; don't invent a revision.

At the end inspect git diff --stat and git diff -- <owned-paths>; untracked files need explicit review too. Preserve user changes. Do not reset, clean, force-push or overwrite others' files. A commit is optional until the owner chooses to record it; a clean, reviewable change is required.

## Reusable executor prompt

Copy this and replace NNN and the plan filename:

> Implement only plan NNN in plans/simplewiki-public-rag/<filename>.md.
> First read that whole plan, EXECUTOR-HANDBOOK.md, CONTRACTS.md and ARCHITECTURE.md.
> Inspect current files and the completed dependencies before editing.
> List the intended files and the first acceptance test, then implement the numbered steps.
> You share the repository; preserve other work and stay inside the plan's file ownership.
> Do not implement later plans, weaken tests, change interfaces silently, add paid services,
> publish, or run a full-corpus job unless this plan explicitly calls for it and its gates pass.
> Follow the exact verification commands; distinguish mocked, local integration and live results.
> At a design fork write a handback instead of guessing.
> Finish with changed files, tests and outcomes, deviations, blockers and the next plan.

## Per-step loop

1. Inspect the relevant actual files; expected files named in plans may not exist until their dependency lands.
2. Add a meaningful test for behavior with a known expected result.
3. Implement the smallest coherent change.
4. Run the focused test and the relevant lint/typecheck.
5. Inspect diff for accidental changes and secrets.
6. Update completion note with evidence and stop at the plan boundary.

Do not ask an agent to "build everything from the roadmap." Do not let two agents edit the same package/lockfile simultaneously.
Parallel work is optional only after dependencies pass: 003 and browser UI scaffolding can proceed independently after 002/007 as applicable. Sequential execution is easiest initially.

## Completion note template

In reports/plan-NNN.md:
- Start revision and end revision if committed.
- Files changed.
- Commands run and exact success/failure summary.
- New config values (no secrets).
- Artifacts with paths, counts and checksum.
- Manual checks and environment.
- Known limitations.
- Deviations and why.
- Next executable plan.

Update only your row in the effort README. Small reports can be committed; raw datasets, keys, model files, logs and vectors are ignored.

## STOP / handback protocol

Stop dependent work when:
- Required predecessor evidence or command is missing.
- Shared schemas/model/pooling/IDs need changing.
- Data loss or rejected articles lack a disposition.
- Actual API behavior disagrees with a plan.
- A free-tier gate fails, provider requires billing, or a migration would change public service.
- Existing edits overlap and cannot be safely preserved.

Do not stop for ordinary implementation choices inside the specified behavior.

Write plans/simplewiki-public-rag/handback-NNN-<topic>.md:
1. Current state and exact failing command.
2. Desired outcome.
3. Evidence, files and minimal reproduction.
4. Decisions still needed.
5. Work safe to retain.

Do not change the design spec to make a failing test pass. The owner/planner resolves the fork in memo-<topic>.md, amends affected plans, and logs the decision.

## Reviewer prompt

> Review only the scoped implementation against plan NNN and CONTRACTS.md.
> Check correctness, missing edge cases, data loss, exposed keys, runtime compatibility and
> whether tests actually exercise the behavior. Cite file/line evidence.
> Do not rewrite architecture or fix files. Rank actionable findings and say which gate they block.
> Check claimed tests against actual output; "not run" is not a pass.

## Installation / versions

No dependencies are installed by this planning work. Plan 001 selects mutually compatible stable versions and records exact versions in lockfiles. Never substitute SDK method names from memory when installed types disagree. Recheck primary documentation in SOURCES.md at execution, especially provider limits, models and framework integration.

No missing template blocks execution: the writing-plans skill's plan-template.md was absent at planning time. Each plan instead carries outcome, ownership, ordered steps, gates, stop conditions and handback instructions.

