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

Work in the implementation workspace at `{WORKTREE_PATH}`.

{{#if POST_IMPLEMENTATION_REVIEW_OBSERVATIONS_JSON}}
<post_implementation_review_observations_json>
{POST_IMPLEMENTATION_REVIEW_OBSERVATIONS_JSON}
</post_implementation_review_observations_json>
{{/if}}

A skipped test is a failed test — there are no "legitimate" skips in a final run. After running tests, if ANY test was skipped: identify why it skipped, then make it run and pass. Exhaust every option to make it run. If after genuine effort a test still cannot run and pass without weakening it, halt immediately, write a postmortem of what you tried, and escalate to the user. Never report success while any tests remain skipped.

Implement using TDD: for each feature or component, first establish the red state with the highest-priority automated check or checks from the test plan. Reuse or extend high-value existing tests when they already cover the behavior; when coverage is missing, write the new failing test or tests first. If the test plan specifies harnesses to build, build those first.

{{#if POST_IMPLEMENTATION_REVIEW_OBSERVATIONS_JSON}}Fix the implementation against the attached review observations directly. Treat them as observed evidence and verification targets, not as optional suggestions.{{/if}}

Commit your changes, then return a markdown report with these sections in this order:
- `## Implementation summary` — concise implementation summary
- `## Verification results` — verification commands and outcomes
- `## Commit` — the latest short commit hash
- `## Changed files` — one changed path per line
