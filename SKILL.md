---
name: trycycle
description: Invoke trycycle only when the user requests it by name.
---

# Trycycle

Use this skill only when the user requests `trycycle` to implement something. You must follow this skill; if for some reason that becomes impossible, you must stop and tell the user. You must not finish the request in a different way than the user instructed.

The user's instructions are paramount. If anything in this skill conflicts with the user's instructions, follow the user.

## Dispatching subagents with prompt templates

Several steps below make reference to prompt template files in `<skill-directory>/subagents/`. Do not read those prompt template files yourself — they are for the subagent, and your job is orchestration, not supervision and not execution. Instead, dispatch the subagent with a short prompt that tells it to read the template file, and include the substitution values it will need (labeled with the placeholder names like `{WORKTREE_PATH}`).

## Transcript placeholder helper

When a step below references `{USER_REQUEST_TRANSCRIPT}`, `{INITIAL_REQUEST_AND_SUBSEQUENT_CONVERSATION}`, or `{FULL_CONVERSATION_VERBATIM}`:
1. First, try direct session lookup:
   - Claude Code: `python3 <skill-directory>/orchestrator/user-request-transcript/build.py --cli claude-code`
   - Codex CLI: `python3 <skill-directory>/orchestrator/user-request-transcript/build.py --cli codex-cli`
2. If the active transcript cannot be determined directly, run `python3 <skill-directory>/orchestrator/user-request-transcript/mark_with_canary.py` and capture stdout exactly as `{CANARY}`.
3. Re-run `build.py` with `--canary "{CANARY}"`.
4. Use that stdout exactly as the placeholder value.

## Subagent Defaults

Unless the user instructs otherwise:
- Planning subagents are persistent: create one planning agent, then resume it for every plan-fix round.
- Review subagents are ephemeral: create a fresh reviewer for each review round.
- Do not pass the full prior conversation context to planning or review subagents.
- Pass `{USER_REQUEST_TRANSCRIPT}` for planning and plan review.
- Pass only the prompt template and the parameters it names.
- Do not append extra steering, advice, guidance, or direction

Example: You should not say "Keep fixing this file." If the user says "We're almost there, don't start over", though, then that is an exception, and you should relay those instructions.

## Timing expectations

Planning and review subagents typically take 10-30 minutes. The implementation subagent typically takes 30-60 minutes.

Do not treat these durations alone as evidence that a subagent is stuck.

## 1) Version check

Run `bash <skill-directory>/check-update.sh` (where `<skill-directory>` is the directory containing this SKILL.md). If an update is available, tell the user and ask if they'd like to update before continuing. If they say yes, run `git -C <skill-directory> pull` and then re-read this skill file.

## 2) Confirm critical unknowns before work

Read the user's request and identify whether any missing information could materially change the outcome and likely upset the user if guessed wrong.

Assume the user cares about outcomes, not technologies. Mention technology choices only when they impact user experience.

If there are no critical unknowns, reply exactly:

`Getting started.`

If there are critical unknowns, list each succinctly as:

`1. Question? (recommended answer)`

Example:
`1. Webapp or local? (recommendation: webapp)`

If needed, follow up with additional questions of similar importance or discussion. Proceed either when the user indicates they are ready, or when the user has answered all critical questions.

## 3) Testing strategy

If the task specification already includes detailed instructions for testing, you will use it and skip to step 4.

Otherwise, dispatch a subagent to analyze the task and the codebase and propose a testing strategy.

Dispatch a subagent whose prompt tells it to read and follow `<skill-directory>/subagents/prompt-test-strategy.md`, and provides `{INITIAL_REQUEST_AND_SUBSEQUENT_CONVERSATION}` with the actual value.

When the subagent returns a proposed strategy, present it to the user verbatim. Wait for the user to respond — they may accept, adjust, or redirect entirely. If the user adjusts, the adjusted version becomes the agreed strategy. Do not re-dispatch the subagent for adjustments; incorporate the user's changes directly.

The agreed testing strategy is used in step 7.

## 4) Create worktree

Use the `trycycle-worktrees` skill to create an isolated worktree for the implementation with an appropriately named branch, for example `add-connection-status-icon`.

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

Do not proceed until the planning subagent has either returned a complete plan or reported `USER DECISION REQUIRED:`.

If the planning subagent says a user decision is required, stop and ask the user. This is allowed only when there is no safe path forward without a user decision because of a fundamental conflict between user requirements, a fundamental conflict between the requirements and reality, or a real risk of doing harm if the agent guesses.

If a plan was returned, before starting plan-review round 1, run the Worktree hygiene gate checks and confirm the plan file exists at the returned path.

## 7) Plan-review loop (up to 5 rounds)

