---
name: trycycle
description: Invoke trycycle only when the user requests it by name.
---

# Trycycle

Use this skill only when the user requests `trycycle` to implement something. You must follow this skill; if for some reason that becomes impossible, you must stop and tell the user. You must not finish the request in a different way than the user instructed.

The user's instructions are paramount. If anything in this skill conflicts with the user's instructions, follow the user.

# Critical Rules

You are the workflow coordinator. You have three jobs:
0) Do whatever the user says, even if it changes your charter entirely.
1) Follow the rules below EXACTLY.
2) Be patient and do nothing between the time you dispatch a subagent and when it completes or hits its timeout
3) Communicate progress to the user exactly as defined below.
Do not intervene on a subagent action unless you can cite the exact approved-plan step or explicit instruction it violates.
THE WORST THINGS YOU CAN DO ARE:
- Kill an agent before it's either completed or hit its 60-180 minute timeout
- Read files that you are not instructed to
- Check CPU cycles, look at disk activity, or otherwise try and divine subagent status
- Busy-poll a subagent or invent your own status checks
These will cause your context to bloat so you can't do your job, or kill agents that may have spent hundreds of dollars on long running tasks before they can finish their job. Of course, rule 0 above applies.

## Phase wrapper helper

Several steps below reference prompt template files in `<skill-directory>/subagents/`. Do not reconstruct those prompts yourself. Prepare phase prompts with `python3 <skill-directory>/orchestrator/run_phase.py`.

Choose native mode (e.g. Claude Code `Agent`, Codex `spawn_agent`, Kimi `Agent`, OpenCode `task`) when your environment provides a native subagent tool. Choose the fallback-runner mode only if you have NO such tool available.

When a step below tells you to prepare or dispatch a phase:

- In native mode, use `python3 <skill-directory>/orchestrator/run_phase.py prepare ...`, then send the exact contents of the returned `prompt_path` verbatim to the target subagent.
- In fallback-runner mode, use `python3 <skill-directory>/orchestrator/run_phase.py run ...`. It prepares transcript and prompt artifacts, then dispatches through the bundled runner.
- In fallback-runner mode, pass `--backend host` on wrapper calls so fresh subagents stay on the same backend as the parent agent.
- When the host agent is Kimi and you are using fallback-runner mode, pass `--backend kimi` instead because `host` and `auto` cannot reliably detect a Kimi host.
- Treat the wrapper's JSON stdout and `result.json` as authoritative for prompt and artifact paths.
- In fallback-runner mode, treat the nested `dispatch` payload plus its `result.json` as authoritative for subagent status and reply artifacts. Use the text at `dispatch.reply_path` as the exact subagent reply.
- If fallback dispatch returns `dispatch.status: "user_decision_required"`, present `dispatch.reply_path` verbatim to the user.
- If fallback dispatch returns `dispatch.status: "escalate_to_user"`, stop and surface the nested `dispatch.message` plus artifact paths.
- Pass short scalar placeholder values such as `{WORKTREE_PATH}`, `{IMPLEMENTATION_PLAN_PATH}`, and `{TEST_PLAN_PATH}` with `--set NAME=VALUE`.
- Pass multiline values such as reviewer outputs with `--set-file NAME=PATH`.
- When a multiline placeholder comes from command or subagent stdout, save it to a temp file immediately before wrapper invocation so you can bind it with `--set-file`.
- Bind transcript placeholders such as `{USER_REQUEST_TRANSCRIPT}`, `{INITIAL_REQUEST_AND_SUBSEQUENT_CONVERSATION}`, and `{FULL_CONVERSATION_VERBATIM}` with `--transcript-placeholder NAME`.
- Use `--require-nonempty-tag TAG` when a prompt requires a tagged block to contain real content after trimming whitespace.
- Use `--ignore-tag-for-placeholders TAG` when placeholder-like text may legitimately appear inside that tag.
- If your environment has no native subagent support and the wrapper's fallback run does not function, escalate to the user.

The prompt builder still supports conditional blocks inside templates. A block guarded by `{{#if NAME}} ... {{/if}}` is included only when `NAME` is bound to a non-empty value.

## Workspace path convention

Throughout this skill, `{WORKTREE_PATH}` means the directory where implementation happens:
- In the default mode, it is the path to the dedicated git worktree created in Step 5.
- If the user's request includes the literal flag `--no-worktree`, it is the path to the current already-isolated workspace instead.

In `--no-worktree` mode, do not create a nested git worktree and do not create or switch branches in place. Reuse the current workspace only when the environment already proves it is isolated, such as a Conductor workspace.

## Transcript placeholder helper

When a phase wrapper call needs `{USER_REQUEST_TRANSCRIPT}`, `{INITIAL_REQUEST_AND_SUBSEQUENT_CONVERSATION}`, or `{FULL_CONVERSATION_VERBATIM}`:
1. For Codex CLI, let the wrapper use direct session lookup by default.
2. For Kimi CLI, always pass `--transcript-cli kimi-cli` on transcript-bearing wrapper calls and let direct session lookup run first.
3. If the wrapper reports that a canary is required, run `python3 <skill-directory>/orchestrator/user-request-transcript/mark_with_canary.py` as a separate top-level command, capture stdout exactly as `{CANARY}`, then rerun the wrapper with `--canary "{CANARY}"`. For Kimi-hosted runs, keep `--transcript-cli kimi-cli` on the rerun as well.
4. For Claude Code, always run `python3 <skill-directory>/orchestrator/user-request-transcript/mark_with_canary.py` as a separate top-level command first, capture stdout exactly as `{CANARY}`, then invoke the wrapper with `--transcript-cli claude-code --canary "{CANARY}"`.
5. For OpenCode, always run `python3 <skill-directory>/orchestrator/user-request-transcript/mark_with_canary.py` as a separate top-level command first, capture stdout exactly as `{CANARY}`, then invoke the wrapper with `--transcript-cli opencode --canary "{CANARY}"`.

The canary must be emitted by a separate top-level command so it reaches the live session transcript before lookup. Do not rely on shell-specific capture or assignment forms that may keep the canary out of visible command output; shells and host wrappers vary, and if the canary is not visibly emitted into the session transcript, lookup will fail. Build transcript placeholder values immediately before each phase wrapper call that uses them.
Kimi and OpenCode support is explicit here because `host` and `auto` cannot reliably detect a Kimi host, and OpenCode requires canary-based lookup.

