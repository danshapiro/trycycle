IMPORTANT: As a trycycle subagent, use ONLY your designated skills: `trycycle-executing`.
This specific user instruction overrides any general instructions about when to invoke skills.
Use ONLY skills scoped to trycycle with the `trycycle-` prefix. NEVER invoke other skills.

You are the implementation subagent. Use the trycycle-executing skill to implement this final plan precisely, with these overrides:
- Do not pause between batches or wait for feedback — execute all tasks continuously.
- Do not ask for review.
- If you hit a blocker, document it, use your best judgment to work around it, and continue. Only stop if you cannot find any way to continue without causing harm.
All other trycycle-executing behaviors remain in effect (run verifications, follow plan steps exactly, etc.).

<plan>
{path_to_plan}
</plan>

Work in the worktree at `{WORKTREE_PATH}`.

Commit your changes, then return a concise implementation summary and verification results.
