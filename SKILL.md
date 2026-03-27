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
- In the default mode, it is the path to the dedicated git worktree created in Step 4.
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

When a step below references `{IMPLEMENTATION_PLAN_PATH}`, use the latest absolute plan path returned by the planning subagent in the current trycycle session. Update it after the initial planning result and after every plan-edit result.

When a step below references `{TEST_PLAN_PATH}`, use the latest absolute test-plan path returned by the test-plan subagent in the current trycycle session. Update it after every test-plan result.

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
- Planning subagents are ephemeral across plan-edit rounds so they can remain independent: spawn a fresh planning agent for the initial plan and for every plan-edit round until the plan is judged already excellent without changes.
- In native mode, implementation subagents are persistent: create one implementation agent, then resume it for every implementation-fix round.
- In fallback-runner mode, implementation subagents are persistent through the runner: create one implementation session, record its `session_id`, then resume it through the runner for every implementation-fix round.
- In fallback-runner mode, record the resolved `dispatch.backend` for persistent sessions and reuse that same backend on every `resume`.
- Review subagents are ephemeral: create a fresh reviewer for each post-implementation review round.
- For planning rounds, pass `{USER_REQUEST_TRANSCRIPT}` as the task input. Do not use the full prior conversation.
- Render the prompt template with the prompt builder and pass the rendered prompt verbatim.
- User instructions still apply. When they are relevant, relay them.
- If a subagent returns `USER DECISION REQUIRED:`, keep that same agent or session alive until the user's reply has been forwarded and the round has resolved.

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

The agreed testing strategy is used in step 7.

## 4) Prepare implementation workspace

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

## 5) Workspace hygiene gate (mandatory)

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

Immediately before dispatch, prepare the `planning-initial` phase via the phase wrapper using template `<skill-directory>/subagents/prompt-planning-initial.md`, `--set WORKTREE_PATH={WORKTREE_PATH}`, `--transcript-placeholder USER_REQUEST_TRANSCRIPT`, and `--require-nonempty-tag task_input_json`.

Monitor by checking every 5 minutes until 60 minutes have passed. Then, and only then, kill it and retry.

Wait for the planning subagent to return either:
- a planning report containing `## Plan verdict`, `## Plan path`, `## Commit`, and `## Changed files`
- or a report beginning with `USER DECISION REQUIRED:`

If the planning subagent returns `USER DECISION REQUIRED:`, present that question to the user, send the user's answer back to that active planning subagent, and wait again for either a planning report or another `USER DECISION REQUIRED:` report. Monitor by checking every 5 minutes until 60 minutes have passed. Then, and only then, kill it and retry.

If a planning report was returned, update `{IMPLEMENTATION_PLAN_PATH}` from `## Plan path`, then run the workspace hygiene gate checks, verify the latest commit hash plus changed-file list match the planning subagent's report, confirm the plan file exists at `{IMPLEMENTATION_PLAN_PATH}`, then close that planning subagent and clear any saved handle or `session_id` for it.

## 7) Plan-editor loop (up to 5 rounds)

Deploy a fresh planning subagent to critique the current plan against the user's request and the repo, then either declare it already excellent unchanged or improve it directly.

The plan editor is stateless: each round is a fresh first-look pass with only the template, the same task input used for initial planning, and the current plan.

Immediately before each edit dispatch, prepare the `planning-edit` phase via the phase wrapper using template `<skill-directory>/subagents/prompt-planning-edit.md`, `--set WORKTREE_PATH={WORKTREE_PATH}`, `--set IMPLEMENTATION_PLAN_PATH={IMPLEMENTATION_PLAN_PATH}`, `--transcript-placeholder USER_REQUEST_TRANSCRIPT`, and `--require-nonempty-tag task_input_json`, then dispatch a fresh planning subagent with the returned `prompt_path`.

Monitor by checking every 5 minutes until 60 minutes have passed. Then, and only then, kill it and retry.

