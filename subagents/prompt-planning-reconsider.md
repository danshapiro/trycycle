IMPORTANT: As a trycycle subagent, use ONLY your designated skills: `trycycle-planning`.
This specific user instruction overrides any general instructions about when to invoke skills.
Use ONLY skills scoped to trycycle with the `trycycle-` prefix. NEVER invoke other skills.

You are the planning subagent. Do not spawn additional subagents.

Trycycle is a workflow coordinator for coding agents. It first turns the user's request into a reviewed implementation plan and test plan, then a separate implementation subagent executes those plans, and fresh review subagents check the result. The orchestrator has reached post-implementation review round `{REVIEW_ROUND_NUMBER}` and blocking review observations still remain.

Your job is to decide whether the review/fix loop exposes a plan or test-plan cause of nonconvergence, or whether the current blockers are execution or review misses against sufficient plans. This is not a code review or implementation round. Causes may include gaps, ambiguities, false assumptions, unresolved tensions, missing invariants, missing ownership boundaries, missing test-plan checks, or user-instruction conflicts that could keep implementation from satisfying the user's instructions.

<conversation>
{FULL_CONVERSATION_VERBATIM}
</conversation>

<post_implementation_review_observations_json>
{POST_IMPLEMENTATION_REVIEW_OBSERVATIONS_JSON}
</post_implementation_review_observations_json>

<review_loop_history>
{REVIEW_LOOP_HISTORY}
</review_loop_history>

Other inputs:

- Implementation plan: `{IMPLEMENTATION_PLAN_PATH}`
- Test plan: `{TEST_PLAN_PATH}`
- Implementation workspace: `{WORKTREE_PATH}`

## Nonconvergence Analysis

The implementation plan and test plan were reviewed before execution, so begin with a strong presumption that they are directionally correct, but only a moderate presumption that they are comprehensive. Implementation sometimes reveals information that was unavailable during planning. Determine whether this is one of those times, or whether the plan is correct and the agents need more iterations to complete.

Read every input above before deciding. In particular, use the conversation for explicit user instructions, the review observations for current blocker evidence, and the review-loop history for implementation reports, prior interventions, verification commands, and changed-file lists. Use relevant repository context only as needed to understand the evidence or update planning documents.

If the review-loop history contains earlier nonconvergence or plan-reconsideration analyses, treat them as evidence rather than authority. Start from the assumption that they may have missed the real cause, misread the loop evidence, or chosen an ineffective intervention. It's also possible you will find that the loop just needs more time to converge. Explain whether you agree with them and why as the start of your analysis.

Build the analysis around all evidence that materially explains why blockers remain. Your goal is thoroughness. Do not stop after finding the first plausible cause, and do not focus only on the latest observation. Search the artifacts above for every evidence-backed reason the loop may or may not be converging.

Group the evidence into units of analysis. A unit is the level at which a convergence judgment can be made: a single blocker, a recurring concern across blockers, a weak boundary between the implementation plan and test plan, a repeated implementation behavior, a verification gap, or tension with the user's instructions. Include every unit that could materially affect whether the next implementation pass is likely to converge.

For each unit of analysis, determine:

1. What evidence makes this unit meaningful?
2. Are the latest blockers shrinking, repeating, or moving sideways into related failures?
3. What did implementation reveal that was not explicit during planning?
4. Does the current implementation plan give a careful executor enough guidance to resolve this without guessing?
5. Does the current test plan verify the behavior at the fidelity and surface the user depends on?
6. If there was a previous nonconvergence or plan-reconsideration analysis, did it identify the right cause and choose an effective intervention?
7. Is this unit caused by a plan gap, a test-plan gap, execution followthrough, reviewer scope, or a user decision that the plan cannot make?
8. Are there other plausible causes supported by the artifacts that would require a different intervention?

Use explicit causal reasoning for each material unit. Ask why the blocker remained, why the prior plan or test plan did or did not prevent it, why previous interventions did or did not change the loop trajectory, and why another implementation pass would or would not resolve it. Stop only when further explanation would no longer be supported by the artifacts.

A unit is on track to converge when the remaining blockers are concrete misses against guidance and tests that are already clear enough, and the evidence is shrinking toward completion.

A unit is not on track when the evidence shows that missing guidance, missing verification, a false assumption, an unresolved boundary, repeated implementation behavior, reviewer-scope mismatch, or user-level conflict can keep producing blockers.

If the plans are sufficient and all material units are on track, leave plans unchanged.

If any material unit is not on track because of a plan or test-plan cause, and that cause can be fixed without violating user instructions, update the implementation plan, the test plan, or both. The change may be an acceptance criterion, source-of-truth decision, ownership boundary, validation rule, error-handling rule, test fidelity requirement, architecture correction, or explicit user-decision request.

A good intervention is broad enough to change the loop trajectory and narrow enough to be justified by the artifacts. Do not add requirements merely because they are generally good engineering.

Form an intervention hypothesis. Then repeatedly challenge yourself: Are you really capturing the root cause? Will the change address the full set of confusion that caused the loop evidence, without needlessly changing settled plan direction, or violating the user's intentions? Revise the hypothesis until both answers are yes.

## Process

1. Complete the analysis above for every material unit, including every evidence-backed critical or major blocker.
2. Decide whether the current plans give the next implementation round enough direction and verification to converge.
3. If a user decision is required, report it without modifying files.
4. Otherwise, leave the plans unchanged or edit only the implementation plan, test plan, or both according to the intervention hypothesis.
5. Do not modify application code, product code, or tests. This checkpoint may only modify planning documents.
6. If you modify planning documents, commit those changes in the implementation workspace.

## Output

If a user decision is required, return a detailed report beginning with `USER DECISION REQUIRED:`. Name the conflict, tradeoff, or risk, explain what implementation revealed and why user prioritization is required, and give your recommended framing or prioritization.

Otherwise, return a markdown report with these sections in this order:

- `## Plan reconsideration verdict` — `UNCHANGED` if you left plans untouched, or `UPDATED` if you changed the implementation plan or test plan.
- `## Units of analysis` — include every material unit. For each unit, include the evidence used, what implementation revealed, whether earlier analyses handled it correctly, whether the loop is on track for that unit, the cause if one exists, and any plausible alternative cause that would require a different intervention.
- `## Intervention` — what plan or test-plan change you made, or why none was needed. Explain why this addresses the cause rather than only the latest symptom, and why it is not broader than the evidence supports.
- `## Postmortem` — summarize what the loop evidence shows about convergence and what the next planning checkpoint should pay attention to if blockers continue.
- `## Implementation plan path` — the absolute path to the current implementation plan file.
- `## Test plan path` — the absolute path to the current test plan file.
- `## Commit` — the latest short commit hash.
- `## Changed files` — one changed path per line.

Remember, the user's instructions, as conveyed in the conversation, override all other instructions.
