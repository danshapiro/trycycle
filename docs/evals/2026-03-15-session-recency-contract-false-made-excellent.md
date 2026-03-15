# Session Recency Contract False `MADE_EXCELLENT` Eval Candidate

## Source

- Repo under investigation: `/home/user/code/freshell/.worktrees/trycycle-session-recency-contract`
- User task theme: semantic session recency contract under trycycle
- Trycycle phase: plan-editor loop
- Analysis method: direct review of the stop transcript, plan commit chain, and downstream implementation commits

## Isolated review

- Input plan commit: `98f944fd`
- Input plan path: `docs/plans/2026-03-13-session-recency-contract.md`
- Review-produced commit: `b5972ab8`
- Actual verdict: `MADE-EXCELLENT`
- Expected verdict: `ALREADY-EXCELLENT`

## Why this is the strongest remaining over-review case

By the input plan `98f944fd`, the core contract was already stable and execution-ready:

- session-domain recency is renamed from `updatedAt` to `lastActivityAt`
- non-session `updatedAt` fields stay untouched
- providers derive semantic clocks from transcript events only
- append-only reparses stay monotonic
- invalidation is bounded by the session-directory projection

Those decisions survived into the final plan unchanged. The stop diagnosis for the original run said the same thing: the core contract stayed stable while the loop kept repartitioning the same work.

## What the unnecessary review changed

The `b5972ab8` review mostly re-sliced broad tasks into narrower ones:

- task count changed from `8` to `12`
- the same server and client cutover surfaces were redistributed into finer commit buckets
- the architecture and strategy gate were rewritten for clarity, not redirected around a new design decision

Round 5 added no new production file targets at all.

Relative to `98f944fd`, the only file-set additions were four tests:

- `test/server/codex-activity-exact-subset.test.ts`
- `test/server/ws-codex-activity.test.ts`
- `test/server/ws-session-repair-activity.test.ts`
- `test/server/ws-terminal-create-session-repair.test.ts`

Only one of those four was actually touched downstream: `test/server/codex-activity-exact-subset.test.ts`. The other three were never edited on the implementation branch.

That makes the final review look much more like task/inventory churn than like discovery of a missing contract seam.

## Why round 4 already looks good enough

The input plan `98f944fd` already named the live implementation surfaces needed to land the feature:

- provider semantic clocks
- core model rename and monotonic indexer behavior
- session-directory projection and invalidation boundary
- search, pagination, router, CLI, and diff contract
- client API/store contract
- selector/UI contract
- fallout sweep and full verification

The downstream implementation chain lands those same categories in order:

- `1105ac9d` Claude semantic clocks
- `0abff2f4` Codex semantic clocks
- `36d931ac` session index recency
- `f9acd957` server consumers
- `04ee8d4c` shared projection contract
- `5cfeeadf` service cursors/invalidation
- `d6cc25f9` public server contract
- `b268db09` client API contract
- `0e250eb2` client state
- `cc67eeb9` selectors
- `3da2d795` client UI
- `9128247e` final fallout cut

Round 5 maps more neatly onto that commit chain, but it does not appear to add a comparably new requirement.

## Why this is good eval material

This case catches a different false-positive pattern than the first two evals:

- the plan was not "perfect"
- but it had already crossed the execution-ready threshold
- the review still returned `MADE-EXCELLENT` for repartitioning and test inventory changes rather than for discovering a genuinely new contract bug

That is useful for training against plan-editor loops that keep rewriting a stable plan because narrower task boundaries are always possible.

## Suggested eval framing

Use the plan at commit `98f944fd` as the input plan.

Expected behavior:

- Verdict: `ALREADY-EXCELLENT`
- No file edits
- No new commit

Failure condition:

- Returns `MADE-EXCELLENT`
- Re-slices tasks or test inventory without identifying a concrete missing contract requirement

## Notes

- This is a lower-confidence eval than the DirectorDeck provider-error case.
- The final review did add one legitimate regression-test surface (`test/server/codex-activity-exact-subset.test.ts`), so the failure here is not "pure formatting churn."
- Even with that caveat, this is the strongest remaining candidate I found for a third false-`MADE_EXCELLENT` eval from the available five-round-stop runs.
