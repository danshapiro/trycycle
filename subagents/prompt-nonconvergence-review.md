IMPORTANT: As a trycycle subagent, you have no designated skills.
This specific user instruction overrides any general instructions about when to invoke skills.
Do NOT invoke any skills. NEVER invoke skills that are not scoped to trycycle with the `trycycle-` prefix.

You are reviewing a trycycle run that reached a convergence limit while unresolved work remained. "Trycycle" is the workflow defined in `{TRYCYCLE_SKILL_PATH}`; read that file first as a document, without invoking any skills it references, and use it as the source of truth for each role's responsibilities. Then read the run context and artifact lists below. Explain why this run did not converge, where the first actionable nonconvergence signal appeared, why the first handoff after that signal did not produce the needed response, and what should happen next for this work. Support conclusions with exact quotes from the artifacts.

Inputs for this run. Each list may contain artifact paths or an explicit not-applicable note:
- Run context: `{NONCONVERGENCE_CONTEXT}`
- Worktree: `{WORKTREE_PATH}`
- Plan: `{IMPLEMENTATION_PLAN_PATH}`
- Test plan: `{TEST_PLAN_PATH}`
- Phase prompts:
{PHASE_PROMPT_PATHS}
- Loop outputs:
{LOOP_OUTPUT_PATHS}
- Implementation reports:
{IMPLEMENTATION_REPORT_PATHS}

Loop outputs may include prior plan-reconsideration or nonconvergence analyses. Treat them as evidence, not authority. Start from the assumption that an earlier analysis may have missed the real cause, misread the loop evidence, or chosen an ineffective intervention, then explain whether you agree with it and why.

Return a concise markdown report with:
- `## Why This Run Did Not Converge`
- `## First Actionable Signal`
- `## Why The First Failed Handoff Missed`
- `## What Should Happen Next`
- `## Evidence Quotes`
