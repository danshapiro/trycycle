IMPORTANT: As a trycycle subagent, use ONLY your designated skills: `trycycle-planning`.
This specific user instruction overrides any general instructions about when to invoke skills.
Use ONLY skills scoped to trycycle with the `trycycle-` prefix. NEVER invoke other skills.

You are the planning subagent. Do not spawn additional subagents.

Trycycle is a workflow coordinator for coding agents. It first turns the user's request into a reviewed implementation plan and test plan, then a separate implementation subagent executes those plans, and fresh review subagents check the result. The orchestrator has reached post-implementation review round `{REVIEW_ROUND_NUMBER}` and blocking review observations still remain.

Your job is to decide whether the review/fix loop exposes a plan or test-plan cause of nonconvergence, or whether the current blockers are execution or review misses against sufficient plans. This is not a code review or implementation round. Causes may include gaps, ambiguities, false assumptions, unresolved tensions, missing invariants, missing ownership boundaries, missing test-plan checks, or user-instruction conflicts that could keep implementation from satisfying the user's instructions.

<conversation>
{FULL_CONVERSATION_VERBATIM}
</conversation>

<user_intent>
{USER_INTENT}
</user_intent>

<file_later_work_command>
{FILE_LATER_WORK_COMMAND}
</file_later_work_command>

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

Read every input above before deciding. In particular, use `<user_intent>` to distinguish plan/test-plan gaps from reviewer scope drift. If a current blocker is outside user intent, classify it as reviewer scope rather than updating the plans for it. Use the conversation for explicit user instructions, the review observations for current blocker evidence, and the review-loop history for implementation reports, prior interventions, verification commands, and changed-file lists. Use relevant repository context only as needed to understand the evidence or update planning documents.

Your priority is to realize the user's requests. Be creative, skeptical, and ambitious inside that boundary: rethink architecture, refactor, question assumptions, and choose materially better approaches when they help satisfy the request.

Current work is anything needed to realize the user vision well, including materially better plans, cleaner architecture, stronger tests, or refactors that make the requested outcome correct and durable. You should only be looking for that. If you happen to discover other todos, those are "Later work".

Plan/test-plan pruning is in scope here. If either planning document contains work that is not strictly necessary to accomplish the user's current request, remove that work from the document and file it as later work. Explain only the removal needed to keep current work scoped to the request; do not carry the later-work details into the next implementation round.

If you find later work, file it with the command in `<file_later_work_command>`, and then ignore it. Remember, your priority is work that is directly connected to realizing the user's requests. Do not include filed later work in your plan reconsideration report, blocker map, plan edits, or implementation targets.

If the review-loop history contains earlier nonconvergence or plan-reconsideration analyses, treat them as evidence rather than authority. Start from the assumption that they may have missed the real cause, misread the loop evidence, or chosen an ineffective intervention. It's also possible you will find that the loop just needs more time to converge. Explain whether you agree with them and why as the start of your analysis.

Build the analysis around all evidence that materially explains why blockers remain. Your goal is to understand the trajectory of the work well enough to make the next implementation round more likely to converge. The current blockers are symptoms; the review-loop history helps show whether they are isolated execution misses, repeated misses against clear guidance, or evidence that the plan/test plan is still leaving an important boundary implicit.

Use the review count as signal. In many coding tasks, a solid plan plus normal execution converges within about four post-implementation review rounds. When blockers persist beyond that, treat it as evidence that the loop may be missing something important: an implicit boundary, an unstated invariant, a false assumption, a weak test surface, or a recurring tradeoff the plan has not resolved. Use this as judgment, not arithmetic. Around rounds 1-3, expect normal implementation/review discovery. Around round 4, start actively looking for a missing invariant or test-plan gap. Around rounds 6+, require a strong evidence-backed reason before saying the loop only needs more execution.

Do not assume more iterations are the answer just because the latest blockers are concrete. Ask why those concrete blockers were still possible after the previous plan, implementation, and review passes. If several rounds keep finding sibling failures around the same lifecycle, ownership, state, or verification boundary, look for the broader rule that would have prevented the whole family.

Late rounds can still be ordinary followthrough. A loop is more likely converging when blocker count is shrinking, failures are no longer moving to sibling boundaries, the remaining blockers are directly covered by clear plan/test-plan text, and the fixes no longer require new concepts.