After each edit round:
1. Wait for the planning subagent to return either an updated planning report containing `## Plan verdict`, `## Plan path`, `## Commit`, and `## Changed files`, or a report beginning with `USER DECISION REQUIRED:`.
2. If the planning subagent returns `USER DECISION REQUIRED:`, present that question to the user, send the user's answer back to that active planning subagent, and wait again for either an updated planning report or another `USER DECISION REQUIRED:` report. Monitor by checking every 5 minutes until 60 minutes have passed. Then, and only then, kill it and retry.
3. Update `{IMPLEMENTATION_PLAN_PATH}` from `## Plan path` in the latest planning report.
4. Run the workspace hygiene gate checks and verify the latest commit hash plus changed-file list match the planning subagent's report.
5. Close that planning subagent for the completed round and clear any saved handle or `session_id` for it.
6. If `## Plan verdict` is `READY`, continue to step 8 with the current `{IMPLEMENTATION_PLAN_PATH}`. **If the verdict is NOT `READY`, do NOT proceed to step 8 - continue to step 7 for another planning round.**
7. If `## Plan verdict` is `REVISED`, repeat with a fresh planning subagent.
8. Repeat up to 5 rounds.

If the plan still is not judged ready after the 5th editor round: **STOP. Do NOT proceed to step 8.**
1. Stop looping.
2. Dispatch a subagent to review past subagent sessions and hypothesize why the loop is not converging. Monitor by checking every 5 minutes until 60 minutes have passed. Then, and only then, kill it and retry.
3. Present that report and the latest planning report to the user and **await user instructions before taking any further action.**

## 8) Build test plan (subagent-owned)

Now that the implementation plan has passed the plan-editor loop and is finalized, dispatch a subagent to reconcile the testing strategy against the plan and produce the concrete test plan, starting from high-value existing automated checks where they exist and adding new tests where coverage is missing.

Immediately before dispatch, prepare the `test-plan` phase via the phase wrapper using template `<skill-directory>/subagents/prompt-test-plan.md`, `--set IMPLEMENTATION_PLAN_PATH={IMPLEMENTATION_PLAN_PATH}`, `--set WORKTREE_PATH={WORKTREE_PATH}`, `--transcript-placeholder FULL_CONVERSATION_VERBATIM`, and `--require-nonempty-tag conversation`.

Monitor by checking every 5 minutes until 60 minutes have passed. Then, and only then, kill it and retry.

When the subagent returns:

1. Update `{TEST_PLAN_PATH}` from `## Test plan path` in the latest test-plan report.
2. If the test-plan report includes `## Strategy changes requiring user approval`, present that section to the user verbatim.
3. If the user requests changes or redirects the approach, close that completed test-plan subagent and clear any saved handle or `session_id` for it, then rerun the same `test-plan` phase wrapper command immediately before redispatching. Monitor by checking every 5 minutes until 60 minutes have passed. Then, and only then, kill it and retry. Update `{TEST_PLAN_PATH}` from the latest test-plan report. Repeat until the user explicitly approves or the report no longer includes that section.
4. Do not proceed until the current test-plan report either has no `## Strategy changes requiring user approval` section or the user has explicitly approved it.
5. Run the workspace hygiene gate checks, verify the latest commit hash plus changed-file list match the test-plan subagent's report, and verify the test plan file exists at `{TEST_PLAN_PATH}`.
6. Close the completed test-plan subagent for the approved report and clear any saved handle or `session_id` for it.

## 9) Execute with trycycle-executing (subagent-owned)

Code implementation must be done by a new, dedicated subagent.

Before dispatching the implementation subagent, rebase onto the latest base branch to incorporate any changes merged by other agents during planning:

```bash
git -C {WORKTREE_PATH} fetch origin main
git -C {WORKTREE_PATH} rebase origin/main
```

If the rebase has conflicts, stop and present them to the user.

Spawn a fresh implementation subagent and give it the final excellent plan.

The implementation subagent stays in execute mode until the plan is complete, the work has gone through red/green/refactor cycles as needed, and all required automated tests are passing for legitimate reasons. Failed checks mean keep improving the code and tests unless there is a genuine blocker. Do not accept weakened or deleted valid tests as a shortcut to green.

Immediately before dispatch, prepare the `executing` phase via the phase wrapper using template `<skill-directory>/subagents/prompt-executing.md`, `--set IMPLEMENTATION_PLAN_PATH={IMPLEMENTATION_PLAN_PATH}`, `--set TEST_PLAN_PATH={TEST_PLAN_PATH}`, and `--set WORKTREE_PATH={WORKTREE_PATH}`, then dispatch the implementation subagent with the returned `prompt_path`.

In fallback-runner mode, record the returned `dispatch.backend` as `{IMPLEMENTATION_BACKEND}` alongside the saved `session_id`.