When a step below references `{POST_IMPLEMENTATION_REVIEW_OBSERVATIONS_JSON}`, use the extracted review observations JSON exactly as the placeholder value.

When a step below references `{LATEST_IMPLEMENTATION_REPORT}`, use the most recent implementation report returned by the implementation subagent. Bind it with `--set-file` from the temp-file path where you saved that report.

When a step below references `{REVIEW_LOOP_HISTORY}`, use the accumulated post-implementation review-loop history artifact from the current trycycle session.

When a step below references `{IMPLEMENTATION_PLAN_PATH}`, use the latest absolute plan path returned by the planning subagent in the current trycycle session. Update it after the initial planning result, after every planning synthesis result, and after every post-review plan-reconsideration result.

When a step below references `{TEST_PLAN_PATH}`, use the latest absolute test-plan path returned by the test-plan subagent or post-review plan-reconsideration subagent in the current trycycle session. Update it after every test-plan result and every post-review plan-reconsideration result.

When a step below references `{USER_INTENT_PATH}`, use the absolute path to the append-only user-intent artifact for the current Trycycle run.

When a step below references `{USER_INTENT}`, bind the current contents of `{USER_INTENT_PATH}` with `--set-file USER_INTENT={USER_INTENT_PATH}`. Do not manually inline it.

When a step below references `{LATER_WORK_PATH}`, use the absolute path to the append-only later-work store for the current Trycycle run. The conductor must not read this file until a user-facing handoff point: `## 12) Finish`, planning nonconvergence, or post-review nonconvergence.

When a step below references `{FILE_LATER_WORK_COMMAND}`, use the exact per-run command string created by `orchestrator/later_work.py init` for the active shell. Pass it with `--set FILE_LATER_WORK_COMMAND={FILE_LATER_WORK_COMMAND}`. Do not bind `{LATER_WORK_PATH}` into subagent prompts.

When a step below references `{IMPLEMENTATION_BACKEND}`, use the resolved `dispatch.backend` returned by the initial implementation dispatch in the current trycycle session. Update it if you ever recreate the implementation session.

## Subagent Defaults

- **Use the same backend/model unless local configuration says otherwise, and do not switch subagents to a different "best" model on your own.**
  - In native mode, keep subagents on the same model you are currently using unless the user or local configuration overrides that.
  - In fallback-runner mode, use `--backend host` by default so fresh subagents stay on the parent backend. When the host agent is Kimi, use `--backend kimi` explicitly. When the host agent is OpenCode, `--backend host` works correctly because `OPENCODE=1` is detectable.
  - Prefer local overrides when present: `TRYCYCLE_CODEX_PROFILE`, `TRYCYCLE_CODEX_MODEL`, `TRYCYCLE_CLAUDE_MODEL`, `TRYCYCLE_KIMI_MODEL`, and `TRYCYCLE_OPENCODE_MODEL`.
  - `--profile` is a Codex-only exact override for a local Codex profile name.
  - `--model` is an exact backend-specific override, not a discovery mechanism. Only pass it when you have identified a valid backend model name and can spell it exactly. Never guess or invent model names.
  - If no local override is configured and you can reliably identify your current model's exact backend name, pass that same model with `--model`. Otherwise omit `--model` and let the backend's local default apply.
  - Do not pass `--effort` unless the user explicitly asked for it or you are preserving a known parent setting. If the current effort is not safely knowable, omit it rather than guessing.
- Same-agent deepening preserves an active subagent's state inside the current fresh round after that subagent has already found issues that block progress, encouraging it to keep searching for more issues. Send the deepening prompt to the same active subagent before closing it. Do not run deepening after a normal `READY` or no-blocker response.
- Planning subagent state resets at the start of each fresh planning pass: create a fresh planning subagent for the initial plan, for every fresh planning issue-review round, and for every planning synthesis round. Use same-agent deepening only after an active planning issue finder returns `ISSUES`.
- Post-review plan-reconsideration checkpoints also use fresh planning subagents. They may update the implementation plan or test plan when implementation has exposed a real plan gap.
- In native mode, implementation subagents are persistent: create one implementation agent, then resume it for every implementation-fix round.
- In fallback-runner mode, implementation subagents are persistent through the runner: create one implementation session, record its `session_id`, then resume it through the runner for every implementation-fix round.
- In fallback-runner mode, record the resolved `dispatch.backend` for persistent sessions and reuse that same backend on every `resume`.
- Review subagent state resets at the start of each fresh post-implementation review round: create a fresh review subagent for each round, and use same-agent deepening only after an active review subagent reports blocking issues.
- For initial planning, planning issue-review rounds, and planning synthesis rounds, pass `{USER_REQUEST_TRANSCRIPT}` as the task input. Do not use the full prior conversation there. User-intent preparation and post-review plan-reconsideration checkpoints use `{FULL_CONVERSATION_VERBATIM}` because they need the full current conversation.
- Render the prompt template with the prompt builder and pass the rendered prompt verbatim.
- User instructions still apply. When they are relevant, relay them.
- If a subagent returns `USER DECISION REQUIRED:`, keep that same agent or session alive until the user's reply has been forwarded and the round has resolved.
- The initial user-intent artifact is subagent-owned. Do not create it manually.
- Later-work filing is a write-only sink during the run. Subagents may use `{FILE_LATER_WORK_COMMAND}` to file valuable findings outside the user's current request, but no phase may read, summarize, or reason from `{LATER_WORK_PATH}` until a user-facing handoff point.
- User intent freshness is conductor-owned after `{USER_INTENT_PATH}` exists. After every later user message, before dispatching or resuming any subagent, decide whether the new user message adds, removes, corrects, approves, rejects, narrows, broadens, prioritizes, supports an assistant proposal, or otherwise changes the user's intent, constraints, process requirements, scope, or acceptance criteria. If it does, append the exact or minimally trimmed new intent to `{USER_INTENT_PATH}` under `## User Intent Updates, Oldest First`. This may include assistant-proposed text when the user has supported it. Preserve chronological order. Do not rewrite, reorder, summarize, or regenerate earlier content.

Example: if the user says "We're almost there, don't start over," relay that instruction.

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

Immediately before dispatch, prepare the `test-strategy` phase via the phase wrapper using template `<skill-directory>/subagents/prompt-test-strategy.md`, `--transcript-placeholder INITIAL_REQUEST_AND_SUBSEQUENT_CONVERSATION`, and `--require-nonempty-tag context`.

