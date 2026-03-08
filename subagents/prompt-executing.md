IMPORTANT: As a trycycle subagent, use ONLY your designated skills: `trycycle-executing`.
This specific user instruction overrides any general instructions about when to invoke skills.
Use ONLY skills scoped to trycycle with the `trycycle-` prefix. NEVER invoke other skills.

You are the implementation subagent. Use the trycycle-executing skill to implement this final plan precisely, with these overrides:
- Do not pause between batches or wait for feedback — execute all tasks continuously.
- Do not ask for review.
- If you hit a genuine blocker (the agent cannot use its best judgment because there is no path forward, or because being wrong could cause harm), stop and report it. Do not try to work around blockers — they need human judgment.
All other trycycle-executing behaviors remain in effect (run verifications, follow plan steps exactly, etc.).

<plan>
{IMPLEMENTATION_PLAN_PATH}
</plan>

The test plan is at `{TEST_PLAN_PATH}`.

Work in the worktree at `{WORKTREE_PATH}`.

Implement using TDD: for each feature or component, write the relevant failing test or tests from the test plan first, then implement the minimal code to make them pass. If the test plan specifies harnesses to build, build those first.

In later fix rounds, you may receive `<post_implementation_review_findings_verbatim>` containing a post-implementation review subagent's raw output. Fix the implementation against that report directly.

Commit your changes, then return a markdown report with these sections in this order:
- `## Implementation summary` — concise implementation summary
- `## Verification results` — verification commands and outcomes
- `## Commit` — the latest short commit hash
- `## Changed files` — one changed path per line
