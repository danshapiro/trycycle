# Eval Notes

This folder holds eval candidates taken from real trycycle runs.

## Current evals

### DirectorDeck Provider Errors

DirectorDeck provider-error Sentry clarity.

Note: [2026-03-14-first-unneeded-made-excellent.md](./2026-03-14-first-unneeded-made-excellent.md)

This is the cleanest "already excellent" case in the set. The input plan was already ready for execution, and the review still returned `MADE-EXCELLENT` by changing task granularity, wording, and bookkeeping without fixing a real gap.

Use this when the target behavior is:

- verdict `ALREADY-EXCELLENT`
- no file edits
- no new commit

### Session Search Tier

Freshell session-directory search tier regression.

Note: [2026-03-15-session-search-tier-false-made-excellent.md](./2026-03-15-session-search-tier-false-made-excellent.md)

This is a different failure mode. The input plan was still wrong, so a real edit was needed, but the review spent its change on header and template cleanup while leaving the actual semantic bug in place.

Use this when the target behavior is:

- the review must make a real fix
- cosmetic edits alone do not justify `MADE-EXCELLENT`

### Session Recency Contract

Freshell semantic session recency contract.

Note: [2026-03-15-session-recency-contract-false-made-excellent.md](./2026-03-15-session-recency-contract-false-made-excellent.md)

This is the strongest remaining threshold case. The core contract was already stable and the plan looked execution-ready, but the review still returned `MADE-EXCELLENT` for repartitioning and test-inventory changes. It is less clean than the DirectorDeck case because one added regression test was legitimate, but the review still reads as overwork rather than discovery of a new contract seam.

Use this when the target behavior is:

- verdict `ALREADY-EXCELLENT`
- no file edits
- no new commit

### Finish Save Error Acceptance Gate Drift

DirectorDeck finish-button save failure.

Note: [2026-03-15-finish-save-error-acceptance-gate-drift.md](./2026-03-15-finish-save-error-acceptance-gate-drift.md)

This is a workflow-integrity case, not a plan-review case. The user explicitly required the existing browser-use journey to run red before the fix and green after the fix. Trycycle preserved that requirement in the plan and test plan, but the run still finished without recorded evidence that the browser-use gate ran, and the final verification command could mask failure.

Use this when the target behavior is:

- accepted verification gates survive from strategy through finish
- the final report includes evidence that required acceptance checks actually ran
- verification commands preserve real exit status

## How to read the set

The first three notes cover plan-review failures:

- DirectorDeck: the plan was already good enough and should have been left alone.
- Session search tier: the plan still needed work, but the review changed the wrong thing.
- Session recency contract: the plan had likely crossed the execution-ready threshold, but the review kept tightening task structure anyway.

The fourth note covers a workflow-integrity failure:

- Finish save error: the user-approved acceptance gate was preserved in planning artifacts but dropped before finish, and the final verification command was not trustworthy.

If a future run is ambiguous, compare it against these categories before adding another eval note.