Deploy a fresh review subagent to review the plan.
Defer entirely to the subagents' findings about plan contents unless the user specifically asks otherwise.

Instruct the subagent to read the plan and return a numbered list of issues. An issue must be significant enough that the user's intent might not be met due to a technical or product-direction deficiency.

The reviewer should be stateless: you should NOT tell it that it is on review X/5, that it is looking at a plan that has previously been reviewed, etc.

Dispatch a subagent whose prompt tells it to read and follow `<skill-directory>/subagents/prompt-plan-review.md`, and provides `{USER_REQUEST_TRANSCRIPT}` and `{path_to_plan}` with actual values.

After each review:
1. Send all issues to the planning subagent, maintaining context from the previous planning session, and have it first reassess whether the current plan is on the right track overall.
2. If the planning subagent says a user decision is required, stop and ask the user.
3. Run the Worktree hygiene gate checks and verify the latest commit hash plus changed-file list match the planning subagent's report.
4. Re-run a fresh reviewer, with no context history, with the same template and updated plan.
5. Repeat up to 5 rounds.

If issues still remain after the 5th review:
1. Stop looping.
2. Summarize the remaining issues.
3. Speculate briefly why the loop is not converging.
4. Await user instructions.

## 8) Build test plan (subagent-owned)

Now that the implementation plan has been reviewed and finalized, dispatch a subagent to reconcile the testing strategy against the plan and produce the concrete test plan.

Dispatch a subagent whose prompt tells it to read and follow `<skill-directory>/subagents/prompt-test-plan.md`, and provides `{FULL_CONVERSATION_VERBATIM}`, `{IMPLEMENTATION_PLAN_PATH}` (the reviewed plan from step 6), and `{WORKTREE_PATH}` with actual values.

The subagent will check whether the implementation plan invalidates any assumptions in the agreed testing strategy (e.g. harness assumptions were wrong, interaction surface is larger than expected, an expensive external dependency is needed). If the strategy still holds, it proceeds directly to writing the test plan. If adjustments are needed, it includes them in its output.

When the subagent returns:

1. Check whether it flagged any strategy changes that require user approval — specifically changes that increase cost, scope, or require access to paid/external resources that weren't part of the original agreement. If so, present these to the user and wait for approval before proceeding.
2. Run the Worktree hygiene gate checks and verify the test plan file exists at the returned path.

## 9) Execute with trycycle-executing (subagent-owned)

Code implementation must be done by a new, dedicated subagent.

Spawn a fresh implementation subagent and give it the final approved plan.

Dispatch a subagent whose prompt tells it to read and follow `<skill-directory>/subagents/prompt-executing.md`, and provides `{path_to_plan}` and `{WORKTREE_PATH}` with actual values. Additionally, append this to the prompt:

```
A test plan exists at `{TEST_PLAN_PATH}`. Your implementation MUST be TDD: for each feature or component, write the relevant failing test(s) from the test plan first, then implement the minimal code to make them pass. If the test plan specifies harnesses to build, those come first.
```

Do not proceed to post-implementation review until the implementation subagent has completed execution.

After implementation completes, run the Worktree hygiene gate checks and verify commit hash plus changed-file list before launching post-implementation review.

## 10) Post-implementation review loop (up to 8 rounds)

After execution completes, deploy a new reviewer with no prior context.

Dispatch a subagent whose prompt tells it to read and follow `<skill-directory>/subagents/prompt-post-impl-review.md`, and provides `{WORKTREE_PATH}` with the actual value.

Address all issues each round regardless of severity. Route issues back to the implementation subagent for fixes, then re-run with a fresh stateless reviewer each time.

After each implementation-subagent fix round, run the Worktree hygiene gate checks and verify commit hash plus changed-file list before starting the next fresh review round.

Stop when either condition is met:
1. No **critical** or **major** issues remain.
2. 8 rounds have been completed.

If critical or major issues still remain after the 8th review:
1. Stop looping.
2. Summarize the remaining issues.
3. Speculate briefly why the loop is not converging.
4. Await user instructions.

## 11) Finish

Once the post-implementation review loop passes (no critical or major issues):

Clean up temporary artifacts created during the loop (for example plan scratch files and temp notes), then run:
- `git -C {WORKTREE_PATH} status --short`
- `git -C {WORKTREE_PATH} rev-parse --short HEAD`
- `git -C {WORKTREE_PATH} diff --name-only main...HEAD`

Summarize the ENTIRE process to the user: how many plan-review rounds, how many code-review rounds, what was changed in the codebase, any notes about unresolved minor issues or concerns, and where things stand.

Then use the `trycycle-finishing` skill to present the user with options for integrating the worktree (merge, PR, etc.).