Monitor by checking every 5 minutes until 60 minutes have passed. Then, and only then, kill it and retry.

When the subagent returns a proposed strategy, present it to the user verbatim and ask for explicit approval or edits. Then close that completed test-strategy subagent and clear any saved handle or `session_id` for it. Do not proceed unless the user explicitly accepts it or provides changes. Silence, implied approval, or the subagent's own recommendation does not count as agreement. The strategy and any later test plan must not rely on manual QA or human validation; prefer reproducible artifacts such as browser snapshots when visual evidence is needed. Put the strongest weight on high-value automated checks that verify real user-visible behavior through the actual UI, CLI, HTTP surface, or other outputs the user consumes, rather than tests that only show the implementation is internally self-consistent. Prefer reusing or extending those checks when they already exist, and add new tests wherever the existing suite leaves meaningful gaps in coverage, fidelity, or diagnosis. If the problem statement or prior investigation already identifies automated checks that are red and must go green, the strategy and any later test plan must include them explicitly. If the user requests changes or redirects the approach, rerun the same `test-strategy` phase wrapper command immediately before redispatching. Monitor by checking every 5 minutes until 60 minutes have passed. Then, and only then, kill it and retry. Present the revised strategy verbatim. Repeat until the user explicitly approves a strategy.

The agreed testing strategy is used in step 9.

## 4) Prepare user intent (subagent-owned)

Create a temp file path for `{USER_INTENT_PATH}`. Do not write the initial artifact yourself.

Immediately before dispatch, prepare the `user-intent` phase via the phase wrapper using template `<skill-directory>/subagents/prompt-user-intent.md`, `--set USER_INTENT_PATH={USER_INTENT_PATH}`, `--transcript-placeholder FULL_CONVERSATION_VERBATIM`, `--require-nonempty-tag conversation`, and `--ignore-tag-for-placeholders conversation`, then dispatch a fresh subagent with the returned `prompt_path`.

Monitor by checking every 5 minutes until 60 minutes have passed. Then, and only then, kill it and retry.

When the subagent returns, verify the report contains `## User intent path`, confirm it matches `{USER_INTENT_PATH}`, and confirm the file exists and is non-empty. Do not read or summarize the file contents. Close the completed user-intent subagent and clear any saved handle or `session_id`.

Then initialize the later-work filing sink:

```bash
python3 <skill-directory>/orchestrator/later_work.py init --artifacts-dir <trycycle-run-temp-dir>
```

Use the run's existing temp/artifacts directory if one already exists; otherwise create a temp directory specifically for this run's sidecar artifacts. Record `later_work_path` from the JSON stdout as `{LATER_WORK_PATH}`.

Record `{FILE_LATER_WORK_COMMAND}` from the JSON stdout as the exact command string for the conductor's active shell:
- POSIX shells: `file_later_work_command_posix`
- PowerShell: `file_later_work_command_powershell`
- `cmd.exe`: `file_later_work_command_cmd`
- If the active shell is not known, use `file_later_work_command`, which is the helper's best current-host default.

The helper also emits `file_later_work_argv` and `file_later_work_wrapper_path` for tests and diagnostics, but do not bind those into prompts.

Mark `{LATER_WORK_PATH}` and the wrapper path as protected run artifacts. Do not delete them in temp cleanup until after the later-work summary has been generated. Do not read `{LATER_WORK_PATH}` again until a user-facing handoff point.

## 5) Prepare implementation workspace

Default behavior: before creating the worktree, fetch and fast-forward the base branch so the worktree starts from the latest code. Other agents may have merged changes while the user was reviewing earlier steps.

```bash
git fetch origin main && git merge --ff-only origin/main
```

Read and follow `<skill-directory>/subskills/trycycle-worktrees/SKILL.md` to create an isolated worktree for the implementation with an appropriately named branch, for example `add-connection-status-icon`.

If the user's request includes the literal flag `--no-worktree`, skip the worktree-creation subskill and prepare the current workspace instead:
- Set `{WORKTREE_PATH}` to the current repository root.
- Run `git -C {WORKTREE_PATH} status --short` and stop unless it is clean.
- Detect the default branch. Prefer `CONDUCTOR_DEFAULT_BRANCH` when it is set and non-empty. Otherwise use the repo's configured remote default branch if available; if not, fall back to `main`, then `master`.
- Run `git -C {WORKTREE_PATH} branch --show-current` and stop unless it returns a non-empty branch name that is different from the detected default branch.
- Require `CONDUCTOR_WORKSPACE_PATH` to be set and to resolve to the current workspace. If it is unset or points elsewhere, stop and tell the user that `--no-worktree` is only supported in already-isolated workspaces such as Conductor workspaces.
- Do not create a branch, switch branches, or create any nested worktree in this mode.

Immediately after preparing the implementation workspace, run:
- `git -C {WORKTREE_PATH} branch --show-current`
- `git -C {WORKTREE_PATH} status --short`

Do not continue until the branch is correct and the status is clean.

## 6) Workspace hygiene gate (mandatory)

Before and after each major phase (`plan-review/synthesis`, `execution`, `post-implementation review`), run:
- `git -C {WORKTREE_PATH} branch --show-current`
- `git -C {WORKTREE_PATH} status --short`

After every subagent completion, also run:
- `git -C {WORKTREE_PATH} rev-parse --short HEAD`
- `git -C {WORKTREE_PATH} diff --name-only main...HEAD`

**GATE — Do not advance phases** until all of the following are true:
- branch matches expected branch for `{WORKTREE_PATH}`
- changed-file list matches what the subagent reported
- any dirty status is understood and intentional

## 7) Plan with trycycle-planning (subagent-owned)

Spec writing must be done by a dedicated subagent.
Only subagents read or write plan files.

Spawn a fresh planning subagent for each planning round.

Immediately before dispatch, prepare the `planning-initial` phase via the phase wrapper using template `<skill-directory>/subagents/prompt-planning-initial.md`, `--set WORKTREE_PATH={WORKTREE_PATH}`, `--set FILE_LATER_WORK_COMMAND={FILE_LATER_WORK_COMMAND}`, `--set-file USER_INTENT={USER_INTENT_PATH}`, `--transcript-placeholder USER_REQUEST_TRANSCRIPT`, and `--require-nonempty-tag task_input_json`.

