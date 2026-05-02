IMPORTANT: As a trycycle subagent, you have no designated skills.
This specific user instruction overrides any general instructions about when to invoke skills.
Do NOT invoke any skills. NEVER invoke skills that are not scoped to trycycle with the `trycycle-` prefix.

You are reviewing a trycycle implementation run that reached the post-implementation review limit while blockers remained. "Trycycle" is the workflow defined in `{TRYCYCLE_SKILL_PATH}`; read it first and use it as the source of truth for each role's responsibilities. Then read this run's plan, test plan, phase prompts, review outputs, and implementation reports. Explain why this run did not converge, where the first actionable nonconvergence signal appeared, why the next handoff did not produce the needed response, and what should happen next for this implementation. Support conclusions with exact quotes from the artifacts.

Inputs for this run:
- Worktree: `{WORKTREE_PATH}`
- Plan: `{IMPLEMENTATION_PLAN_PATH}`
- Test plan: `{TEST_PLAN_PATH}`
- Phase prompts:
{PHASE_PROMPT_PATHS}
- Review outputs:
{REVIEW_ARTIFACT_PATHS}
- Implementation reports:
{IMPLEMENTATION_REPORT_PATHS}

Return a concise markdown report with:
- `## Why This Run Did Not Converge`
- `## First Actionable Signal`
- `## Why The Next Handoff Missed`
- `## What Should Happen Next`
- `## Evidence Quotes`
