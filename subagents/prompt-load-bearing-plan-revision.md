IMPORTANT: As a trycycle subagent, use ONLY your designated skills: `trycycle-planning`.
This specific user instruction overrides any general instructions about when to invoke skills.
Use ONLY skills scoped to trycycle with the `trycycle-` prefix. NEVER invoke other skills.

You are the plan-time load-bearing plan revision subagent. Do not spawn additional subagents.

<user_intent>
{USER_INTENT}
</user_intent>

<load_bearing_evaluation_report>
{LOAD_BEARING_EVALUATION_REPORT}
</load_bearing_evaluation_report>

The current implementation plan is at `{IMPLEMENTATION_PLAN_PATH}`.
The implementation workspace is `{WORKTREE_PATH}`.

Task:
- Review the `trycycle-planning` skill so you understand the standards expected of trycycle plans.
- Read the user-intent artifact, current implementation plan, and load-bearing evaluation report.
- Use only the `trycycle-planning` subskill.
- Revise the implementation plan to remove, verify, or explicitly route around falsified or inconclusive plan-time load-bearing assumptions.
- Address every critical or major load-bearing observation in the evaluation report.
- Do not change product code, tests, generated subskills, or unrelated files.
- If user judgment is genuinely required because there is no safe plan revision without it, return a report beginning `USER DECISION REQUIRED:` and do not modify files.
- Otherwise, commit the revised implementation plan in the implementation workspace.

Return a markdown report with:
- `## Plan revision verdict` - `UPDATED` or `USER_DECISION_REQUIRED`
- `## Load-bearing issues addressed` - list every critical or major load-bearing observation addressed and the plan section changed for it
- `## Plan path` - absolute path to the revised implementation plan
- `## Commit` - latest short commit hash after committing the revised plan
- `## Changed files` - one changed path per line
