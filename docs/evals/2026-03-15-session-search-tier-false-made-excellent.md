# Session Search Tier False `MADE_EXCELLENT` Eval Candidate

## Source

- Repo under investigation: `/home/user/code/freshell/.worktrees/codex-fix-session-search-tier`
- User task theme: lane 2 session-directory search tier regression under trycycle
- Trycycle phase: plan-editor loop
- Analysis method: subagent-assisted review of the plan commit chain (`14c0ef9c -> fa4023e3 -> 5127687c -> a3fbe08d`)

## Isolated review

- Input plan commit: `fa4023e3`
- Input plan path: `docs/plans/2026-03-14-fix-session-search-tier.md`
- Review-produced commit: `5127687c`
- Actual verdict: `MADE-EXCELLENT`

## Why this is the first clearly bad `MADE_EXCELLENT`

This case is different from the earlier DirectorDeck eval.

Here, the input plan was **not** already excellent. A real improvement was still needed, because the plan preserved the wrong session-search semantics:

- `title` should be title + summary only
- `userMessages` should be file-backed user-message search
- `fullText` should be file-backed user + assistant search

The input plan still described:

- `userMessages` as in-memory `title + summary + firstUserMessage`
- `fullText` as JSONL file search with an in-memory fallback

So a plan edit was warranted. The problem is that `5127687c` spent its review on template normalization instead of fixing the real semantic defect.

## Why the earlier review is not the eval

I am not using `14c0ef9c -> fa4023e3` as the primary eval because that first review made some concrete, defensible improvements even though it still missed the core semantic bug.

The first review:

- simplified the service test typing (`Partial<CodingCliSession>` instead of a brittle `Parameters<...>` chain)
- corrected router test setup details
- added a refactor task for `applyFullTextSearch`

That review was insufficient, but it was not pure churn.

## Why `5127687c` is the eval candidate

The `5127687c` review is the first clearly false-positive `MADE_EXCELLENT` in this sequence:

- commit message: `plan: align header format to trycycle-planning template (add Architecture field, retitle)`
- diff size: 16 lines changed
- effect: mostly header/template normalization

It preserved the same wrong semantics from `fa4023e3`, including:

- `userMessages` staying in-memory / `firstUserMessage` based
- `fullText` keeping the in-memory fallback

So the review claimed success while leaving the actual regression contract unfixed.

## Why this is good eval material

This is a clean example of a different planner failure mode:

- the planner correctly sensed that the plan was not yet done
- but it applied only superficial/template edits
- and still certified the output as `MADE-EXCELLENT`

That makes it useful for catching reviews that optimize formatting while failing to repair the missing requirement.

## Suggested eval framing

Use the plan at commit `fa4023e3` as the input plan.

Expected behavior:

- The reviewer must materially correct the search-tier semantics.
- Cosmetic/template-only changes do **not** count as a valid `MADE-EXCELLENT`.

Failure condition:

- Returns `MADE-EXCELLENT`
- Changes only header/template/task formatting
- Leaves `userMessages` and `fullText` semantics wrong

## Notes

- This eval should not be scored with the same expectation as the DirectorDeck case. The correct result here is not necessarily `ALREADY-EXCELLENT`; the key is that a successful review must fix the real semantic defect, not just prettify the document.
