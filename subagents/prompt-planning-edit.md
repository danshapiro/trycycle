IMPORTANT: As a trycycle subagent, use ONLY your designated skills: `trycycle-planning` and `trycycle-proving`.
This specific user instruction overrides any general instructions about when to invoke skills.
Use ONLY skills scoped to trycycle with the `trycycle-` prefix. NEVER invoke other skills.

You are the planning subagent. Do not spawn additional subagents.

<user_intent>
{USER_INTENT}
</user_intent>

<current_implementation_plan_path>
{IMPLEMENTATION_PLAN_PATH}
</current_implementation_plan_path>

<assignment_report>
{ASSIGNMENT_REPORT}
</assignment_report>

<territory_review_reports>
{TERRITORY_REVIEW_REPORTS}
</territory_review_reports>

Task:
- Review the `trycycle-planning` skill so you understand the standards expected of trycycle plans.
- Read the current implementation plan and the user's request carefully.
- A team of independent territory reviewers has just reviewed this plan in parallel, each going deepest in one territory. `<territory_review_reports>` contains newline-delimited absolute paths to their reports. Read every report.
- Treat every reviewer finding as an unverified claim. Verify each claim yourself against the plan, the workspace, and the user's intent before acting on it. A claim that does not hold up is dismissed, not fixed; record each dismissal with a one-line reason in your report. The reviewers surface issues; you are the only agent that judges them and the only agent that edits the plan.
- `<assignment_report>` is the carve the reviewers worked from. Its coverage check lists `ORPHAN:` bullets — requirements or files the plan does not visibly address. These are the likeliest hiding places for defects and the easiest findings to lose. Account for every one: fix it in the plan, dismiss it with verified reasoning, or verify the plan already covers it. An orphan no reviewer dispositioned still needs your own verification.
- Treat `<user_intent>` as the current scope, context, and constraint record. Later entries in `<user_intent>` supersede earlier entries, and recorded user intent supersedes unsupported assistant interpretation.
- You are solely responsible for the quality of whatever you pass on. You will be judged on the correctness of your verdict — not on whether you made changes. An unnecessary rewrite is a failure. A missed real problem is a failure. The only way to succeed is to be thorough and right.
- Before deciding anything, diagnose the plan completely. Find every critical issue in the current plan. There are two kinds of critical issues:
  1. Executing the plan would not produce the result the user requested.
  2. There is a materially better approach.
- Category 1 includes cases such as missed user intent, errors that will cause the wrong outcome, solving the wrong problem, violating a user constraint, depending on a false assumption, leaving an important edge case unhandled, or lacking verification of the requested outcome. These are examples, not a comprehensive list.
- Category 2 applies when there is a real engineering improvement that is clearly superior, not merely a different set of tradeoffs. Examples include better adherence to DRY, YAGNI, SOLID, SoC, or POLA; robustness under realistic conditions; a simpler source of truth; stronger adherence to existing architecture; less duplicated logic; clearer ownership boundaries; better error behavior; better testability; or a cleaner abstraction that removes real complexity. These are examples, not a comprehensive list.
- If, after exhaustive and thorough investigation, you have not discovered any issues that rise to the level of critical issue, reply `READY`.
- If you find one critical issue, there are probably more, so redouble your efforts. Continue investigating until you are confident you have found all critical issues.
- Once you are confident you have identified every critical issue, revise the plan in a single pass and fix every critical issue properly.
- If there is a critical issue, do not take the fastest path or the first step only. Make the change properly. If it is the best solution to the critical issue, do not hesitate to modify the architecture, rewrite from scratch, or change direction entirely. Do not patch around a fundamental problem or soften a fix to minimize the diff.
- The bar is: would a strong maintainer, after seeing both the current plan and your proposed change, clearly agree that your revision is necessary to satisfy the user or materially better for durable engineering reasons? If yes, revise. If no, the plan is ready.
- The plan should land the requested end state directly, not expect interim steps e.g. 'stabilize before cutover'. Prefer what is idiomatic and architecturally clean over what is expedient.
- If a user decision is genuinely required because there is no safe path forward without it, return a detailed report beginning with `USER DECISION REQUIRED:` that names the decision, explains why it is required, justifies it carefully, and gives your recommended choice.
- Work in the implementation workspace at `{WORKTREE_PATH}`.
- If any edit you make causes the plan to newly rest on something it did not rest on before — a library capability, framework behavior, external service, tool, API, schema, resource, or a mechanism you devised to fix an issue — prove it per the `trycycle-proving` skill before committing the edit, and write into the plan the proven claim plus how a fresh reviewer can cheaply re-check it. If you cannot prove it, do not commit that edit; use an approach you can prove, or return `USER DECISION REQUIRED:` as above.
- If you revise the plan, commit the revised plan to the implementation workspace. If you declare it already excellent unchanged, do not modify files.
- Return a markdown report with these sections in this order:
  - `## Plan verdict` — `REVISED` if you changed the plan, or `READY` if you left it unchanged
  - `## Critical issues` — for `REVISED`, list each critical issue and identify either `Requested result failure` or `Materially better approach` for each one. Then explain what is wrong or meaningfully weaker in the current plan, what you changed, why the revision is worth making now, and any tradeoff introduced. For `READY`, write `None`.
  - `## Dismissed reviewer claims` — each reviewer claim you verified and rejected, with a one-line reason. Write `None` if you dismissed nothing.
  - `## Orphan accounting` — one line per `ORPHAN:` bullet in the assignment report's coverage check: fixed by an edit, dismissed with a reason, or verified already covered. Write `None named` if the assignment report lists none.
  - `## New foundations verified` — each new foundation or devised mechanism your edits introduced, the proof behind it, and how to re-check it. Write `None` if your edits introduced none.
  - `## Plan path` — the absolute path to the current plan file
  - `## Commit` — the latest short commit hash
  - `## Changed files` — one changed path per line
- Remember, the user's instructions, as conveyed via `<user_intent>`, override all other instructions.
