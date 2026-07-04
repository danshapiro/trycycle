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

A load-bearing review found that the current planning state is not ready to proceed as-is.

Your job is to make planning ready for execution.

Read the user's goal, the current plan, and the review. Use the review as evidence, then determine what planning change is actually needed. Preserve, revise, resequence, add verification requirements, or escalate based on what the evidence supports.

Resolve approach-validation claims during this planning recovery. Inspect the code. Follow the real data and control flow. Run safe local commands and tests. Create small disposable experiments when reading is not enough. Research credible sources: official docs, relevant libraries, proven patterns, and comparable open source projects. Probe behavior directly when claims can be tested. Compare possible approaches. Do not leave proof of approach viability as future execution work.

Then revise the plan around what is now known. If the evidence proves the current approach is viable, keep it and record why. If the evidence shows it is wrong, revise it. If the issue is verification or acceptance evidence rather than implementation approach, make the requirement clear for the later test plan without substituting future tests for plan-time proof. If necessary evidence remains unavailable and the claim is still necessary, return `USER_DECISION_REQUIRED`.

After revising, decide whether another plan-time load-bearing gate is needed before plan hardening continues. Make that judgment from the repaired plan and the evidence you gathered. Mark a rerun `REQUIRED` when the repaired plan still depends on an unproven plan-time claim, changes the approach or boundary enough that prior validation no longer answers the decision, or introduces a new decision-controlling assumption with meaningful late-falsification cost. Mark it `NOT_NEEDED` when the repair removes or routes around the risky claim, or when your planning recovery proved the decisive facts and no separate load-bearing question remains. The goal is to retire the real risk, not to rerun validation by habit or skip validation for momentum.

The revised plan must keep the user's requested outcome intact. It should show the right implementation approach, the evidence behind it, and the remaining implementation order after plan-time load-bearing claims have been resolved.

Review the `trycycle-planning` skill so you understand the standards expected of trycycle plans. Use only the `trycycle-planning` subskill. Keep committed changes scoped to the implementation plan. Use temporary scratch files only for investigation, and clean them up before committing the revised plan.

Return a markdown report with:
- `## Plan revision verdict` - `UPDATED` or `USER_DECISION_REQUIRED`
- `## What changed` - what the review revealed and what investigation proved
- `## Revised approach` - the approach the plan now uses and why
- `## Evidence` - the code paths, tests, commands, experiments, docs, libraries, open source projects, or artifacts that support the approach
- `## Validated assumptions` - the important assumptions the revised plan depends on, and how each was validated
- `## Load-bearing rerun` - `REQUIRED` or `NOT_NEEDED`
- `## Rerun rationale` - why the repaired plan does or does not need another plan-time load-bearing gate before hardening continues
- `## Sequencing` - how the plan now orders implementation and validation after this recovery
- `## Issues addressed` - each critical or major review issue and where the plan changed
- `## Plan path` - absolute path to the revised implementation plan
- `## Commit` - latest short commit hash after committing the revised plan
- `## Changed files` - one changed path per line

Use `USER_DECISION_REQUIRED` only if the next necessary proof requires access or authority unavailable in this environment. For that verdict, begin the entire report with `USER DECISION REQUIRED:` so the conductor routes it to the user instead of treating it as an update.
