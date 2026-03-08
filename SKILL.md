---
name: trycycle
description: Invoke trycycle only when the user requests it by name.
---

# Trycycle

Use this skill only when the user requests `trycycle` to implement something. You must follow this skill; if for some reason that becomes impossible, you must stop and tell the user. You must not finish the request in a different way than the user instructed.

The user's instructions are paramount. If anything in this skill conflicts with the user's instructions, follow the user.

## Dispatching subagents with prompt templates

Several steps below reference prompt template files in `<skill-directory>/subagents/`. Treat them as subagent inputs: dispatch the subagent with a short prompt that points it to the template file and supplies the substitution values it needs, labeled with the placeholder names such as `{WORKTREE_PATH}`. Do not read them yourself; you're the orchestrator, not the overseer.

## Transcript placeholder helper

When a step below references `{USER_REQUEST_TRANSCRIPT}`, `{INITIAL_REQUEST_AND_SUBSEQUENT_CONVERSATION}`, or `{FULL_CONVERSATION_VERBATIM}`:
1. For Claude Code, always use the canary flow:
   - Run `python3 <skill-directory>/orchestrator/user-request-transcript/mark_with_canary.py` and capture stdout exactly as `{CANARY}`.
   - Run `python3 <skill-directory>/orchestrator/user-request-transcript/build.py --cli claude-code --canary "{CANARY}"`.
   - Use its stdout exactly as the placeholder value.
2. For Codex CLI, first try direct session lookup with `python3 <skill-directory>/orchestrator/user-request-transcript/build.py --cli codex-cli`.
3. If that succeeds, use its stdout exactly as the placeholder value.
4. Otherwise, run `python3 <skill-directory>/orchestrator/user-request-transcript/mark_with_canary.py` and capture stdout exactly as `{CANARY}`.
5. Re-run `build.py` with `--cli codex-cli --canary "{CANARY}"`.
6. Use that stdout exactly as the placeholder value.

Build transcript placeholder values immediately before each dispatch that uses them. If the conversation changes, rebuild the placeholder value before the next dispatch.

When a step below references `{PLAN_REVIEW_FINDINGS_VERBATIM}` or `{POST_IMPLEMENTATION_REVIEW_FINDINGS_VERBATIM}`, use the corresponding review subagent's stdout exactly as the placeholder value.

When a step below references `{IMPLEMENTATION_PLAN_PATH}`, use the latest absolute plan path returned by the planning subagent in the current trycycle session. Update it after the initial planning result and after every plan-revision result.

When a step below references `{TEST_PLAN_PATH}`, use the latest absolute test-plan path returned by the test-plan subagent in the current trycycle session. Update it after every test-plan result.

## Subagent Defaults

- Planning subagents are persistent: create one planning agent, then resume it for every plan-fix round.
- Implementation subagents are persistent: create one implementation agent, then resume it for every implementation-fix round.
- Review subagents are ephemeral: create a fresh reviewer for each review round.
- For planning and plan review, pass `{USER_REQUEST_TRANSCRIPT}`. Do not use the full prior conversation.
- Pass the prompt template together with the parameters it names.
- User instructions still apply. When they are relevant, relay them.

Example: if the user says "We're almost there, don't start over," relay that instruction.

## Timing expectations

Planning and review subagents typically take 10-30 minutes. The implementation subagent typically takes 30-60 minutes. Do not poll frequently

## 1) Version check

Run `bash <skill-directory>/check-update.sh` (where `<skill-directory>` is the directory containing this SKILL.md). If an update is available, tell the user and ask if they'd like to update before continuing. If they say yes, run `git -C <skill-directory> pull` and then re-read this skill file.

## 2) Ask about critical unknowns before work

If the request leaves out information that could materially change the outcome and likely upset the user if guessed wrong, ask about it.

Assume the user cares about outcomes, not technologies. Mention technology choices only when they impact user experience.

If there are no critical unknowns, reply exactly:

`Getting started.`

If there are critical unknowns, list each blocking question succinctly as:

`1. Question?`

If more than one blocking question exists, ask them together. Proceed once the blocking questions have been answered.

## 3) Testing strategy

If the task specification already includes detailed instructions for testing, you will use it and skip to step 4.

Otherwise, dispatch a subagent to analyze the task and the codebase and propose a testing strategy.

Dispatch a subagent whose prompt tells it to read and follow `<skill-directory>/subagents/prompt-test-strategy.md`, and provides `{INITIAL_REQUEST_AND_SUBSEQUENT_CONVERSATION}` with the actual value.