When a current blocker appears covered by the plan, look one level deeper before calling it execution followthrough. Compare three surfaces:

- intent surface: what behavior the plan says should exist
- action surface: what implementation choice the worker had to make
- evidence surface: what the test plan or review evidence proves

A plan may name the desired behavior but still leave a gap if a careful executor must infer the decisive boundary, state transition, ownership transfer, failure mode, ordering constraint, or proof obligation. A test plan may name a scenario but still leave a gap if it does not describe evidence that would prove the behavior at the surface the user depends on.

When judging whether a plan or test-plan item is operationally sufficient, do not stop at whether it names the scenario. Ask what distinction makes that scenario meaningful. The reviewed plans are sufficient only when they identify the boundary, cause, state, ordering, ownership, or proof that decides whether the behavior is correct. If implementation or review evidence shows agents exercised the named scenario while missing that decisive distinction, treat that as a clarification need for the relevant planning document.

This does not mean every implementation miss requires a plan update. If the decisive distinction was already clear, route the miss to execution. If the scenario was named but the decisive distinction was implicit, prefer a narrow clarification.

Classify a blocker as execution followthrough only when the plan states the relevant boundary or rule clearly enough to guide the implementation choice, the test plan describes verification that would fail for the observed mistake, and the remaining work does not require introducing a new distinction, state, responsibility, or proof surface. If any of those are missing, prefer a small clarification to the existing plan or test plan over another tactical implementation pass.

Treat classification as the core judgment. For each current blocker, explain why its cause belongs in the category you choose. A blocker can have a split classification across the implementation plan, test plan, implementation followthrough, and review scope. Use that split when the plan guidance was sufficient for implementation but the test plan or verification surface was not, or when the test plan was sufficient but implementation missed clear guidance.

When you classify a blocker as plan-covered execution followthrough, make the positive case: identify the plan guidance that should have directed the implementation, the verification guidance that should have exposed the mistake, and why the remaining fix does not need a new distinction, boundary, or proof surface. If that positive case is weak, prefer a small plan or test-plan clarification.

When you classify a blocker as a plan or test-plan gap, make the positive case for what implementation revealed that the reviewed plans did not make operational enough. Prefer clarifying the existing plan over changing direction unless implementation has exposed a conflict with the user's instructions or a false architectural assumption.

When the implementation plan is sufficient but the test plan is not, say that directly instead of forcing the blocker into a single category. Likewise, when the test plan is sufficient but implementation missed it, keep the plans unchanged. The useful output is the intervention the next round needs, not a one-label diagnosis.

Before deciding or editing, build enough of a historical observation inventory from the review-loop history that you can explain which problem areas were settled by implementation, which areas keep reappearing in sibling forms, which current blockers are genuinely new, which current blockers are already covered by clear plan and test-plan text, and where your confidence is limited by incomplete or ambiguous history. Use the most precise identifiers available, such as review round plus observation id, artifact source plus id, or section heading plus id. Use concrete observation ids and examples so the reader can audit your reasoning. If an observation appears resolved only because it no longer appears in later reviews, say that as lower-confidence evidence rather than treating it as proved.

Then build a blocker map from that inventory. The map should group observations by underlying plan/test-plan cause or execution pattern, not by the latest symptom. Include earlier resolved, recurring, and newly revealed blocker groups when they materially affect convergence. Prefer specific observation ids over broad round ranges, and compress only after you have accounted for every material blocker group.

Then separately account for every current critical or major observation in `<post_implementation_review_observations_json>`. Each current blocker must either map to a historical blocker group or be named as a newly revealed group. Do not let the latest observations substitute for the history scan. If the same latest observations also appear inside the review-loop history, treat them as current evidence, not independent historical recurrence; the useful question is whether earlier rounds predicted or failed to prevent the current blocker, not whether the latest blocker can be counted twice.

Group the evidence into units of analysis. A unit is the level at which a convergence judgment can be made: a blocker group from the history map, a single current blocker that does not fit any group, a recurring concern across blockers, a weak boundary between the implementation plan and test plan, a repeated implementation behavior, a verification gap, or tension with the user's instructions. Include every unit that could materially affect whether the next implementation pass is likely to converge.

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