Monitor by checking every 5 minutes until 180 minutes have passed. Then, and only then, kill it and retry.
If you kill and retry this implementation round, create a fresh implementation subagent or runner session and replace the saved implementation handle. In fallback-runner mode, also replace the saved `session_id` and `{IMPLEMENTATION_BACKEND}` with the fresh dispatch values.

Do not proceed to post-implementation review until the implementation subagent has returned an implementation report.

After implementation completes, run the workspace hygiene gate checks and verify the latest commit hash plus changed-file list match the implementation subagent's report before launching post-implementation review.

## 10) Post-implementation review loop (up to 8 rounds)

After execution completes, deploy a new reviewer with no prior context and give it the finalized implementation plan plus the finalized test plan.

Immediately before dispatch, prepare the `post-implementation-review` phase via the phase wrapper using template `<skill-directory>/subagents/prompt-post-impl-review.md`, `--set WORKTREE_PATH={WORKTREE_PATH}`, `--set IMPLEMENTATION_PLAN_PATH={IMPLEMENTATION_PLAN_PATH}`, and `--set TEST_PLAN_PATH={TEST_PLAN_PATH}`, then dispatch a review subagent with the returned `prompt_path`.

Monitor by checking every 5 minutes until 60 minutes have passed. Then, and only then, kill it and retry.

Use the review subagent's output as the fix-loop input. As soon as you have captured the reviewer's stdout or decided the review loop is done, close that completed review subagent and clear any saved handle or `session_id` for it.

After every review round, save the reviewer's raw stdout to a temp file immediately and extract a structured review-observations artifact from it:

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

When another fix round is needed:
1. Prepare the `executing` phase again via the phase wrapper using template `<skill-directory>/subagents/prompt-executing.md`, `--set IMPLEMENTATION_PLAN_PATH={IMPLEMENTATION_PLAN_PATH}`, `--set TEST_PLAN_PATH={TEST_PLAN_PATH}`, `--set WORKTREE_PATH={WORKTREE_PATH}`, `--set-file POST_IMPLEMENTATION_REVIEW_OBSERVATIONS_JSON=<review-observations-temp-file>`, and `--ignore-tag-for-placeholders post_implementation_review_observations_json`.
2. In native mode, resume the same implementation subagent and send the exact returned `prompt_path` contents verbatim. In fallback-runner mode, resume the implementation session through `python3 <skill-directory>/orchestrator/subagent_runner.py resume` using the saved `session_id`, `--backend {IMPLEMENTATION_BACKEND}`, and the wrapper-prepared `prompt_path`.
3. Monitor by checking every 5 minutes until 180 minutes have passed. Then, and only then, kill it and retry.
4. If you kill and retry this implementation round, create a fresh implementation subagent or runner session and replace the saved implementation handle. In fallback-runner mode, also replace the saved `session_id` and `{IMPLEMENTATION_BACKEND}` with the fresh dispatch values.

After each implementation-subagent fix round, run the workspace hygiene gate checks and verify the latest commit hash plus changed-file list match the implementation subagent's report before starting the next fresh review round.

Stop when either condition is met:
1. The extracted review-observations artifact reports `blocking_issue_count: 0`.
2. 8 rounds have been completed.

If the latest extracted review-observations artifact still reports `blocking_issue_count > 0` after the 8th review:
1. Stop looping.
2. Dispatch a subagent to review past subagent sessions and hypothesize why the loop is not converging. Monitor by checking every 5 minutes until 60 minutes have passed. Then, and only then, kill it and retry.
3. Present that report and the latest review output to the user and await user instructions.

## 11) Finish

Once the post-implementation review loop passes (`blocking_issue_count: 0`):

Clean up temporary artifacts created during the loop (for example plan scratch files and temp notes), then run:
- `git -C {WORKTREE_PATH} status --short`
- `git -C {WORKTREE_PATH} rev-parse --short HEAD`
- `git -C {WORKTREE_PATH} diff --name-only main...HEAD`

If the implementation subagent is still open, close it and clear its saved handle or `session_id` before handing off to finishing.

Report the process to the user using concrete facts and returned artifacts: how many plan-editor rounds, how many code-review rounds, the current `HEAD`, the changed-file list, the implementation subagent's latest summary and verification results, and any reviewer-reported residual issues.

Then read and follow `<skill-directory>/subskills/trycycle-finishing/SKILL.md` to present the user with options for integrating the implementation workspace (merge, PR, etc.).
