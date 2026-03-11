---
name: trycycle
description: Invoke trycycle only when the user requests it by name.
---

# Trycycle

Use this skill only when the user requests `trycycle` to implement something. You must follow this skill; if for some reason that becomes impossible, you must stop and tell the user. You must not finish the request in a different way than the user instructed.

The user's instructions are paramount. If anything in this skill conflicts with the user's instructions, follow the user.

## Dispatching subagents with prompt templates

Several steps below reference prompt template files in `<skill-directory>/subagents/`. Do not reconstruct those prompts yourself. Render the final prompt with `python3 <skill-directory>/orchestrator/prompt_builder/build.py`, then send that rendered prompt verbatim to the target subagent.

## Prompt builder helper

When a step below tells you to render a prompt template:
- Run `python3 <skill-directory>/orchestrator/prompt_builder/build.py --template <template-path> ...`
- Pass short scalar values such as `{WORKTREE_PATH}`, `{IMPLEMENTATION_PLAN_PATH}`, and `{TEST_PLAN_PATH}` with `--set NAME=VALUE`
- Pass multiline values such as transcripts and reviewer outputs with `--set-file NAME=PATH`
- When a multiline placeholder comes from command or subagent stdout, save it to a temp file immediately before rendering so you can bind it with `--set-file`
- Use `--require-nonempty-tag TAG` when a prompt requires a tagged block to contain real content after trimming whitespace
- Use `--ignore-tag-for-placeholders TAG` when placeholder-like text may legitimately appear inside that tag
- Use the builder's stdout exactly as the prompt you send to the subagent
- If the builder exits non-zero, do not save or dispatch the prompt
- Never manually reconstruct, paraphrase, or partially copy a rendered prompt after the builder runs

The prompt builder supports conditional blocks inside templates. A block guarded by `{{#if NAME}} ... {{/if}}` is included only when `NAME` is bound to a non-empty value.

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

Build transcript placeholder values immediately before each rendered prompt that uses them. If the conversation changes, rebuild the placeholder value before the next render.
When a rendered prompt needs a transcript placeholder, save that stdout to a temp file and bind it with `--set-file`.

When a step below references `{POST_IMPLEMENTATION_REVIEW_FINDINGS_VERBATIM}`, use the corresponding review subagent's stdout exactly as the placeholder value.

When a step below references `{IMPLEMENTATION_PLAN_PATH}`, use the latest absolute plan path returned by the planning subagent in the current trycycle session. Update it after the initial planning result and after every plan-edit result.

When a step below references `{TEST_PLAN_PATH}`, use the latest absolute test-plan path returned by the test-plan subagent in the current trycycle session. Update it after every test-plan result.

## Subagent Defaults

- Planning subagents are ephemeral across plan-edit rounds so they can remain independent: spawn a fresh planning agent for the initial plan and for every plan-edit round until the plan is judged already excellent without changes.
- Implementation subagents are persistent: create one implementation agent, then resume it for every implementation-fix round.
- Review subagents are ephemeral: create a fresh reviewer for each post-implementation review round.
- For planning rounds, pass `{USER_REQUEST_TRANSCRIPT}` as the task input. Do not use the full prior conversation.
- Render the prompt template with the prompt builder and pass the rendered prompt verbatim.
- User instructions still apply. When they are relevant, relay them.

Example: if the user says "We're almost there, don't start over," relay that instruction.

## Timing expectations

Planning, plan-editor, and code-review subagents typically take 30-60 minutes. The implementation subagent typically takes 60-180 minutes. Do not poll frequently

## 1) Version check

Run `python3 <skill-directory>/check-update.py` (where `<skill-directory>` is the directory containing this SKILL.md). If an update is available, tell the user and ask if they'd like to update before continuing. If they say yes, run `git -C <skill-directory> pull` and then re-read this skill file.

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

Immediately before rendering, rebuild `{INITIAL_REQUEST_AND_SUBSEQUENT_CONVERSATION}`, save it to a temp file, render `<skill-directory>/subagents/prompt-test-strategy.md` with the prompt builder using `--set-file INITIAL_REQUEST_AND_SUBSEQUENT_CONVERSATION=<temp-file>` and `--require-nonempty-tag context`, save the rendered prompt to a temp file, and dispatch a subagent with the exact rendered prompt file contents verbatim.