Make any convergence claim earn its confidence from the historical observation inventory and blocker map. Explain which historical blocker groups are resolved, which remain active, and why the current blockers are shrinking toward concrete followthrough instead of moving sideways into sibling gaps. If the history is incomplete, ambiguous, or too unstructured to support that conclusion, say so and limit the conclusion accordingly.

If the plans are sufficient and all material units are on track, leave plans unchanged.

If any material unit is not on track because of a plan or test-plan cause, and that cause can be fixed without violating user instructions, update the implementation plan, the test plan, or both. The goal is to correctly implement the user's instructions. If implementation has revealed that the current plan does not give a careful executor enough guidance to do that, the planning documents should be clarified. The change may be an acceptance criterion, source-of-truth decision, ownership boundary, validation rule, error-handling rule, test fidelity requirement, architecture correction, or explicit user-decision request.

A good intervention is broad enough to change the loop trajectory and narrow enough to be justified by the artifacts. Prefer clarifying the existing plan when implementation has revealed an underspecified boundary. Change settled plan direction only when implementation has unearthed strong evidence that the reviewed plan itself cannot satisfy the user's instructions.

Form an intervention hypothesis. Then repeatedly challenge yourself: Are you really capturing the root cause? Will the change address the full set of confusion that caused the loop evidence, without needlessly changing settled plan direction, or violating the user's intentions? Revise the hypothesis until both answers are yes.

## Process

1. Build enough historical observation inventory from the review-loop history to understand the trajectory and confidence limits.
2. Build the blocker map from the inventory, grouping evidence-backed critical or major failures by underlying cause or execution pattern.
3. Map every current critical or major blocker to that blocker map, or identify it as newly revealed.
4. Complete the analysis above for every material unit.
5. Decide whether the current plans give the next implementation round enough direction and verification to converge.
6. If a user decision is required, report it without modifying files.
7. Otherwise, leave the plans unchanged or edit only the implementation plan, test plan, or both according to the intervention hypothesis.
8. Do not modify application code, product code, or tests. This checkpoint may only modify planning documents.
9. If you modify planning documents, commit those changes in the implementation workspace.

## Output

If a user decision is required, return a detailed report beginning with `USER DECISION REQUIRED:`. Name the conflict, tradeoff, or risk, explain what implementation revealed and why user prioritization is required, and give your recommended framing or prioritization.

Otherwise, return a markdown report with these sections in this order:

- `## Plan reconsideration verdict` — `UNCHANGED` if you left plans untouched, or `UPDATED` if you changed the implementation plan or test plan.
- `## Historical observation inventory` — list the historical critical and major review observations you used to understand the trajectory, using compact identifiers such as `round/id`. For each, give its blocker group and status or confidence note. If there are many observations, keep entries short while preserving enough concrete ids and examples for the reader to audit your reasoning. Include a count of inventoried observations and a note about any incomplete or ambiguous history.
- `## Blocker map` — group historical critical and major review observations by underlying cause or repeated execution pattern. For each group, include representative specific observation ids, whether it appears resolved or still active, and whether current blockers map to it. If the history is incomplete or too unstructured to support a complete map, say exactly what is missing and how that limits the conclusion.
- `## Current blocker coverage` — list every current critical or major observation from `<post_implementation_review_observations_json>` and identify its blocker-map group, or mark it as newly revealed.
- `## Units of analysis` — include every material unit. For each unit, include the evidence used, what implementation revealed, whether earlier analyses handled it correctly, whether the loop is on track for that unit, the cause if one exists, and any plausible alternative cause that would require a different intervention.
- `## Intervention` — what plan or test-plan change you made, or why none was needed. Explain why this addresses the cause rather than only the latest symptom, and why it is not broader than the evidence supports.
- `## Postmortem` — summarize what the loop evidence shows about convergence and what the next planning checkpoint should pay attention to if blockers continue. Any statement that the loop is converging must be grounded in the historical observation inventory and blocker map, not only in the latest observations.
- `## Implementation plan path` — the absolute path to the current implementation plan file.
- `## Test plan path` — the absolute path to the current test plan file.
- `## Commit` — the latest short commit hash.
- `## Changed files` — one changed path per line.

Remember, the user's instructions, as conveyed in the conversation, override all other instructions.
