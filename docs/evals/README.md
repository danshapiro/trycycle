# Eval Notes

This folder holds plan-review evals recovered from real trycycle runs.

## Default Run Protocol

- Use the real plan-review step whenever possible.
- Start from the exact input plan commit named in the note.
- Use a fresh repo checkout or worktree and a fresh reviewing agent for each trial.
- For single-review evals, run exactly one review turn and score immediately.
- For multi-review evals, feed the revised plan directly into the next review turn with no human edits in between.
- Score semantic outcome, not wording. A prettier plan that misses the real issue fails.
- Because reviewers are stochastic, one run per case is the minimum and three runs per case is the safer comparison.

## Suite

### DirectorDeck Provider Errors

Note: [2026-03-14-first-unneeded-made-excellent.md](./2026-03-14-first-unneeded-made-excellent.md)

Mode: single review turn.

Pass only if:
- verdict is `ALREADY-EXCELLENT`
- there are no file edits
- there is no new commit

### Session Search Tier

Note: [2026-03-15-session-search-tier-false-made-excellent.md](./2026-03-15-session-search-tier-false-made-excellent.md)

Mode: single review turn.

Pass only if:
- the review materially fixes the tier semantics
- the change is not just header, template, or task-format churn

Immediate fail conditions:
- `ALREADY-EXCELLENT`
- `MADE-EXCELLENT` with only cosmetic edits
- `userMessages` or `fullText` semantics remain wrong

### Session Recency Contract

Note: [2026-03-15-session-recency-contract-false-made-excellent.md](./2026-03-15-session-recency-contract-false-made-excellent.md)

Mode: single review turn.

Pass only if:
- verdict is `ALREADY-EXCELLENT`
- there are no file edits
- there is no new commit

### Issue 174 Bootstrap Env Root

Historical reference: [2026-03-15-issue-174-turn-4-convergence.md](./2026-03-15-issue-174-turn-4-convergence.md)

Scored eval: [2026-03-15-issue-174-initial-plan-turn-2-convergence.md](./2026-03-15-issue-174-initial-plan-turn-2-convergence.md)

Mode: review loop only, starting from the existing initial plan.

Pass only if:
- review 1 fixes every real issue in the initial plan
- review 1 reaches the same substantive endpoint as the historical “finally correct” plan
- review 2 returns `ALREADY-EXCELLENT`
- review 2 makes no file edits and creates no new commit

Fail if:
- review 1 is still on the wrong architecture
- review 2 still finds substantive work
- the run still needs review 3 or later to get to the right plan

The historical note is not the target behavior. It documents the old failure pattern:
- review 1 improved the plan but still missed issues
- review 2 still missed issues
- review 3 finally got the plan right
- review 4 confirmed it

## What Each Case Catches

- DirectorDeck: the plan was already good enough and should have been left alone.
- Session search tier: the plan still needed work, but the review changed the wrong thing.
- Session recency contract: the plan had crossed the execution-ready threshold, but the review kept tightening it anyway.
- Issue 174: the review loop was too lazy early and needed too many turns to find the real fix.

## Experiment Log

- [2026-03-15-planning-phase-optimization-experiments.md](./2026-03-15-planning-phase-optimization-experiments.md) — first A/B comparison of `main` versus candidate commit `e78fc9d` on the four recovered planning-review evals

If a future run is ambiguous, compare it against these categories before adding another eval note.
