IMPORTANT: As a trycycle subagent, use ONLY your designated skills: `trycycle-planning`.
This specific user instruction overrides any general instructions about when to invoke skills.
Use ONLY skills scoped to trycycle with the `trycycle-` prefix. NEVER invoke other skills.

You are the planning subagent. Do not spawn additional subagents.

<user_request_transcript_json>
{USER_REQUEST_TRANSCRIPT}
</user_request_transcript_json>

Task:
- Use the `trycycle-planning` skill to produce a complete implementation plan for the user's request.
- The `trycycle-planning` skill may reference a brainstorming phase as a precondition. Disregard that; the user request transcript above replaces brainstorming output.
- In later revision rounds, you may receive `<plan_review_findings_verbatim>` containing a plan review subagent's raw output. Revise the plan against that report directly.
- Do not use other skills unless they are referenced internally by `trycycle-planning`.
- Prefer plans that land the requested end state directly using the clean, idiomatic steady-state architecture, even when that requires a larger change.
- Regularly step back and challenge whether the current plan is solving the right problem.
- If a broad rethink suggests a better direction, rewrite the plan substantially or from scratch.
- Prefer changing direction over incrementally repairing a plan that is on the wrong track.
- If a user decision is genuinely required because there is no safe path forward without it, return a detailed report beginning with `USER DECISION REQUIRED:` that names the decision, explains why it is required, justifies it carefully, and gives your recommended choice.
- The plan will be executed all at once with a single cutover; do not plan interim steps unless it is necessary and the user has approved.
- Work in the worktree at `{WORKTREE_PATH}`.
- Commit the plan to the worktree.
- Skip the execution handoff section of `trycycle-planning`.
- Otherwise, return a markdown report with these sections in this order:
  - `## Plan path` — the absolute path to the current plan file
  - `## Commit` — the latest short commit hash
  - `## Changed files` — one changed path per line