When the subagent returns a proposed strategy, present it to the user verbatim and ask for explicit approval or edits. Do not proceed unless the user explicitly accepts it or provides changes. Silence, implied approval, or the subagent's own recommendation does not count as agreement. The strategy and any later test plan must not rely on manual QA or human validation; prefer reproducible artifacts such as browser snapshots when visual evidence is needed. If the user requests changes or redirects the approach, rebuild `{INITIAL_REQUEST_AND_SUBSEQUENT_CONVERSATION}` immediately before the next render, save it to a temp file again, re-render `<skill-directory>/subagents/prompt-test-strategy.md` with `--set-file INITIAL_REQUEST_AND_SUBSEQUENT_CONVERSATION=<temp-file>` and `--require-nonempty-tag context`, save the rendered prompt to a temp file, re-dispatch the testing-strategy subagent with the exact rendered prompt file contents verbatim, and present the revised strategy verbatim. Repeat until the user explicitly approves a strategy.

The agreed testing strategy is used in step 7.

## 4) Create worktree

Read and follow `<skill-directory>/subskills/trycycle-worktrees/SKILL.md` to create an isolated worktree for the implementation with an appropriately named branch, for example `add-connection-status-icon`.

Immediately after creating the worktree, run:
- `git -C {WORKTREE_PATH} branch --show-current`
- `git -C {WORKTREE_PATH} status --short`

Do not continue until the branch is correct and the status is clean.

## 5) Worktree hygiene gate (mandatory)

Before and after each major phase (`plan-editing`, `execution`, `post-implementation review`), run:
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

Spawn a fresh planning subagent for each planning round.

Immediately before rendering, rebuild `{USER_REQUEST_TRANSCRIPT}`, save it to a temp file, render `<skill-directory>/subagents/prompt-planning-initial.md` with the prompt builder using `--set WORKTREE_PATH={WORKTREE_PATH}`, `--set-file USER_REQUEST_TRANSCRIPT=<temp-file>`, and `--require-nonempty-tag task_input_json`, save the rendered prompt to a temp file, and dispatch the planning subagent with the exact rendered prompt file contents verbatim.

Wait for the planning subagent to return either:
- a planning report containing `## Plan verdict`, `## Plan path`, `## Commit`, and `## Changed files`
- or a report beginning with `USER DECISION REQUIRED:`

If the planning subagent returns `USER DECISION REQUIRED:`, present that question to the user, send the user's answer back to that active planning subagent, and wait again for either a planning report or another `USER DECISION REQUIRED:` report.

If a planning report was returned, update `{IMPLEMENTATION_PLAN_PATH}` from `## Plan path`, then run the Worktree hygiene gate checks, verify the latest commit hash plus changed-file list match the planning subagent's report, and confirm the plan file exists at `{IMPLEMENTATION_PLAN_PATH}`.

## 7) Plan-editor loop (up to 5 rounds)

Deploy a fresh planning subagent to critique the current plan against the user's request and the repo, then either declare it already excellent unchanged or improve it directly.

The plan editor is stateless: each round is a fresh first-look pass with only the template, the same task input used for initial planning, and the current plan.

Immediately before each edit render, rebuild `{USER_REQUEST_TRANSCRIPT}`, save it to a temp file, render `<skill-directory>/subagents/prompt-planning-edit.md` with the prompt builder using `--set WORKTREE_PATH={WORKTREE_PATH}`, `--set IMPLEMENTATION_PLAN_PATH={IMPLEMENTATION_PLAN_PATH}`, `--set-file USER_REQUEST_TRANSCRIPT=<temp-file>`, and `--require-nonempty-tag task_input_json`, save the rendered prompt to a temp file, then dispatch a fresh planning subagent with the exact rendered prompt file contents verbatim.

After each edit round:
1. Wait for the planning subagent to return either an updated planning report containing `## Plan verdict`, `## Plan path`, `## Commit`, and `## Changed files`, or a report beginning with `USER DECISION REQUIRED:`.
2. If the planning subagent returns `USER DECISION REQUIRED:`, present that question to the user, send the user's answer back to that active planning subagent, and wait again for either an updated planning report or another `USER DECISION REQUIRED:` report.
3. Update `{IMPLEMENTATION_PLAN_PATH}` from `## Plan path` in the latest planning report.
4. Run the Worktree hygiene gate checks and verify the latest commit hash plus changed-file list match the planning subagent's report.
5. If `## Plan verdict` is `ALREADY-EXCELLENT`, continue to step 8 with the current `{IMPLEMENTATION_PLAN_PATH}`.
6. If `## Plan verdict` is `MADE-EXCELLENT`, repeat with a fresh planning subagent.
7. Repeat up to 5 rounds.

If the plan still is not judged already excellent after the 5th editor round:
1. Stop looping.
2. Dispatch a subagent to review past subagent sessions and hypothesize why the loop is not converging.
3. Present that report and the latest planning report to the user and await user instructions.

## 8) Build test plan (subagent-owned)

