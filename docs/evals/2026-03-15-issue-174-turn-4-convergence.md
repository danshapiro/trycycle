# Issue 174 Historical Four-Review Convergence Reference

## Source

- Repo under investigation: `/home/user/code/freshell`
- User task theme: issue `#174` first-run bootstrap env root regression
- Trycycle phase: plan-editor loop after the initial plan already existed
- Plan under review: `docs/plans/2026-03-13-issue-174-bootstrap-env-root.md`

## Purpose

This note records the old lazy-factor behavior for this case.

Do not use this as the target behavior. Use it as the baseline the improved prompts should beat.

## Historical review chain

Starting from the existing initial plan, the old review loop behaved like this:

Original recovered chain:

1. initial plan: `1e1ec0e8`
2. review 1: `5808fd89`
3. review 2: `e30d8172`
4. review 3: `063a9fee`
5. review 4: `ALREADY-EXCELLENT` at `063a9fee`

Rewritten equivalent chain:

1. initial plan: `6b8614bd`
2. review 1: `09aa715c`
3. review 2: `344f563d`
4. review 3: `459e86ba`
5. review 4: `ALREADY-EXCELLENT` at `459e86ba`

The important old behavior is:

- review 1 improved the plan but still missed issues
- review 2 still missed issues
- review 3 finally got the plan right
- review 4 confirmed it

## Why the first two reviews were still wrong

The initial plan was on the wrong track in ways that would likely cause implementation rework:

- it proposed a new env-path / dotenv loader abstraction instead of starting from the compiled-start regression boundary
- it treated duplicated authority between bootstrap and dotenv loading as the primary problem, even though the repo already had the preferred `process.cwd()` fix in product code
- it staged the runtime-root harness in a temp copied runtime outside the worktree, which the later plan correctly rejects because dependency resolution would fail for the wrong reason

By the final correct plan, the review loop had settled the right fix surface:

- compiled cold start, not source-only bootstrap logic
- existing `TestServer`, not a new harness
- isolated runtime root under the worktree
- no symlinks
- product code changes only if the compiled-start regression still exposed a real mismatch

## How to use this note

Use this as the baseline when scoring [2026-03-15-issue-174-initial-plan-turn-2-convergence.md](./2026-03-15-issue-174-initial-plan-turn-2-convergence.md).

If a new run still behaves like this, it failed to improve the lazy-factor problem.

## Semantic endpoint

Do not compare text literally. The meaningful endpoint is the final correct plan at `063a9fee` / `459e86ba`, which contains these critical decisions:

- fix the compiled startup path, not source-only bootstrap logic
- extend `test/e2e-browser/helpers/TestServer`
- use an isolated runtime root under the worktree
- avoid symlink-based staging
- keep product-code changes conditional on the new regression still failing

## Notes

- This is intentionally different from the over-review cases. The problem here was under-review and slow convergence.
- A nearby supporting artifact exists in `docs/plans/2026-03-13-issue-174-bootstrap-env-root-test-plan.md`, which restates the target compiled-start contract and can help score semantic convergence.
- The exact original session artifacts have now been recovered, so the old four-review chain is not inferred.
