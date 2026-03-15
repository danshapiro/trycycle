# Eval Notes

This folder holds plan-review eval candidates taken from real trycycle runs.

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

## How to read the set

The three notes cover different review failures:

- DirectorDeck: the plan was already good enough and should have been left alone.
- Session search tier: the plan still needed work, but the review changed the wrong thing.
- Session recency contract: the plan had likely crossed the execution-ready threshold, but the review kept tightening task structure anyway.

If a future run is ambiguous, compare it against these categories before adding another eval note.