Monitor by checking every 5 minutes until 60 minutes have passed. Then, and only then, kill it and retry.

Wait for the planning subagent to return either:
- a planning report containing `## Plan verdict`, `## Plan path`, `## Commit`, and `## Changed files`
- or a report beginning with `USER DECISION REQUIRED:`

If the planning subagent returns `USER DECISION REQUIRED:`, present that question to the user, run the user-intent freshness check, send the user's answer back to that active planning subagent, and wait again for either a planning report or another `USER DECISION REQUIRED:` report. Monitor by checking every 5 minutes until 60 minutes have passed. Then, and only then, kill it and retry.

If a planning report was returned, update `{IMPLEMENTATION_PLAN_PATH}` from `## Plan path`, then run the workspace hygiene gate checks, verify the latest commit hash plus changed-file list match the planning subagent's report, confirm the plan file exists at `{IMPLEMENTATION_PLAN_PATH}`, then close that planning subagent and clear any saved handle or `session_id` for it.

## 8) Planning issue-review and synthesis loop (up to 5 review rounds)

Deploy a fresh planning issue finder to critique the current plan against the user's request and the repo. The issue finder only discovers and reports plan issues; it must not edit the plan. If it finds issues, deepen on the same issue finder until discovery is saturated or the planning issue-finder deepening cap is reached, then close it and dispatch a fresh planning synthesis subagent to rewrite the plan holistically from the accumulated findings.

A planning review round is one fresh issue-finder pass plus any same-agent deepening responses from that same issue finder. If that round returns `ISSUES`, one fresh synthesis pass follows and the round counts as not ready. The synthesis pass is separate from issue discovery and must not be sent to the same subagent.

Immediately before each issue-review dispatch, prepare the `planning-review` phase via the phase wrapper using template `<skill-directory>/subagents/prompt-planning-review.md`, `--set WORKTREE_PATH={WORKTREE_PATH}`, `--set IMPLEMENTATION_PLAN_PATH={IMPLEMENTATION_PLAN_PATH}`, `--set FILE_LATER_WORK_COMMAND={FILE_LATER_WORK_COMMAND}`, `--set-file USER_INTENT={USER_INTENT_PATH}`, `--transcript-placeholder USER_REQUEST_TRANSCRIPT`, and `--require-nonempty-tag task_input_json`, then dispatch a fresh planning subagent with the returned `prompt_path`. Start a phase prompt paths temp file if needed, and append the returned `prompt_path`.

Monitor by checking every 5 minutes until 180 minutes have passed. Then, and only then, kill it and retry.

After each issue-review round starts:
1. Wait for the planning issue finder to return either a report containing `## Plan verdict`, `## Findings memo`, `## Plan path`, `## Commit`, and `## Changed files`, or a report beginning with `USER DECISION REQUIRED:`.
2. If the planning issue finder returns `USER DECISION REQUIRED:`, present that question to the user, run the user-intent freshness check, send the user's answer back to that active planning subagent, and wait again for either an issue-review report or another `USER DECISION REQUIRED:` report. Monitor by checking every 5 minutes until 180 minutes have passed. Then, and only then, kill it and retry.
3. Confirm `## Plan path` matches the current `{IMPLEMENTATION_PLAN_PATH}`, then run the workspace hygiene gate checks and verify the latest commit hash plus changed-file list match the planning issue finder's report.
4. Start a loop outputs temp file if needed, save the returned issue-review report to a temp file, and append that path.
5. If `## Plan verdict` is `READY`, close that planning subagent for the completed round, clear any saved handle or `session_id`, and continue to `## 9) Build test plan` with the current `{IMPLEMENTATION_PLAN_PATH}`. Do not run deepening after a `READY` verdict.
6. If `## Plan verdict` is `ISSUES`, run the same-agent planning issue-finder deepening loop below without closing the planning subagent.
7. When the deepening loop ends normally or reaches its cap, create a planning findings memo temp file from all issue-review and deepening report paths for this round. Preserve the simple findings memo shape; do not add a taxonomy, ledger, required resolution field, or semantic deduplication. File headers that identify the source report are okay.
8. Close the completed issue-finder subagent and clear any saved handle or `session_id`.
9. Dispatch a fresh planning synthesis subagent with the findings memo as described below.
10. After synthesis completes, if fewer than 5 fresh planning review rounds have completed, repeat the issue-review dispatch and this "After each issue-review round starts" flow with a fresh issue finder. If the 5th fresh planning review round found issues and synthesis completed, stop and follow the nonconvergence-review path below.

Same-agent planning issue-finder deepening loop:

Before entering this loop, set the planning issue-finder deepening count to 0 for this planning subagent.

For each deepening pass:
1. Prepare the `planning-review-deepen` phase via the phase wrapper using template `<skill-directory>/subagents/prompt-planning-review-deepen.md`, `--set WORKTREE_PATH={WORKTREE_PATH}`, `--set IMPLEMENTATION_PLAN_PATH={IMPLEMENTATION_PLAN_PATH}`, `--set FILE_LATER_WORK_COMMAND={FILE_LATER_WORK_COMMAND}`, and `--set-file USER_INTENT={USER_INTENT_PATH}`. Append the returned `prompt_path` to the phase prompt paths temp file.
2. In native mode, send the exact returned `prompt_path` contents verbatim to the same active planning issue finder. In fallback-runner mode, resume the same planning session through `python3 <skill-directory>/orchestrator/subagent_runner.py resume` using that planning dispatch's saved `session_id`, its resolved backend, the wrapper-prepared `prompt_path`, and phase `planning-review-deepen`.
3. Monitor by checking every 5 minutes until 180 minutes have passed. Then, and only then, kill it and halt this Trycycle run as an unexpected deepening timeout. Surface all completed planning issue-review report paths, the timed-out attempt artifacts if available, and the active planning session id if available. Notify the user of what happened and tell them they can instruct you to continue; await user instructions before taking any further action.
4. Wait for either a report containing `## Plan verdict`, `## Findings memo`, `## Plan path`, `## Commit`, and `## Changed files`, or a report beginning with `USER DECISION REQUIRED:`.
5. If the planning issue finder returns `USER DECISION REQUIRED:`, present that question to the user, run the user-intent freshness check, send the user's answer back to that same active planning subagent, and wait again for either an issue-review report or another `USER DECISION REQUIRED:` report. Monitor by checking every 5 minutes until 180 minutes have passed. Then, and only then, kill it and halt with the completed planning issue-review report paths and timed-out attempt artifacts.
6. Save the completed deepening report to a temp file immediately and append that path to the loop outputs temp file before sending any further prompt.
7. Confirm `## Plan path` matches the current `{IMPLEMENTATION_PLAN_PATH}`, then run the workspace hygiene gate checks and verify the latest commit hash plus changed-file list match the planning issue finder's report.
8. If `## Plan verdict` is `READY`, the same planning issue finder has found no additional critical plan issues. End this same-agent deepening loop.
9. If `## Plan verdict` is `ISSUES`, increment the planning issue-finder deepening count.
10. If the planning issue-finder deepening count is 5, end this same-agent deepening loop and continue to synthesis with all accumulated findings. This is not a halt condition.
11. If the planning issue-finder deepening count is less than 5, repeat from the start of the deepening pass list.