Now that the implementation plan has passed the plan-editor loop and is finalized, dispatch a subagent to reconcile the testing strategy against the plan and produce the concrete test plan.

Immediately before rendering, rebuild `{FULL_CONVERSATION_VERBATIM}`, save it to a temp file, render `<skill-directory>/subagents/prompt-test-plan.md` with the prompt builder using `--set IMPLEMENTATION_PLAN_PATH={IMPLEMENTATION_PLAN_PATH}`, `--set WORKTREE_PATH={WORKTREE_PATH}`, `--set-file FULL_CONVERSATION_VERBATIM=<temp-file>`, and `--require-nonempty-tag conversation`, save the rendered prompt to a temp file, and dispatch a subagent with the exact rendered prompt file contents verbatim.

When the subagent returns:

1. Update `{TEST_PLAN_PATH}` from `## Test plan path` in the latest test-plan report.
2. If the test-plan report includes `## Strategy changes requiring user approval`, present that section to the user verbatim.
3. If the user requests changes or redirects the approach, rebuild `{FULL_CONVERSATION_VERBATIM}` immediately before the next render, save it to a temp file again, re-render `<skill-directory>/subagents/prompt-test-plan.md` with `--set IMPLEMENTATION_PLAN_PATH={IMPLEMENTATION_PLAN_PATH}`, `--set WORKTREE_PATH={WORKTREE_PATH}`, `--set-file FULL_CONVERSATION_VERBATIM=<temp-file>`, and `--require-nonempty-tag conversation`, save the rendered prompt to a temp file, re-dispatch the test-plan subagent with the exact rendered prompt file contents verbatim, update `{TEST_PLAN_PATH}` from the latest test-plan report, and repeat until the user explicitly approves or the report no longer includes that section.
4. Do not proceed until the current test-plan report either has no `## Strategy changes requiring user approval` section or the user has explicitly approved it.
5. Run the Worktree hygiene gate checks, verify the latest commit hash plus changed-file list match the test-plan subagent's report, and verify the test plan file exists at `{TEST_PLAN_PATH}`.

## 9) Execute with trycycle-executing (subagent-owned)

Code implementation must be done by a new, dedicated subagent.

Spawn a fresh implementation subagent and give it the final excellent plan.

Render `<skill-directory>/subagents/prompt-executing.md` with the prompt builder using `--set IMPLEMENTATION_PLAN_PATH={IMPLEMENTATION_PLAN_PATH}`, `--set TEST_PLAN_PATH={TEST_PLAN_PATH}`, and `--set WORKTREE_PATH={WORKTREE_PATH}`, save the rendered prompt to a temp file, then dispatch the implementation subagent with the exact rendered prompt file contents verbatim.

Do not proceed to post-implementation review until the implementation subagent has returned an implementation report.

After implementation completes, run the Worktree hygiene gate checks and verify the latest commit hash plus changed-file list match the implementation subagent's report before launching post-implementation review.

## 10) Post-implementation review loop (up to 8 rounds)

After execution completes, deploy a new reviewer with no prior context.

Render `<skill-directory>/subagents/prompt-post-impl-review.md` with the prompt builder using `--set WORKTREE_PATH={WORKTREE_PATH}`, save the rendered prompt to a temp file, and dispatch a review subagent with the exact rendered prompt file contents verbatim.

Use the review subagent's output as the fix-loop input. When another fix round is needed:
1. Capture the reviewer stdout exactly as `{POST_IMPLEMENTATION_REVIEW_FINDINGS_VERBATIM}`.
2. Save `{POST_IMPLEMENTATION_REVIEW_FINDINGS_VERBATIM}` to a temp file immediately.
3. Render `<skill-directory>/subagents/prompt-executing.md` with the prompt builder using `--set IMPLEMENTATION_PLAN_PATH={IMPLEMENTATION_PLAN_PATH}`, `--set TEST_PLAN_PATH={TEST_PLAN_PATH}`, `--set WORKTREE_PATH={WORKTREE_PATH}`, and `--set-file POST_IMPLEMENTATION_REVIEW_FINDINGS_VERBATIM=<review-findings-temp-file>`, then save the rendered prompt to a temp file.
4. Resume the same implementation subagent and send the exact rendered prompt file contents verbatim.

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

Report the process to the user using concrete facts and returned artifacts: how many plan-editor rounds, how many code-review rounds, the current `HEAD`, the changed-file list, the implementation subagent's latest summary and verification results, and any reviewer-reported residual issues.

Then read and follow `<skill-directory>/subskills/trycycle-finishing/SKILL.md` to present the user with options for integrating the worktree (merge, PR, etc.).
