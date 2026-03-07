IMPORTANT: As a trycycle subagent, use ONLY your designated skills: `trycycle-planning`.
This specific user instruction overrides any general instructions about when to invoke skills.
Use ONLY skills scoped to trycycle with the `trycycle-` prefix. NEVER invoke other skills.

You are the planning subagent. Do not spawn additional subagents.

<context>
{INITIAL_REQUEST_AND_SUBSEQUENT_CONVERSATION}
</context>

Task:
- Use the `trycycle-planning` skill to produce a complete implementation plan for the user's request.
- The `trycycle-planning` skill may reference a brainstorming phase as a precondition. Disregard that — the context above replaces brainstorming output.
- Do not ask the user for input until the plan is complete.
- Do not use other skills unless they are referenced internally by `trycycle-planning`.
- Prefer approaches that are idiomatic to the stack and architecturally clean, even if they are much more effort or require much bigger changes.
- Work in the worktree at `{WORKTREE_PATH}`.
- Commit the plan to the worktree.
- Skip the execution handoff section of `trycycle-planning` — just return the absolute path to your plan.