The planning issue-finder counter intentionally counts completed deepening responses that contain `ISSUES`. A final `READY` response stops the loop and is not counted toward the cap.

Planning synthesis pass:
1. Immediately before each synthesis dispatch, prepare the `planning-synthesis` phase via the phase wrapper using template `<skill-directory>/subagents/prompt-planning-synthesis.md`, `--set WORKTREE_PATH={WORKTREE_PATH}`, `--set IMPLEMENTATION_PLAN_PATH={IMPLEMENTATION_PLAN_PATH}`, `--set FILE_LATER_WORK_COMMAND={FILE_LATER_WORK_COMMAND}`, `--set-file PLANNING_FINDINGS_MEMO=<planning-findings-memo-temp-file>`, `--set-file USER_INTENT={USER_INTENT_PATH}`, `--transcript-placeholder USER_REQUEST_TRANSCRIPT`, `--require-nonempty-tag task_input_json`, and `--ignore-tag-for-placeholders planning_findings_memo`, then dispatch a fresh planning subagent with the returned `prompt_path`. Append the returned `prompt_path` to the phase prompt paths temp file.
2. Monitor by checking every 5 minutes until 180 minutes have passed. Then, and only then, kill it and retry.
3. Wait for the planning synthesis subagent to return either a report containing `## Plan verdict`, `## Synthesis summary`, `## Plan path`, `## Commit`, and `## Changed files`, or a report beginning with `USER DECISION REQUIRED:`.
4. If the planning synthesis subagent returns `USER DECISION REQUIRED:`, present that question to the user, run the user-intent freshness check, send the user's answer back to that active planning subagent, and wait again for either a synthesis report or another `USER DECISION REQUIRED:` report. Monitor by checking every 5 minutes until 180 minutes have passed. Then, and only then, kill it and retry.
5. Update `{IMPLEMENTATION_PLAN_PATH}` from `## Plan path`, then run the workspace hygiene gate checks, verify the latest commit hash plus changed-file list match the planning synthesis subagent's report, and confirm the plan file exists at `{IMPLEMENTATION_PLAN_PATH}`.
6. Save the synthesis report to a temp file and append that path to the loop outputs temp file.
7. Close the completed synthesis subagent and clear any saved handle or `session_id`.

If the plan still is not judged ready after the 5th planning review round: **STOP. Do NOT proceed to step 9.**
1. Stop looping.
2. Prepare the `nonconvergence-review` phase via the phase wrapper using template `<skill-directory>/subagents/prompt-nonconvergence-review.md`, `--set TRYCYCLE_SKILL_PATH=<skill-directory>/SKILL.md`, `--set NONCONVERGENCE_CONTEXT="Planning issue-review and synthesis loop reached 5 review rounds without a READY verdict."`, `--set WORKTREE_PATH={WORKTREE_PATH}`, `--set IMPLEMENTATION_PLAN_PATH={IMPLEMENTATION_PLAN_PATH}`, `--set TEST_PLAN_PATH="Not built yet; the planning issue-review and synthesis loop did not converge before the test-plan phase."`, `--set FILE_LATER_WORK_COMMAND={FILE_LATER_WORK_COMMAND}`, `--set-file PHASE_PROMPT_PATHS=<phase-prompt-paths-temp-file>`, `--set-file LOOP_OUTPUT_PATHS=<loop-outputs-temp-file>`, `--set IMPLEMENTATION_REPORT_PATHS="Not applicable; execution did not start."`, and `--set-file USER_INTENT={USER_INTENT_PATH}`, then dispatch a subagent with the returned `prompt_path`. Monitor by checking every 5 minutes until 60 minutes have passed. Then, and only then, kill it and retry.
3. Before presenting the report, read the later-work store by running `python3 <skill-directory>/orchestrator/later_work.py summarize --path {LATER_WORK_PATH}`. Include the output under `Other important work found during this run`; if it prints `No later work was filed.`, report that briefly instead.
4. Present the nonconvergence report, the later-work summary, and the latest issue-review and synthesis reports to the user and **await user instructions before taking any further action.**

## 9) Build test plan (subagent-owned)

Now that the implementation plan has passed the planning issue-review and synthesis loop and is finalized, dispatch a subagent to reconcile the testing strategy against the plan and produce the concrete test plan, starting from high-value existing automated checks where they exist and adding new tests where coverage is missing.

Immediately before dispatch, prepare the `test-plan` phase via the phase wrapper using template `<skill-directory>/subagents/prompt-test-plan.md`, `--set IMPLEMENTATION_PLAN_PATH={IMPLEMENTATION_PLAN_PATH}`, `--set WORKTREE_PATH={WORKTREE_PATH}`, `--set FILE_LATER_WORK_COMMAND={FILE_LATER_WORK_COMMAND}`, `--set-file USER_INTENT={USER_INTENT_PATH}`, `--transcript-placeholder FULL_CONVERSATION_VERBATIM`, and `--require-nonempty-tag conversation`.

Monitor by checking every 5 minutes until 60 minutes have passed. Then, and only then, kill it and retry.

When the subagent returns:

