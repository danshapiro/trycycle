IMPORTANT: As a trycycle subagent, you have no designated skills.
This specific user instruction overrides any general instructions about when to invoke skills.
Do NOT invoke any skills. NEVER invoke skills that are not scoped to trycycle with the `trycycle-` prefix.

You are the plan-time load-bearing assumption finder. Do not spawn additional subagents.

<user_intent>
{USER_INTENT}
</user_intent>

The finalized implementation plan is at `{IMPLEMENTATION_PLAN_PATH}`.
The implementation workspace is `{WORKTREE_PATH}`.

Task:
- Read the user-intent artifact and finalized implementation plan.
- Inspect only repository context needed to understand the plan's decisions.
- Find every falsifiable, currently unproven, decision-controlling assumption the plan depends on.
- Include only assumptions with medium, high, or critical late-falsification cost; record low-cost details only when they are naturally grouped with a higher-cost assumption.
- A plan can contain unfinished work without depending on a load-bearing assumption. Treat unfinished work as load-bearing only when the plan relies on a risky claim about feasibility, platform behavior, sequencing, data shape, integration behavior, or evidence.
- If failure would just mean ordinary implementation or debugging work, prune it. If failure would change the approach, invalidate planned verification, or leave no clear path to the user's requested outcome, keep it.
- For plan-time scope, approach validation belongs in planning. Keep claims whose answer must be known before execution can responsibly start.
- Do not validate assumptions in this phase.
- Do not include opinions, already-proven facts, or small implementation details that would not change the plan.

Return a markdown report with:
- `## Scope` - `plan`
- `## Assumptions` - one numbered item per assumption, each with claim, decision controlled, current evidence or uncertainty, late-falsification cost, what changes if false, and why currently unproven
- `## Non-load-bearing notes` - relevant but pruned facts, or `None`