When the subagent returns a proposed strategy, present it to the user verbatim and ask for explicit approval or edits. Do not proceed unless the user explicitly accepts it or provides changes. Silence, implied approval, or the subagent's own recommendation does not count as agreement. If the user requests changes or redirects the approach, rebuild `{INITIAL_REQUEST_AND_SUBSEQUENT_CONVERSATION}` to include that feedback, re-dispatch the testing-strategy subagent, and present the revised strategy verbatim. Repeat until the user explicitly approves a strategy.

The agreed testing strategy is used in step 7.

## 4) Create worktree

Read and follow `<skill-directory>/subskills/trycycle-worktrees/SKILL.md` to create an isolated worktree for the implementation with an appropriately named branch, for example `add-connection-status-icon`.

Immediately after creating the worktree, run:
- `git -C {WORKTREE_PATH} branch --show-current`
- `git -C {WORKTREE_PATH} status --short`

Do not continue until the branch is correct and the status is clean.

## 5) Worktree hygiene gate (mandatory)

Before and after each major phase (`plan-review`, `execution`, `post-implementation review`), run:
- `git -C {WORKTREE_PATH} branch --show-current`
- `git -C {WORKTREE_PATH} status --short`

After every subagent completion, also run:
- `git -C {WORKTREE_PATH} rev-parse --short HEAD`
- `git -C {WORKTREE_PATH} diff --name-only main...HEAD`

**GATE — Do not advance phases** until all of the following are true:
- branch matches expected branch for `{WORKTREE_PATH}`
- changed-file list matches what the subagent reported
- any dirty status is understood and intentional

## 6) Plan with trycycle-planning (subagent-owned)

Spec writing must be done by a dedicated subagent.
Only subagents read or write plan files.

Create the planning subagent once, then resume that same subagent for every plan-fix round. 

Dispatch a subagent whose prompt tells it to read and follow `<skill-directory>/subagents/prompt-planning.md`, and provides `{USER_REQUEST_TRANSCRIPT}` and `{WORKTREE_PATH}` with actual values.

Wait for the planning subagent to return either:
- a planning report containing `## Plan path`, `## Commit`, and `## Changed files`
- or a report beginning with `USER DECISION REQUIRED:`

If the planning subagent returns `USER DECISION REQUIRED:`, present that question to the user, send the user's answer back to the same planning subagent, and wait again for either a planning report or another `USER DECISION REQUIRED:` report.

If a planning report was returned, update `{IMPLEMENTATION_PLAN_PATH}` from `## Plan path`, then run the Worktree hygiene gate checks, verify the latest commit hash plus changed-file list match the planning subagent's report, and confirm the plan file exists at `{IMPLEMENTATION_PLAN_PATH}`.

## 7) Plan-review loop (up to 5 rounds)

Deploy a fresh review subagent to review the plan.
Use the subagents' findings about plan contents as the loop inputs.

Instruct the subagent to read the plan and return a numbered list of issues. An issue must be significant enough that the user's intent might not be met due to a technical or product-direction deficiency.

The reviewer is stateless: dispatch each review as a fresh first-look review with only the template and the current plan.

Dispatch a subagent whose prompt tells it to read and follow `<skill-directory>/subagents/prompt-plan-review.md`, and provides `{USER_REQUEST_TRANSCRIPT}` and `{IMPLEMENTATION_PLAN_PATH}` with actual values.

After each review:
1. If the reviewer returns `No significant issues.`, continue to step 8 with the current `{IMPLEMENTATION_PLAN_PATH}`.
2. Capture the review subagent's stdout exactly as `{PLAN_REVIEW_FINDINGS_VERBATIM}`.
3. Resume the same planning subagent you used before and send exactly this message, substituting the placeholder value without changing it:

   ```
   Revise the current implementation plan against this review report.

   <plan_review_findings_verbatim>
   {PLAN_REVIEW_FINDINGS_VERBATIM}
   </plan_review_findings_verbatim>

   Return either a markdown report with `## Plan path`, `## Commit`, and `## Changed files`, or a detailed report beginning with `USER DECISION REQUIRED:`.
   ```

4. Wait for the planning subagent to return either an updated planning report or a report beginning with `USER DECISION REQUIRED:`.
5. If the planning subagent returns `USER DECISION REQUIRED:`, present that question to the user, send the user's answer back to the same planning subagent, and wait again for either an updated planning report or another `USER DECISION REQUIRED:` report.
6. Update `{IMPLEMENTATION_PLAN_PATH}` from `## Plan path` in the latest planning report.
7. Run the Worktree hygiene gate checks and verify the latest commit hash plus changed-file list match the planning subagent's report.
8. Re-run a fresh reviewer, with rebuilt `{USER_REQUEST_TRANSCRIPT}`, the same template, and the updated `{IMPLEMENTATION_PLAN_PATH}`.
9. Repeat up to 5 rounds.