1. Update `{TEST_PLAN_PATH}` from `## Test plan path` in the latest test-plan report.
2. If the test-plan report includes `## Strategy changes requiring user approval`, present that section to the user verbatim.
3. If the user requests changes or redirects the approach, run the user-intent freshness check, close that completed test-plan subagent and clear any saved handle or `session_id` for it, then rerun the same `test-plan` phase wrapper command immediately before redispatching. Monitor by checking every 5 minutes until 60 minutes have passed. Then, and only then, kill it and retry. Update `{TEST_PLAN_PATH}` from the latest test-plan report. Repeat until the user explicitly approves or the report no longer includes that section.
4. Do not proceed until the current test-plan report either has no `## Strategy changes requiring user approval` section or the user has explicitly approved it.
5. Run the workspace hygiene gate checks, verify the latest commit hash plus changed-file list match the test-plan subagent's report, and verify the test plan file exists at `{TEST_PLAN_PATH}`.
6. Close the completed test-plan subagent for the approved report and clear any saved handle or `session_id` for it.

## 10) Execute with trycycle-executing (subagent-owned)

Code implementation must be done by a new, dedicated subagent.

Before dispatching the implementation subagent, rebase onto the latest base branch to incorporate any changes merged by other agents during planning:

```bash
git -C {WORKTREE_PATH} fetch origin main
git -C {WORKTREE_PATH} rebase origin/main
```

If the rebase has conflicts, stop and present them to the user.

Spawn a fresh implementation subagent and give it the final excellent plan.

The implementation subagent stays in execute mode until the plan is complete, the work has gone through red/green/refactor cycles as needed, and all required automated tests are passing for legitimate reasons. Failed checks mean keep improving the code and tests unless there is a genuine blocker. Do not accept weakened or deleted valid tests as a shortcut to green.

Immediately before dispatch, prepare the `executing` phase via the phase wrapper using template `<skill-directory>/subagents/prompt-executing.md`, `--set IMPLEMENTATION_PLAN_PATH={IMPLEMENTATION_PLAN_PATH}`, `--set TEST_PLAN_PATH={TEST_PLAN_PATH}`, `--set WORKTREE_PATH={WORKTREE_PATH}`, `--set FILE_LATER_WORK_COMMAND={FILE_LATER_WORK_COMMAND}`, and `--set-file USER_INTENT={USER_INTENT_PATH}`, then dispatch the implementation subagent with the returned `prompt_path`. Start a phase prompt paths temp file if needed, and append the returned `prompt_path`.

In fallback-runner mode, record the returned `dispatch.backend` as `{IMPLEMENTATION_BACKEND}` alongside the saved `session_id`.

Monitor by checking every 5 minutes until 180 minutes have passed. Then, and only then, kill it and retry.
If you kill and retry this implementation round, create a fresh implementation subagent or runner session and replace the saved implementation handle. In fallback-runner mode, also replace the saved `session_id` and `{IMPLEMENTATION_BACKEND}` with the fresh dispatch values.

Do not proceed to post-implementation review until the implementation subagent has returned an implementation report. Start an implementation reports temp file if needed, save the report to a temp file immediately, append that path, and treat that saved file as the latest implementation report for the first review prompt.

After implementation completes, run the workspace hygiene gate checks and verify the latest commit hash plus changed-file list match the implementation subagent's report before launching post-implementation review.

## 11) Post-implementation review loop (up to 8 rounds by default)

After execution completes, deploy a new reviewer with no prior context and give it the finalized implementation plan plus the finalized test plan.

Create an empty temp file for `{REVIEW_LOOP_HISTORY}` before starting the first review round, then append the implementation subagent's initial implementation report to it.

Immediately before dispatch, prepare the `post-implementation-review` phase via the phase wrapper using template `<skill-directory>/subagents/prompt-post-impl-review.md`, `--set WORKTREE_PATH={WORKTREE_PATH}`, `--set IMPLEMENTATION_PLAN_PATH={IMPLEMENTATION_PLAN_PATH}`, `--set TEST_PLAN_PATH={TEST_PLAN_PATH}`, `--set FILE_LATER_WORK_COMMAND={FILE_LATER_WORK_COMMAND}`, `--set-file LATEST_IMPLEMENTATION_REPORT=<latest-implementation-report-temp-file>`, `--set-file USER_INTENT={USER_INTENT_PATH}`, and `--ignore-tag-for-placeholders latest_implementation_report`, then dispatch a review subagent with the returned `prompt_path`. Append the returned `prompt_path` to the phase prompt paths temp file.

Monitor by checking every 5 minutes until 180 minutes have passed. Then, and only then, kill it and retry.

Use the review subagent's completed output as the first review-pass input. Keep that same review subagent open until either:
- the normal first response has no blocking issues,
- same-agent deepening completes without additional blocking issues,
- the 5-pass deepening cap is hit,
- a timeout or extraction failure requires halting,
- or the reviewer asks for `USER DECISION REQUIRED:`.

If the reviewer returns `USER DECISION REQUIRED:`, present that question to the user, run the user-intent freshness check, send the user's answer back to that same active review subagent, and wait again for either a completed review response or another `USER DECISION REQUIRED:` report. Monitor by checking every 5 minutes until 180 minutes have passed. Then, and only then, kill it and halt with all completed review reply paths, extracted observation paths, and timed-out attempt artifacts if available.

After every completed review pass, including the normal first response and every deepening response:
1. Save the reviewer's raw stdout to a temp file immediately.
2. Extract a structured review-observations artifact from that saved reply.
3. Append the review reply path and extracted review-observations path to the loop outputs temp file.
4. Append the completed review pass number, raw stdout, and normalized review-observations JSON to `{REVIEW_LOOP_HISTORY}` under the current post-implementation review round before sending any further prompt.

Use this command for each pass extraction:

```bash
python3 <skill-directory>/orchestrator/review_observations.py extract \
  --reply <review-reply-temp-file> \
  --output <review-observations-temp-file>
```

Treat the extractor's JSON stdout as authoritative for:
- `issue_count`
- `blocking_issue_count`
- `has_blocking_issues`
- `review_status`

If extraction fails, stop and surface the review reply plus the extractor failure to the user rather than guessing.

Start a loop outputs temp file if needed before appending review artifacts.

If the normal first review response has `blocking_issue_count: 0`, do not run deepening. Close the completed review subagent and clear any saved handle or `session_id`.

