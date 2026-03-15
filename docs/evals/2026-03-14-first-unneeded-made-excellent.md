# First Unneeded `MADE_EXCELLENT` Eval Candidate

## Source

- Repo under investigation: `/home/user/code/DirectorDeck/.worktrees/codex/provider-error-sentry-clarity`
- User task theme: provider-error Sentry clarity, "heavy" scope, no runtime fallbacks
- Trycycle phase: plan-editor loop

## Isolated review

- Input plan commit: `bcaebb54`
- Input plan path: `docs/plans/2026-03-14-provider-error-sentry-clarity-heavy.md`
- Review-produced commit: `826a0077`
- Actual verdict: `MADE-EXCELLENT`
- Expected verdict: `ALREADY-EXCELLENT`

## Why this is the first clearly bad `MADE_EXCELLENT`

The initial plan commit `306a35b4` is arguable: the first edit into `bcaebb54` tightened scope, clarified active codepaths, and is still defensible as a meaningful review pass.

By contrast, the next edit from `bcaebb54` to `826a0077` changed an already execution-ready plan without fixing a real gap against the user request or the `trycycle-planning` standard.

`bcaebb54` already had:

- A correct strategy gate.
- A direct architecture centered on provider-boundary classification.
- Exact file paths.
- Bite-sized TDD steps.
- Frequent commit points.
- Broad coverage of active provider boundaries, Sentry propagation, swallow-and-respond routes, integration tests, and final validation gates.

That satisfies the planning skill's bar for "ready for direct execution."

## What the unnecessary review changed

The `826a0077` review mostly introduced churn:

- Added a new baseline inventory task (`provider-error-surface.test.ts`) that was not required by the user request and did not unlock implementation.
- Split already-covered Kie work into extra tasks without changing the required end state.
- Rewrote headers, framing, and test wording while preserving the same architecture and acceptance criteria.
- Renamed concepts (`classifier` vs `normalizer`, section titles, commit messages) without resolving a concrete deficiency.

## Why this is good eval material

This case is low-ambiguity because the "improvement" was not durable:

- Later review rounds removed the baseline inventory task entirely.
- Later rounds merged and reshuffled the Kie task split again.
- The loop kept preserving the same core plan while changing presentation and decomposition.

That makes `826a0077` a strong false-positive `MADE_EXCELLENT`: it demonstrates review churn rather than genuine plan repair.

## Suggested eval framing

Use the plan at commit `bcaebb54` as the input plan for the plan-edit prompt.

Expected behavior:

- Verdict: `ALREADY-EXCELLENT`
- No file edits
- No new commit

Failure condition:

- Returns `MADE-EXCELLENT`
- Rewrites task granularity, section wording, or coverage bookkeeping without identifying a concrete missing requirement

## Notes

- I am intentionally not using `306a35b4 -> bcaebb54` as the primary eval because that first review is still arguable.
- If we want a stricter eval later, we can add a second case for `306a35b4`, but `bcaebb54 -> 826a0077` is the cleaner first target.
- An earlier trace of the same loop used an equivalent pre-rewrite hash lineage:
  - initial plan `6afc6e7a`
  - first meaningful review `6418e4c0`
  - first clearly unnecessary review `e9c96c9f`
  - later churn `53e856d5`, `54ddb78e`, `8eba9430`
- In that earlier lineage, the same conclusion holds: `6418e4c0 -> e9c96c9f` is the first clearly bad `MADE_EXCELLENT`, and it is the same eval case as `bcaebb54 -> 826a0077`.