If issues still remain after the 5th review:
1. Stop looping.
2. Dispatch a subagent to review past subagent sessions and hypothesize why the loop is not converging.
3. Present that report and the latest review output to the user and await user instructions.

## 8) Build test plan (subagent-owned)

Now that the implementation plan has been reviewed and finalized, dispatch a subagent to reconcile the testing strategy against the plan and produce the concrete test plan.

Dispatch a subagent whose prompt tells it to read and follow `<skill-directory>/subagents/prompt-test-plan.md`, and provides `{FULL_CONVERSATION_VERBATIM}`, `{IMPLEMENTATION_PLAN_PATH}` (the latest approved plan path from step 7), and `{WORKTREE_PATH}` with actual values.

When the subagent returns:

1. Update `{TEST_PLAN_PATH}` from `## Test plan path` in the latest test-plan report.
2. If the test-plan report includes `## Strategy changes requiring user approval`, present that section to the user verbatim.
3. If the user requests changes or redirects the approach, rebuild `{FULL_CONVERSATION_VERBATIM}` to include that feedback, re-dispatch the test-plan subagent with the latest `{IMPLEMENTATION_PLAN_PATH}` and `{WORKTREE_PATH}`, update `{TEST_PLAN_PATH}` from the latest test-plan report, and repeat until the user explicitly approves or the report no longer includes that section.
4. Do not proceed until the current test-plan report either has no `## Strategy changes requiring user approval` section or the user has explicitly approved it.
5. Run the Worktree hygiene gate checks, verify the latest commit hash plus changed-file list match the test-plan subagent's report, and verify the test plan file exists at `{TEST_PLAN_PATH}`.

## 9) Execute with trycycle-executing (subagent-owned)

Code implementation must be done by a new, dedicated subagent.

Spawn a fresh implementation subagent and give it the final approved plan.

Dispatch a subagent whose prompt tells it to read and follow `<skill-directory>/subagents/prompt-executing.md`, and provides `{IMPLEMENTATION_PLAN_PATH}`, `{TEST_PLAN_PATH}`, and `{WORKTREE_PATH}` with actual values.

Do not proceed to post-implementation review until the implementation subagent has returned an implementation report.

After implementation completes, run the Worktree hygiene gate checks and verify the latest commit hash plus changed-file list match the implementation subagent's report before launching post-implementation review.

## 10) Post-implementation review loop (up to 8 rounds)

After execution completes, deploy a new reviewer with no prior context.

Dispatch a subagent whose prompt tells it to read and follow `<skill-directory>/subagents/prompt-post-impl-review.md`, and provides `{WORKTREE_PATH}` with the actual value.

Use the review subagent's output as the fix-loop input. When another fix round is needed, capture the reviewer stdout exactly as `{POST_IMPLEMENTATION_REVIEW_FINDINGS_VERBATIM}` and resume the same implementation subagent with this message:

```
Fix the implementation against this review report.

<post_implementation_review_findings_verbatim>
{POST_IMPLEMENTATION_REVIEW_FINDINGS_VERBATIM}
</post_implementation_review_findings_verbatim>

Commit your changes, then return a markdown report with `## Implementation summary`, `## Verification results`, `## Commit`, and `## Changed files`.
```

After each implementation-subagent fix round, run the Worktree hygiene gate checks and verify the latest commit hash plus changed-file list match the implementation subagent's report before starting the next fresh review round.

Stop when either condition is met:
1. No **critical** or **major** issues remain.
2. 8 rounds have been completed.

If critical or major issues still remain after the 8th review:
1. Stop looping.
2. Dispatch a subagent to review past subagent sessions and hypothesize why the loop is not converging.
3. Present that report and the latest review output to the user and await user instructions.

## 11) Finish

Once the post-implementation review loop passes (no critical or major issues):

Clean up temporary artifacts created during the loop (for example plan scratch files and temp notes), then run:
- `git -C {WORKTREE_PATH} status --short`
- `git -C {WORKTREE_PATH} rev-parse --short HEAD`
- `git -C {WORKTREE_PATH} diff --name-only main...HEAD`

Report the process to the user using concrete facts and returned artifacts: how many plan-review rounds, how many code-review rounds, the current `HEAD`, the changed-file list, the implementation subagent's latest summary and verification results, and any reviewer-reported residual issues.

Then read and follow `<skill-directory>/subskills/trycycle-finishing/SKILL.md` to present the user with options for integrating the worktree (merge, PR, etc.).