If any completed review pass has `blocking_issue_count > 0`, run same-agent post-implementation review deepening before deciding the fix-loop input. Before entering this loop, set the post-implementation review deepening count to 0 for this review subagent. If this loop halts for timeout, cap, or extraction failure, preserve the active review subagent or runner session where the host supports it. For each deepening pass:
1. Prepare the `post-implementation-review-deepen` phase via the phase wrapper using template `<skill-directory>/subagents/prompt-post-impl-review-deepen.md`, `--set FILE_LATER_WORK_COMMAND={FILE_LATER_WORK_COMMAND}`, `--set-file USER_INTENT={USER_INTENT_PATH}`. Append the returned `prompt_path` to the phase prompt paths temp file.
2. In native mode, send the exact returned `prompt_path` contents verbatim to the same active review subagent. In fallback-runner mode, resume the same review session through `python3 <skill-directory>/orchestrator/subagent_runner.py resume` using that review dispatch's saved `session_id`, its resolved backend, the wrapper-prepared `prompt_path`, and phase `post-implementation-review-deepen`.
3. Monitor by checking every 5 minutes until 180 minutes have passed. Then, and only then, kill it and halt this Trycycle run as an unexpected deepening timeout. Surface all completed review reply paths, extracted observation paths, the timed-out attempt artifacts if available, and the active review session id if available. Await user instructions before taking any further action.
4. Wait for either a completed review response containing a `<review_observations_json>...</review_observations_json>` block or a report beginning with `USER DECISION REQUIRED:`.
5. If the reviewer returns `USER DECISION REQUIRED:`, present that question to the user, run the user-intent freshness check, send the user's answer back to that same active review subagent, and wait again for either a completed review response or another `USER DECISION REQUIRED:` report. Monitor by checking every 5 minutes until 180 minutes have passed. Then, and only then, kill it and halt with all completed review reply paths, extracted observation paths, and timed-out attempt artifacts if available.
6. Save and extract the completed deepening response immediately, append its reply path and observation path to the loop outputs temp file, and append the pass to `{REVIEW_LOOP_HISTORY}` before sending any further prompt.
7. If extraction fails, stop and surface the review reply plus the extractor failure to the user rather than guessing.
8. If the deepening response has `blocking_issue_count: 0`, the same reviewer has found no additional critical or major issues. End this same-agent deepening loop, then close the completed review subagent and clear any saved handle or `session_id`.
9. If the deepening response has `blocking_issue_count > 0`, increment the post-implementation review deepening count.
10. If the post-implementation review deepening count is 5, create the combined review-round observation artifact using the combine command below and all completed extracted observation paths. Append the combined path to the loop outputs temp file. If combine fails, keep the per-pass artifacts and surface the combine failure instead of guessing.
11. After the 5th blocking deepening pass has been saved, extracted, and combined if possible, halt this Trycycle run as an unexpected deepening cap. Do not dispatch an implementation fix round, do not run plan reconsideration, and do not start another fresh review round. Do not close the active review subagent or runner session unless the user instructs you to. Surface the latest review output, all completed review reply paths, all extracted observation paths, the combined observation path if created, the active review handle or session id if available, and the resolved review backend if available. Await user instructions.
12. If the post-implementation review deepening count is less than 5, repeat from the start of the deepening pass list.

The counter intentionally counts completed deepening responses that contain `critical` or `major` observations. A final `no_issues` response stops the loop and is not counted toward the cap.

After the normal review response and any completed deepening responses have been extracted, create the review-round observation artifact used by the rest of the loop:

```bash
python3 <skill-directory>/orchestrator/review_observations.py combine \
  --output <combined-review-observations-temp-file> \
  <review-observations-temp-file> [<deepening-review-observations-temp-file> ...]
```

Treat the combine command's JSON stdout as authoritative for:
- `issue_count`
- `blocking_issue_count`
- `has_blocking_issues`
- `review_status`

Append the combined review-round observation artifact path to the loop outputs temp file.

Use this combined review-round observation artifact anywhere Step 11 previously used the latest extracted review-observations artifact, including:
- stop condition checks
- plan reconsideration `{POST_IMPLEMENTATION_REVIEW_OBSERVATIONS_JSON}`
- implementation fix-round `{POST_IMPLEMENTATION_REVIEW_OBSERVATIONS_JSON}`
- nonconvergence evidence

Deepening passes do not increment the completed fresh post-implementation review round number. Plan reconsideration cadence and the default stop point use completed fresh review rounds only.

When blocking issues remain after a review round, first check whether the loop has reached its stop point. The default stop point is 8 completed fresh review rounds, but the user can override that like any other instruction.

Before either dispatching another fix round or running nonconvergence review, check whether plan reconsideration is due. Plan reconsideration is due when blocking issues remain and either:
- The completed review round is even-numbered and greater than 2: the 4th, 6th, 8th, and every 2 rounds thereafter if the user overrides the stop point.
- The loop has reached its configured stop point. This means nonconvergence review always runs after a plan-reconsideration checkpoint when the loop stops with blockers, even if the user chose a stop point that would not otherwise trigger the even-round cadence.

If plan reconsideration is due, run this checkpoint before the next action:
- Prepare the `planning-reconsider` phase via the phase wrapper using template `<skill-directory>/subagents/prompt-planning-reconsider.md`, `--set WORKTREE_PATH={WORKTREE_PATH}`, `--set IMPLEMENTATION_PLAN_PATH={IMPLEMENTATION_PLAN_PATH}`, `--set TEST_PLAN_PATH={TEST_PLAN_PATH}`, `--set REVIEW_ROUND_NUMBER=<completed-review-round-number>`, `--set FILE_LATER_WORK_COMMAND={FILE_LATER_WORK_COMMAND}`, `--set-file POST_IMPLEMENTATION_REVIEW_OBSERVATIONS_JSON=<combined-review-observations-temp-file>`, `--set-file REVIEW_LOOP_HISTORY=<review-loop-history-temp-file>`, `--set-file USER_INTENT={USER_INTENT_PATH}`, `--transcript-placeholder FULL_CONVERSATION_VERBATIM`, `--require-nonempty-tag conversation`, `--require-nonempty-tag review_loop_history`, `--ignore-tag-for-placeholders conversation`, `--ignore-tag-for-placeholders post_implementation_review_observations_json`, and `--ignore-tag-for-placeholders review_loop_history`, then dispatch a fresh planning subagent with the returned `prompt_path`. Append the returned `prompt_path` to the phase prompt paths temp file.
- Monitor by checking every 5 minutes until 60 minutes have passed. Then, and only then, kill it and retry.
- Wait for either a report containing `## Plan reconsideration verdict`, `## Implementation plan path`, `## Test plan path`, `## Commit`, and `## Changed files`, or a report beginning with `USER DECISION REQUIRED:`.
- If the planning subagent returns `USER DECISION REQUIRED:`, present that question to the user, run the user-intent freshness check, send the user's answer back to that active planning subagent, and wait again for either a plan-reconsideration report or another `USER DECISION REQUIRED:` report. Monitor by checking every 5 minutes until 60 minutes have passed. Then, and only then, kill it and retry.
- Update `{IMPLEMENTATION_PLAN_PATH}` from `## Implementation plan path` and `{TEST_PLAN_PATH}` from `## Test plan path` in the latest plan-reconsideration report.
- Run the workspace hygiene gate checks and verify the latest commit hash plus changed-file list match the planning subagent's report.
- Save the plan-reconsideration report to a temp file and append that path to the loop outputs temp file.
- Append the plan-reconsideration report itself to `{REVIEW_LOOP_HISTORY}` under a clear plan-reconsideration heading so future plan-reconsideration checkpoints receive prior analyses. This history is for planning and final nonconvergence analysis; do not add it to executor or reviewer prompts.
- Close that planning subagent and clear any saved handle or `session_id` for it.

