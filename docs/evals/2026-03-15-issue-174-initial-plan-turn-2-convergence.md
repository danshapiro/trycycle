# Issue 174 Initial-Plan Turn-2 Convergence Eval Candidate

## Source

- Repo under investigation: `/home/user/code/freshell`
- User task theme: issue `#174` first-run bootstrap env root regression
- Trycycle phase: plan-editor loop only
- Starting plan: the existing initial implementation plan at `docs/plans/2026-03-13-issue-174-bootstrap-env-root.md`

## Purpose

This is the scored lazy-factor eval for this case.

It does not test the initial planner. It tests whether, given the existing weak initial plan, the first review can find every real problem and the second review can confirm the corrected plan unchanged.

## Starting point

Use the initial plan as the input plan.

Original recovered chain:

- initial plan: `1e1ec0e8`
- historical review 1: `5808fd89`
- historical review 2: `e30d8172`
- historical review 3: `063a9fee`
- historical review 4: `ALREADY-EXCELLENT` at `063a9fee`

Rewritten equivalent chain:

- initial plan: `6b8614bd`
- historical review 1: `09aa715c`
- historical review 2: `344f563d`
- historical review 3: `459e86ba`
- historical review 4: `ALREADY-EXCELLENT` at `459e86ba`

The historical failure pattern was:

- review 1 improved the plan but still missed issues
- review 2 still missed issues
- review 3 finally got the plan right
- review 4 confirmed it

## Required run shape

Run only the review loop:

1. start from the initial plan commit
2. dispatch review round 1
3. feed the resulting plan directly into review round 2
4. stop after review round 2 and score

Do not rerun the initial planner. Do not rewrite the input plan by hand between rounds.

## Pass condition

Pass only if both conditions hold:

1. review 1 fixes every real issue in the initial plan and reaches the same substantive endpoint as `063a9fee` / `459e86ba`
2. review 2 returns `ALREADY-EXCELLENT` with no file edits and no new commit

In plain terms: one review fixes everything, the next review confirms it.

## Failure condition

Fail if any of the following happen:

- review 1 is still centered on the env-loader abstraction or another wrong architectural target
- review 1 still misses one of the critical fix-surface decisions below
- review 2 still performs a material rewrite
- review 2 reaches `ALREADY-EXCELLENT` while the plan still misses a real issue
- the run still needs review 3 or later to get to the right plan

## What counts as “got it right”

Do not score by wording or task count. Score by whether review 1 contains the critical decisions from the final correct plan:

- treat the bug as a compiled cold-start regression, not a source-only bootstrap cleanup
- recognize that the repo already has the preferred `process.cwd()` product fix and should not invent a new dotenv authority layer unless the regression still proves one is needed
- extend the existing `test/e2e-browser/helpers/TestServer` helper rather than building a separate startup harness
- stage an isolated runtime root under the worktree so dependency resolution stays realistic
- avoid symlink-based staging
- treat product-code changes as conditional on the new compiled-start regression still failing after the harness is corrected
- prove first-run `.env` placement and authenticated startup behavior at the compiled boundary

## Notes

- This is the scored companion to [2026-03-15-issue-174-turn-4-convergence.md](./2026-03-15-issue-174-turn-4-convergence.md), which documents the old bad behavior.
- The exact original session artifacts have been recovered, so this eval can be replayed against the real historical initial plan rather than a reconstruction.
- A nearby supporting artifact exists in `docs/plans/2026-03-13-issue-174-bootstrap-env-root-test-plan.md`, which restates the target compiled-start contract and can help score semantic correctness.