Stop when either condition is met:
1. The combined review-round observation artifact reports `blocking_issue_count: 0`.
2. The configured stop point has been reached. By default, this is 8 completed fresh review rounds.

If the combined review-round observation artifact still reports `blocking_issue_count > 0` after the configured stop point:
1. Stop looping. Do not dispatch another implementation fix round.
2. Prepare the `nonconvergence-review` phase via the phase wrapper using template `<skill-directory>/subagents/prompt-nonconvergence-review.md`, `--set TRYCYCLE_SKILL_PATH=<skill-directory>/SKILL.md`, `--set NONCONVERGENCE_CONTEXT="Post-implementation review loop stopped after <completed-review-round-number> review rounds while blockers remained."`, `--set WORKTREE_PATH={WORKTREE_PATH}`, `--set IMPLEMENTATION_PLAN_PATH={IMPLEMENTATION_PLAN_PATH}`, `--set TEST_PLAN_PATH={TEST_PLAN_PATH}`, `--set FILE_LATER_WORK_COMMAND={FILE_LATER_WORK_COMMAND}`, `--set-file PHASE_PROMPT_PATHS=<phase-prompt-paths-temp-file>`, `--set-file LOOP_OUTPUT_PATHS=<loop-outputs-temp-file>`, `--set-file IMPLEMENTATION_REPORT_PATHS=<implementation-reports-temp-file>`, and `--set-file USER_INTENT={USER_INTENT_PATH}`, then dispatch a subagent with the returned `prompt_path`. Monitor by checking every 5 minutes until 60 minutes have passed. Then, and only then, kill it and retry.
3. Before presenting the report, read the later-work store by running `python3 <skill-directory>/orchestrator/later_work.py summarize --path {LATER_WORK_PATH}`. Include the output under `Other important work found during this run`; if it prints `No later work was filed.`, report that briefly instead.
4. Present the nonconvergence report, the later-work summary, and the latest review output to the user and await user instructions.

If blockers remain and the configured stop point has not been reached, continue with the fix round:
1. Prepare the `executing` phase again via the phase wrapper using template `<skill-directory>/subagents/prompt-executing.md`, `--set IMPLEMENTATION_PLAN_PATH={IMPLEMENTATION_PLAN_PATH}`, `--set TEST_PLAN_PATH={TEST_PLAN_PATH}`, `--set WORKTREE_PATH={WORKTREE_PATH}`, `--set FILE_LATER_WORK_COMMAND={FILE_LATER_WORK_COMMAND}`, `--set-file POST_IMPLEMENTATION_REVIEW_OBSERVATIONS_JSON=<combined-review-observations-temp-file>`, `--set-file USER_INTENT={USER_INTENT_PATH}`, and `--ignore-tag-for-placeholders post_implementation_review_observations_json`. Append the returned `prompt_path` to the phase prompt paths temp file. The executing prompt must treat only `critical` and `major` observations as critical issues and required fix targets; `minor` and `nit` observations are not required fix targets.
2. In native mode, resume the same implementation subagent and send the exact returned `prompt_path` contents verbatim. In fallback-runner mode, resume the implementation session through `python3 <skill-directory>/orchestrator/subagent_runner.py resume` using the saved `session_id`, `--backend {IMPLEMENTATION_BACKEND}`, and the wrapper-prepared `prompt_path`.
3. Monitor by checking every 5 minutes until 180 minutes have passed. Then, and only then, kill it and retry.
4. If you kill and retry this implementation round, create a fresh implementation subagent or runner session and replace the saved implementation handle. In fallback-runner mode, also replace the saved `session_id` and `{IMPLEMENTATION_BACKEND}` with the fresh dispatch values. Keep any paths already appended for the killed attempt; they are useful evidence if nonconvergence analysis is needed.

After each implementation-subagent fix round, save the returned implementation report to a temp file, append that path to the implementation reports temp file, treat that saved file as the latest implementation report for the next review prompt, append the report to `{REVIEW_LOOP_HISTORY}`, then run the workspace hygiene gate checks and verify the latest commit hash plus changed-file list match the implementation subagent's report before starting the next fresh review round.

## 12) Finish

Once the post-implementation review loop passes (`blocking_issue_count: 0`):

Now, and only now for a successful run, read the later-work store by running:

```bash
python3 <skill-directory>/orchestrator/later_work.py summarize --path {LATER_WORK_PATH}
```

Include the summary under `Other important work found during this run`. If the command prints `No later work was filed.`, report that briefly instead.

Clean up temporary artifacts created during the loop (for example plan scratch files and temp notes), except the later-work store and wrapper until after the summary above has been generated, then run:
- `git -C {WORKTREE_PATH} status --short`
- `git -C {WORKTREE_PATH} rev-parse --short HEAD`
- `git -C {WORKTREE_PATH} diff --name-only main...HEAD`

If the implementation subagent is still open, close it and clear its saved handle or `session_id` before handing off to finishing.

Finally, in one paragraph, briefly describe what was built/accomplished/changed/fixed. Then report the process to the user using concrete facts and returned artifacts: how many planning issue-review/synthesis rounds, how many code-review rounds, the current `HEAD`, the changed-file list, the implementation subagent's latest summary and verification results, the later-work summary, and any reviewer-reported residual issues.

Then read and follow `<skill-directory>/subskills/trycycle-finishing/SKILL.md` to present the user with options for integrating the implementation workspace (merge, PR, etc.).
