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
- Bind transcript placeholders with `--transcript-placeholder NAME`. Only the user-intent extraction phase should receive raw conversation transcript; later phases should receive `{USER_INTENT}` and explicit artifacts instead.
- If live transcript lookup fails but you have an existing transcript file, bind that transcript with `--transcript-file NAME=PATH` instead of `--transcript-placeholder NAME`. Do not combine transcript binding flags or `--set`/`--set-file` for the same placeholder.
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

When a phase wrapper call needs `{FULL_CONVERSATION_VERBATIM}`:
1. For Codex CLI, let the wrapper use direct session lookup by default.
2. For Kimi CLI, always pass `--transcript-cli kimi-cli` on transcript-bearing wrapper calls and let direct session lookup run first.
3. If the wrapper reports that a canary is required, run `python3 <skill-directory>/orchestrator/user-request-transcript/mark_with_canary.py` as a separate top-level command, capture stdout exactly as `{CANARY}`, then rerun the wrapper with `--canary "{CANARY}"`. For Kimi-hosted runs, keep `--transcript-cli kimi-cli` on the rerun as well.
4. For Claude Code, always run `python3 <skill-directory>/orchestrator/user-request-transcript/mark_with_canary.py` as a separate top-level command first, capture stdout exactly as `{CANARY}`, then invoke the wrapper with `--transcript-cli claude-code --canary "{CANARY}"`.
5. For OpenCode, always run `python3 <skill-directory>/orchestrator/user-request-transcript/mark_with_canary.py` as a separate top-level command first, capture stdout exactly as `{CANARY}`, then invoke the wrapper with `--transcript-cli opencode --canary "{CANARY}"`.
6. If live lookup still fails and the current user request can be reconstructed from visible context, write that transcript to a temp file and rerun the wrapper with `--transcript-file NAME=<temp-file>` for the needed transcript placeholder. Use this only as a fallback, and bind each placeholder exactly once.

The canary must be emitted by a separate top-level command so it reaches the live session transcript before lookup. Do not rely on shell-specific capture or assignment forms that may keep the canary out of visible command output; shells and host wrappers vary, and if the canary is not visibly emitted into the session transcript, lookup will fail. Build transcript placeholder values immediately before each phase wrapper call that uses them.
Kimi and OpenCode support is explicit here because `host` and `auto` cannot reliably detect a Kimi host, and OpenCode requires canary-based lookup.

When a step below references `{POST_IMPLEMENTATION_REVIEW_OBSERVATIONS_JSON}`, use the extracted review observations JSON exactly as the placeholder value.

When a step below references `{ACCEPTANCE_ARTIFACT_REVIEW_OBSERVATIONS_JSON}`, use the extracted acceptance-artifact review observations JSON exactly as the placeholder value.

When a step below references `{LATEST_IMPLEMENTATION_REPORT}`, use the most recent implementation report returned by the implementation subagent. Bind it with `--set-file` from the temp-file path where you saved that report.

When a step below references `{REVIEW_LOOP_HISTORY}`, use the accumulated post-execution load-bearing, acceptance-artifact, and post-implementation review-loop history artifact from the current trycycle session.

When a step below references `{PLAN_LOAD_BEARING_LEDGER_PATH}`, use the latest accepted plan-time load-bearing ledger path from the current trycycle session.

When a step below references `{POST_EXECUTION_LOAD_BEARING_LEDGER_PATH}`, use the latest accepted post-execution load-bearing ledger path from the current trycycle session.

When a step below references `{LOAD_BEARING_LEDGER_PATH}`, use the current load-bearing gate's canonical ledger output path. The curator creates this file and the evaluator updates it in place.

When a step below references `{LOAD_BEARING_SCOPE}`, use exactly `plan` for the plan-time gate or `post-execution` for the post-execution gate.

When a step below references `{LOAD_BEARING_VALIDATION_REPORTS}`, use the current load-bearing gate's temp file containing newline-delimited absolute validator report paths. It may be empty when no validation targets exist.

When a step below references `{LOAD_BEARING_EVALUATION_REPORT}`, use the latest saved load-bearing evaluator report for the current gate.

When a step below references `{PREVIOUS_LOAD_BEARING_STRATEGY}`, bind the prior rejected load-bearing strategy report only during a strategy-revision round.

When a step below references `{LOAD_BEARING_STRATEGY_REVIEW_REPORT}`, bind the latest load-bearing strategy-review correction report only during a strategy-revision round.

When a step below references `{LOAD_BEARING_REVIEW_OBSERVATIONS_JSON}`, use the extracted post-execution load-bearing review observations JSON exactly as the placeholder value.

When a step below references `{IMPLEMENTATION_PLAN_PATH}`, use the latest absolute plan path returned by the planning subagent in the current trycycle session. Update it after the initial planning result, after every plan-edit result, and after every post-review plan-reconsideration result.

When a step below references `{TEST_PLAN_PATH}`, use the latest absolute test-plan path returned by the test-plan subagent or post-review plan-reconsideration subagent in the current trycycle session. Update it after every test-plan result and every post-review plan-reconsideration result.

When a step below references `{TESTING_STRATEGY_PATH}`, use the absolute path to the latest testing-strategy artifact for the current Trycycle run. Update it after every accepted testing-strategy result.

When a step below references the approved validation scope, use the final `## Validation approval scope` section from the latest user-approved concrete test plan at `{TEST_PLAN_PATH}`. The testing strategy may forecast this scope, but only the concrete test plan approval is the durable authorization checkpoint for state-changing, restricted, external, costly, or environment-mutating validation actions.

When a step below references `{USER_INTENT_PATH}`, use the absolute path to the append-only user-intent artifact for the current Trycycle run.

When a step below references `{USER_INTENT}`, bind the current contents of `{USER_INTENT_PATH}` with `--set-file USER_INTENT={USER_INTENT_PATH}`. Do not manually inline it. Any phase wrapper invocation that binds `{USER_INTENT}` must also pass `--ignore-tag-for-placeholders user_intent` because the artifact preserves relevant text verbatim and may legitimately contain placeholder-like code.

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
- Post-review plan-reconsideration checkpoints also use fresh planning subagents. They may update the implementation plan or test plan when implementation has exposed a real plan gap.
- In native mode, implementation subagents are persistent: create one implementation agent, then resume it for every implementation-fix round.
- In fallback-runner mode, implementation subagents are persistent through the runner: create one implementation session, record its `session_id`, then resume it through the runner for every implementation-fix round.
- In fallback-runner mode, record the resolved `dispatch.backend` for persistent sessions and reuse that same backend on every `resume`.
- Review and load-bearing gate subagents are ephemeral: create fresh load-bearing finder, curator, strategist, strategy-review, validator, and evaluator subagents for each gate; create a fresh assignment subagent and fresh territory reviewers for each plan-hardening round; create a fresh acceptance-artifact reviewer and, when the acceptance gate passes, a fresh assignment subagent, fresh territory code reviewers, and a fresh review-merge subagent for each verification round.
- The user-intent extraction phase is the only phase that receives raw conversation transcript. All later phases receive `{USER_INTENT}` plus explicit artifacts such as the testing strategy, implementation plan, test plan, implementation report, review observations, and review-loop history.
- Render the prompt template with the prompt builder and pass the rendered prompt verbatim.
- User instructions still apply. When they are relevant, relay them.
- If a subagent returns `USER DECISION REQUIRED:`, keep that same agent or session alive until the user's reply has been forwarded and the round has resolved.
- The initial user-intent artifact is subagent-owned. Do not create it manually.
- User intent freshness is conductor-owned after `{USER_INTENT_PATH}` exists. After every later user message, before dispatching or resuming any subagent, decide whether the new user message adds, removes, corrects, approves, rejects, narrows, broadens, prioritizes, supports an assistant proposal, or otherwise changes the user's intent, constraints, process requirements, scope, or acceptance criteria. If it does, append a new span entry under `## User Intent Updates, Oldest First` using the same verbatim span format as the initial artifact. This may include assistant-proposed text when the user has supported it. Preserve chronological order. Do not rewrite, reorder, summarize, infer, normalize, or regenerate earlier content.

Example: if the user says "We're almost there, don't start over," relay that instruction.

## Empty Task Result Repair (OpenCode native mode)

OpenCode's native `task` tool can return empty `<task_result>` when a subagent's final assistant message contains no text parts (only tool calls or reasoning). This is a known OpenCode issue (see https://github.com/anomalyco/opencode/issues/24447). The subagent session data is not lost — it is preserved in OpenCode's SQLite database.

When using OpenCode in native mode: after dispatching any subagent, check the raw `<task_result>` block. If it contains only whitespace between the opening and closing tags (no visible text), the result is empty and must be repaired.

To repair, extract the session ID from the task tool output (the `task_id` field — it starts with `ses_`) and run:

```bash
python3 <skill-directory>/orchestrator/repair_empty_result.py --session-id <session-id>
```

Read the script's stdout and treat it as the subagent's actual result. This is deterministic — it reads structured part data from the subagent's session database, no AI re-prompting needed.

The script extracts:
- Tool calls and their outputs from the most recent steps in the subagent session
- Model reasoning from the final step
- Relevant text from the final step

If the script returns "(no extractable content found in subagent session parts)", escalate to the user. If the script exits with a non-zero status (database not found, session not found, schema error), note the error and escalate as well — the orchestrator cannot recover those cases without user input.

The script auto-detects the OpenCode database location. If that fails, pass `--db-path` explicitly or direct the user to set `OPENCODE_DB_PATH` or `OPENCODE_DATA_DIR`.

## Load-Bearing Gate Helper

When a workflow step says to run a full load-bearing gate, use this helper exactly. The helper returns a saved evaluator report path, a normalized review-observations JSON path, the canonical `{LOAD_BEARING_LEDGER_PATH}`, the evaluator verdict, and the normalized `blocking_issue_count`.

Before starting, create a temp path for `{LOAD_BEARING_LEDGER_PATH}` and an empty temp file for `{LOAD_BEARING_VALIDATION_REPORTS}`. Start the phase prompt paths temp file and loop outputs temp file if needed. Append every load-bearing phase `prompt_path` to the phase prompt paths temp file, and save every subagent reply to a temp file before using it in another phase. Append load-bearing reports to the loop outputs temp file with clear labels such as `load-bearing-plan finder report:`, `load-bearing-plan evaluator report:`, `load-bearing-post-execution validator report:`, and `load-bearing-post-execution evaluator report:`. Monitor every load-bearing subagent by checking every 5 minutes until 60 minutes have passed. Then, and only then, kill it and retry.

1. Set `{LOAD_BEARING_SCOPE}` to `plan` for the plan-time gate or `post-execution` for the post-execution gate.
2. Prepare and dispatch the finder phase.
   - For `plan`, use template `<skill-directory>/subagents/prompt-load-bearing-finder-plan.md` with `--set LOAD_BEARING_SCOPE=plan`, `--set WORKTREE_PATH={WORKTREE_PATH}`, `--set IMPLEMENTATION_PLAN_PATH={IMPLEMENTATION_PLAN_PATH}`, `--set-file USER_INTENT={USER_INTENT_PATH}`, `--require-nonempty-tag user_intent`, and `--ignore-tag-for-placeholders user_intent`.
   - For `post-execution`, use template `<skill-directory>/subagents/prompt-load-bearing-finder-execution.md` with `--set LOAD_BEARING_SCOPE=post-execution`, `--set WORKTREE_PATH={WORKTREE_PATH}`, `--set IMPLEMENTATION_PLAN_PATH={IMPLEMENTATION_PLAN_PATH}`, `--set TEST_PLAN_PATH={TEST_PLAN_PATH}`, `--set-file LATEST_IMPLEMENTATION_REPORT=<latest-implementation-report-temp-file>`, `--set-file USER_INTENT={USER_INTENT_PATH}`, `--require-nonempty-tag user_intent`, `--require-nonempty-tag latest_implementation_report`, `--ignore-tag-for-placeholders user_intent`, and `--ignore-tag-for-placeholders latest_implementation_report`.
3. Prepare and dispatch the curator phase with template `<skill-directory>/subagents/prompt-load-bearing-curate.md`, `--set LOAD_BEARING_SCOPE={LOAD_BEARING_SCOPE}`, `--set WORKTREE_PATH={WORKTREE_PATH}`, `--set LOAD_BEARING_LEDGER_PATH={LOAD_BEARING_LEDGER_PATH}`, `--set-file USER_INTENT={USER_INTENT_PATH}`, `--set-file FINDER_REPORT=<finder-report-temp-file>`, `--require-nonempty-tag user_intent`, `--require-nonempty-tag finder_report`, `--ignore-tag-for-placeholders user_intent`, and `--ignore-tag-for-placeholders finder_report`.
4. Prepare and dispatch the strategist phase with template `<skill-directory>/subagents/prompt-load-bearing-strategist.md`, `--set LOAD_BEARING_SCOPE={LOAD_BEARING_SCOPE}`, `--set WORKTREE_PATH={WORKTREE_PATH}`, `--set-file LOAD_BEARING_LEDGER={LOAD_BEARING_LEDGER_PATH}`, `--set-file TESTING_STRATEGY={TESTING_STRATEGY_PATH}`, `--require-nonempty-tag load_bearing_ledger`, `--require-nonempty-tag testing_strategy`, `--ignore-tag-for-placeholders load_bearing_ledger`, and `--ignore-tag-for-placeholders testing_strategy`. If `{TEST_PLAN_PATH}` exists, also pass `--set-file TEST_PLAN={TEST_PLAN_PATH}`, `--require-nonempty-tag test_plan`, and `--ignore-tag-for-placeholders test_plan`.
5. Prepare and dispatch the strategy-review phase with template `<skill-directory>/subagents/prompt-load-bearing-strategy-review.md`, `--set LOAD_BEARING_SCOPE={LOAD_BEARING_SCOPE}`, `--set WORKTREE_PATH={WORKTREE_PATH}`, `--set-file LOAD_BEARING_LEDGER={LOAD_BEARING_LEDGER_PATH}`, `--set-file TESTING_STRATEGY={TESTING_STRATEGY_PATH}`, `--set-file LOAD_BEARING_STRATEGY=<latest-strategy-report-temp-file>`, `--require-nonempty-tag load_bearing_ledger`, `--require-nonempty-tag testing_strategy`, `--require-nonempty-tag load_bearing_strategy`, `--ignore-tag-for-placeholders load_bearing_ledger`, `--ignore-tag-for-placeholders testing_strategy`, and `--ignore-tag-for-placeholders load_bearing_strategy`. If `{TEST_PLAN_PATH}` exists, also pass `--set-file TEST_PLAN={TEST_PLAN_PATH}`, `--require-nonempty-tag test_plan`, and `--ignore-tag-for-placeholders test_plan`.
6. If the strategy-review verdict is `REVISE`, rerun the strategist phase with the same scope, worktree, ledger, testing-strategy, and optional test-plan bindings, plus `--set-file PREVIOUS_LOAD_BEARING_STRATEGY=<latest-strategy-report-temp-file>`, `--set-file LOAD_BEARING_STRATEGY_REVIEW_REPORT=<latest-strategy-review-report-temp-file>`, `--require-nonempty-tag previous_load_bearing_strategy`, `--require-nonempty-tag load_bearing_strategy_review_report`, `--ignore-tag-for-placeholders previous_load_bearing_strategy`, and `--ignore-tag-for-placeholders load_bearing_strategy_review_report`. Then rerun strategy-review. Repeat until the strategy-review verdict is `READY`, up to 3 strategy-review rounds.
7. If strategy review is still not `READY` after 3 rounds, prepare `nonconvergence-review` with template `<skill-directory>/subagents/prompt-nonconvergence-review.md`, `--set TRYCYCLE_SKILL_PATH=<skill-directory>/SKILL.md`, `--set NONCONVERGENCE_CONTEXT="Load-bearing strategy-review loop reached 3 rounds without a READY verdict."`, `--set WORKTREE_PATH={WORKTREE_PATH}`, `--set IMPLEMENTATION_PLAN_PATH={IMPLEMENTATION_PLAN_PATH}`, `--set TEST_PLAN_PATH=<current TEST_PLAN_PATH or "Not built yet; the plan load-bearing gate did not converge before the test-plan phase.">`, `--set-file PHASE_PROMPT_PATHS=<phase-prompt-paths-temp-file>`, `--set-file LOOP_OUTPUT_PATHS=<loop-outputs-temp-file>`, `--set-file USER_INTENT={USER_INTENT_PATH}`, and `--ignore-tag-for-placeholders user_intent`. If execution has started, bind `IMPLEMENTATION_REPORT_PATHS` with `--set-file IMPLEMENTATION_REPORT_PATHS=<implementation-reports-temp-file>`; otherwise bind `--set IMPLEMENTATION_REPORT_PATHS="Not applicable; execution did not start."`. Present that report and the latest strategy-review report to the user and await instructions.
8. Copy each fenced `load-bearing-validation-target` block from the accepted strategy to its own temp file. If there are no fenced target blocks, leave `{LOAD_BEARING_VALIDATION_REPORTS}` empty and skip validators so the evaluator can return `NO_TARGETS`.
9. If target blocks exist, dispatch one fresh validator per target in parallel using template `<skill-directory>/subagents/prompt-load-bearing-validator.md`, `--set LOAD_BEARING_SCOPE={LOAD_BEARING_SCOPE}`, `--set-file LOAD_BEARING_VALIDATION_TARGET=<validation-target-temp-file>`, `--set-file TESTING_STRATEGY={TESTING_STRATEGY_PATH}`, `--require-nonempty-tag validation_target`, `--require-nonempty-tag testing_strategy`, `--ignore-tag-for-placeholders validation_target`, and `--ignore-tag-for-placeholders testing_strategy`. If `{TEST_PLAN_PATH}` exists, also pass `--set-file TEST_PLAN={TEST_PLAN_PATH}`, `--require-nonempty-tag test_plan`, and `--ignore-tag-for-placeholders test_plan`. Save each validator reply to a temp file and rewrite `{LOAD_BEARING_VALIDATION_REPORTS}` as a newline-delimited list of those absolute reply paths.
10. Prepare and dispatch the evaluator phase with template `<skill-directory>/subagents/prompt-load-bearing-evaluate.md`, `--set LOAD_BEARING_SCOPE={LOAD_BEARING_SCOPE}`, `--set LOAD_BEARING_LEDGER_PATH={LOAD_BEARING_LEDGER_PATH}`, `--set-file USER_INTENT={USER_INTENT_PATH}`, `--set-file LOAD_BEARING_LEDGER={LOAD_BEARING_LEDGER_PATH}`, `--set-file TESTING_STRATEGY={TESTING_STRATEGY_PATH}`, `--set-file LOAD_BEARING_STRATEGY=<latest-strategy-report-temp-file>`, `--set-file LOAD_BEARING_VALIDATION_REPORTS={LOAD_BEARING_VALIDATION_REPORTS}`, `--require-nonempty-tag user_intent`, `--require-nonempty-tag load_bearing_ledger`, `--require-nonempty-tag testing_strategy`, `--require-nonempty-tag load_bearing_strategy`, `--ignore-tag-for-placeholders user_intent`, `--ignore-tag-for-placeholders load_bearing_ledger`, `--ignore-tag-for-placeholders testing_strategy`, `--ignore-tag-for-placeholders load_bearing_strategy`, and `--ignore-tag-for-placeholders load_bearing_validation_reports`. If `{TEST_PLAN_PATH}` exists, also pass `--set-file TEST_PLAN={TEST_PLAN_PATH}`, `--require-nonempty-tag test_plan`, and `--ignore-tag-for-placeholders test_plan`. Do not require `load_bearing_validation_reports` to be non-empty; the tag contains newline-delimited validator report paths and may be empty.
11. Save the evaluator reply to a temp file and extract the structured observations:

```bash
python3 <skill-directory>/orchestrator/review_observations.py extract \
  --reply <load-bearing-evaluator-reply-temp-file> \
  --output <load-bearing-review-observations-temp-file>
```

12. Check that the evaluator markdown verdict and normalized JSON are self-consistent before routing:
   - `VERIFIED` and `NO_TARGETS` require normalized `status: "no_issues"` and `blocking_issue_count: 0`.
   - `FALSIFIED` and `INCONCLUSIVE` require normalized `status: "issues_found"` and `blocking_issue_count > 0`.
   - `NEEDS_USER_APPROVAL` requires normalized `status: "issues_found"`, `blocking_issue_count > 0`, and at least one critical or major `other` observation naming the blocked validation action and why it is materially outside the approved validation scope.
   If the verdict and JSON conflict, stop and surface the evaluator report plus extractor output to the user rather than guessing.
13. Route by the self-consistent evaluator verdict. Use normalized `blocking_issue_count` as the machine-readable blocker count after consistency has been checked.

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

## 3) Prepare user intent (subagent-owned)

Create a temp file path for `{USER_INTENT_PATH}`. Do not write the initial artifact yourself.

Immediately before dispatch, prepare the `user-intent` phase via the phase wrapper using template `<skill-directory>/subagents/prompt-user-intent.md`, `--set USER_INTENT_PATH={USER_INTENT_PATH}`, `--transcript-placeholder FULL_CONVERSATION_VERBATIM`, `--require-nonempty-tag conversation`, and `--ignore-tag-for-placeholders conversation`, then dispatch a fresh subagent with the returned `prompt_path`.

Monitor by checking every 5 minutes until 60 minutes have passed. Then, and only then, kill it and retry.

When the subagent returns, verify the report contains `## User intent path`, confirm it matches `{USER_INTENT_PATH}`, and confirm the file exists and is non-empty. Do not read or summarize the file contents. Close the completed user-intent subagent and clear any saved handle or `session_id`.

## 4) Testing strategy

Dispatch a subagent to analyze the user's intent artifact and the codebase, then propose a testing strategy.

Immediately before dispatch, prepare the `test-strategy` phase via the phase wrapper using template `<skill-directory>/subagents/prompt-test-strategy.md`, `--set-file USER_INTENT={USER_INTENT_PATH}`, `--require-nonempty-tag user_intent`, and `--ignore-tag-for-placeholders user_intent`.

Monitor by checking every 5 minutes until 60 minutes have passed. Then, and only then, kill it and retry.

When the subagent returns a proposed strategy, save the exact returned strategy to a temp file and set `{TESTING_STRATEGY_PATH}` to that path.

General autonomy instructions affect only the test approval gate, meaning the testing-strategy approval gate in this step. If the user has said something broad such as "do not ask for confirmation", "proceed autonomously", "keep going", "don't wait for me", "I'm going to bed", or equivalent, treat that as permission to skip asking for explicit approval of the proposed testing strategy in this step. Close the completed test-strategy subagent, clear any saved handle or `session_id`, and continue with the saved strategy. Do not infer approval for anything else from that general instruction. Other approvals and user-decision stops still apply, including `USER DECISION REQUIRED`, `NEEDS_USER_APPROVAL`, the concrete test-plan and validation-approval-scope approval in step 10, nonconvergence decisions, production or destructive operations, finishing/integration choices, or any other approval gate. The user may explicitly skip a different approval, but they must name that approval or decision specifically; a broad autonomy instruction always and only skips this testing-strategy approval gate.

If there is no general autonomy instruction that skips this gate, present the proposed strategy to the user verbatim and ask for explicit approval or edits. Then close that completed test-strategy subagent and clear any saved handle or `session_id` for it. Do not proceed unless the user explicitly accepts it or provides changes. Silence, implied approval, or the subagent's own recommendation does not count as agreement. The strategy approval confirms the testing direction and forecasted validation scope; the concrete test plan approval in step 10 is the durable approval checkpoint for state-changing, restricted, external, costly, or environment-mutating validation actions. The strategy and any later test plan must not rely on user/human validation; every test plan must include acceptance artifacts for a later blank-slate subagent to inspect against the user request without rerunning or recreating checks. Put the strongest weight on high-value automated checks that verify real user-visible behavior through the actual UI, CLI, HTTP surface, or other outputs the user consumes, rather than tests that only show the implementation is internally self-consistent. Prefer reusing or extending those checks when they already exist, and add new tests wherever the existing suite leaves meaningful gaps in coverage, fidelity, or diagnosis. If the problem statement or prior investigation already identifies automated checks that are red and must go green, the strategy and any later test plan must include them explicitly. After every user response to the strategy, run the user-intent freshness check before proceeding or redispatching. If the user requests changes or redirects the approach, rerun the same `test-strategy` phase wrapper command immediately before redispatching. Monitor by checking every 5 minutes until 60 minutes have passed. Then, and only then, kill it and retry. Save the revised strategy to `{TESTING_STRATEGY_PATH}` and present it verbatim. Repeat until the user explicitly approves a strategy.

The agreed testing strategy is used in step 10 through `{TESTING_STRATEGY_PATH}`.

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

Before and after each major phase (`plan load-bearing`, `plan-hardening`, `execution`, `post-execution load-bearing`, `acceptance-artifact review`, `post-implementation review`), run:
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

Immediately before dispatch, prepare the `planning-initial` phase via the phase wrapper using template `<skill-directory>/subagents/prompt-planning-initial.md`, `--set WORKTREE_PATH={WORKTREE_PATH}`, `--set-file USER_INTENT={USER_INTENT_PATH}`, `--require-nonempty-tag user_intent`, and `--ignore-tag-for-placeholders user_intent`.

Monitor by checking every 5 minutes until 60 minutes have passed. Then, and only then, kill it and retry.

Wait for the planning subagent to return either:
- a planning report containing `## Plan verdict`, `## Plan path`, `## Commit`, and `## Changed files`
- or a report beginning with `USER DECISION REQUIRED:`

If the planning subagent returns `USER DECISION REQUIRED:`, present that question to the user, run the user-intent freshness check, send the user's answer back to that active planning subagent, and wait again for either a planning report or another `USER DECISION REQUIRED:` report. Monitor by checking every 5 minutes until 60 minutes have passed. Then, and only then, kill it and retry.

If a planning report was returned, update `{IMPLEMENTATION_PLAN_PATH}` from `## Plan path`, then run the workspace hygiene gate checks, verify the latest commit hash plus changed-file list match the planning subagent's report, confirm the plan file exists at `{IMPLEMENTATION_PLAN_PATH}`, then close that planning subagent and clear any saved handle or `session_id` for it.

## 8) Build and run plan load-bearing gate

Run this gate after initial planning has produced a plan and before the plan-hardening loop. It proves the plan's load-bearing assumptions — the things the chosen approach rests on — before any hardening effort is spent polishing that approach. Before entering this gate for the first time, initialize the plan load-bearing blocking-result counter to 0. Do not reset that counter when a plan-revision round returns here with a revised plan.

Run the full load-bearing gate helper with `{LOAD_BEARING_SCOPE}` set to `plan`.

If the self-consistent evaluator verdict is `VERIFIED` or `NO_TARGETS`, set `{PLAN_LOAD_BEARING_LEDGER_PATH}` to `{LOAD_BEARING_LEDGER_PATH}`, save the evaluator report to the loop outputs temp file with the label `load-bearing-plan evaluator report:`, and continue to step 9, the plan-hardening loop.

If the self-consistent evaluator verdict is `FALSIFIED` or `INCONCLUSIVE`, increment the plan load-bearing blocking-result counter. If this is the third blocking plan load-bearing result, stop before plan hardening and prepare the `nonconvergence-review` phase via the phase wrapper using template `<skill-directory>/subagents/prompt-nonconvergence-review.md`, `--set TRYCYCLE_SKILL_PATH=<skill-directory>/SKILL.md`, `--set NONCONVERGENCE_CONTEXT="Plan load-bearing gate reached 3 blocking rounds before plan hardening."`, `--set WORKTREE_PATH={WORKTREE_PATH}`, `--set IMPLEMENTATION_PLAN_PATH={IMPLEMENTATION_PLAN_PATH}`, `--set TEST_PLAN_PATH="Not built yet; the plan load-bearing gate did not pass before the test-plan phase."`, `--set-file PHASE_PROMPT_PATHS=<phase-prompt-paths-temp-file>`, `--set-file LOOP_OUTPUT_PATHS=<loop-outputs-temp-file>`, `--set IMPLEMENTATION_REPORT_PATHS="Not applicable; execution did not start."`, `--set-file USER_INTENT={USER_INTENT_PATH}`, and `--ignore-tag-for-placeholders user_intent`, then dispatch a subagent with the returned `prompt_path`. Present that nonconvergence report, the latest evaluator report, and the latest planning report to the user and await instructions.

If the self-consistent evaluator verdict is `FALSIFIED` or `INCONCLUSIVE` and the gate has not reached the third blocking result, run a fresh planning subagent with template `<skill-directory>/subagents/prompt-load-bearing-plan-revision.md`, `--set WORKTREE_PATH={WORKTREE_PATH}`, `--set IMPLEMENTATION_PLAN_PATH={IMPLEMENTATION_PLAN_PATH}`, `--set-file USER_INTENT={USER_INTENT_PATH}`, `--set-file LOAD_BEARING_EVALUATION_REPORT=<load-bearing-evaluator-report-temp-file>`, `--require-nonempty-tag user_intent`, `--require-nonempty-tag load_bearing_evaluation_report`, `--ignore-tag-for-placeholders user_intent`, and `--ignore-tag-for-placeholders load_bearing_evaluation_report`. This is planning recovery: the subagent must resolve approach-validation claims during planning, revise the plan around what is known, add verification or acceptance-evidence requirements when that is the real gap, or ask for a user decision. It must not defer proof of approach viability to execution. Monitor by checking every 5 minutes until 60 minutes have passed. Then, and only then, kill it and retry. If the plan-revision subagent returns `USER DECISION REQUIRED:`, present it to the user, run the user-intent freshness check after the user replies, send the answer back to that active subagent, and wait again for either an `UPDATED` report or another `USER DECISION REQUIRED:` report. If it returns `UPDATED`, update `{IMPLEMENTATION_PLAN_PATH}` from `## Plan path`, run the workspace hygiene gate, verify the latest commit hash plus changed-file list match the subagent report, save the plan-revision report to the loop outputs temp file, and close that planning subagent. Return to the start of step 8 and rerun the gate with the revised plan; the plan-hardening loop runs after the gate passes.

If the self-consistent evaluator verdict is `NEEDS_USER_APPROVAL`, present the blocked approval report to the user and await instructions.

## 9) Plan-hardening loop (up to 5 rounds)

Each round, a fresh assignment subagent carves the plan's full surface into review territories, fresh territory reviewers go deep on those territories in parallel, and a fresh planning editor verifies their findings and either declares the plan already excellent unchanged or improves it directly. Every round is a stateless first-look pass: the carve is remade fresh each round, and no subagent receives any prior round's reports.

Round structure:

1. Prepare the `planning-assign` phase via the phase wrapper using template `<skill-directory>/subagents/prompt-planning-assign.md`, `--set REVIEWER_COUNT=5`, `--set WORKTREE_PATH={WORKTREE_PATH}`, `--set IMPLEMENTATION_PLAN_PATH={IMPLEMENTATION_PLAN_PATH}`, `--set-file USER_INTENT={USER_INTENT_PATH}`, `--require-nonempty-tag user_intent`, and `--ignore-tag-for-placeholders user_intent`, then dispatch a fresh assignment subagent with the returned `prompt_path`. Start a phase prompt paths temp file if needed, and append the returned `prompt_path`. Monitor by checking every 5 minutes until 60 minutes have passed. Then, and only then, kill it and retry.
2. Save the assignment report to a temp file. Check only its final lines: the report must end with `COVERAGE: COMPLETE` followed by `TERRITORY_COUNT: <n>` where `<n>` is an integer from 1 to 5. If the check fails, dispatch one fresh assignment subagent for this round; if the second report also fails the check, stop and surface both assignment reports to the user. Do not read the rest of the assignment report; only subagents interpret it. Close each completed assignment subagent and clear any saved handle or `session_id` for it.
3. Dispatch `<n>` fresh territory-review subagents in parallel, one per territory number from 1 through `<n>`. For each, prepare the `planning-review` phase via the phase wrapper using template `<skill-directory>/subagents/prompt-planning-review.md`, `--set TERRITORY_NUMBER=<territory-number>`, `--set WORKTREE_PATH={WORKTREE_PATH}`, `--set IMPLEMENTATION_PLAN_PATH={IMPLEMENTATION_PLAN_PATH}`, `--set-file USER_INTENT={USER_INTENT_PATH}`, `--set-file ASSIGNMENT_REPORT=<assignment-report-temp-file>`, `--require-nonempty-tag user_intent`, `--require-nonempty-tag assignment_report`, `--ignore-tag-for-placeholders user_intent`, and `--ignore-tag-for-placeholders assignment_report`, then dispatch with the returned `prompt_path` and append that `prompt_path` to the phase prompt paths temp file. Monitor every territory reviewer by checking every 5 minutes until 60 minutes have passed. Then, and only then, kill that reviewer and retry it. Save each reviewer reply to its own temp file without reading it, write a newline-delimited list of those absolute paths to a territory-reports list temp file, then close each completed territory-review subagent and clear its saved handle or `session_id`.
4. Prepare the `planning-edit` phase via the phase wrapper using template `<skill-directory>/subagents/prompt-planning-edit.md`, `--set WORKTREE_PATH={WORKTREE_PATH}`, `--set IMPLEMENTATION_PLAN_PATH={IMPLEMENTATION_PLAN_PATH}`, `--set-file USER_INTENT={USER_INTENT_PATH}`, `--set-file ASSIGNMENT_REPORT=<assignment-report-temp-file>`, `--set-file TERRITORY_REVIEW_REPORTS=<territory-reports-list-temp-file>`, `--require-nonempty-tag user_intent`, `--require-nonempty-tag assignment_report`, `--require-nonempty-tag territory_review_reports`, `--ignore-tag-for-placeholders user_intent`, `--ignore-tag-for-placeholders assignment_report`, and `--ignore-tag-for-placeholders territory_review_reports`, then dispatch a fresh planning subagent with the returned `prompt_path`. Append the returned `prompt_path` to the phase prompt paths temp file. Monitor by checking every 5 minutes until 60 minutes have passed. Then, and only then, kill it and retry.

After each round:
1. Wait for the planning editor to return either an updated planning report containing `## Plan verdict`, `## Critical issues`, `## Plan path`, `## Commit`, and `## Changed files`, or a report beginning with `USER DECISION REQUIRED:`.
2. If the planning editor returns `USER DECISION REQUIRED:`, present that question to the user, run the user-intent freshness check, send the user's answer back to that active planning subagent, and wait again for either an updated planning report or another `USER DECISION REQUIRED:` report. Monitor by checking every 5 minutes until 60 minutes have passed. Then, and only then, kill it and retry.
3. Update `{IMPLEMENTATION_PLAN_PATH}` from `## Plan path` in the latest planning report.
4. Run the workspace hygiene gate checks and verify the latest commit hash plus changed-file list match the planning editor's report.
5. Start a loop outputs temp file if needed, save the returned planning report to a temp file, append that path, then close that planning subagent for the completed round and clear any saved handle or `session_id` for it.
6. If `## Plan verdict` is `READY`, continue to step 10 with the current `{IMPLEMENTATION_PLAN_PATH}`. **If the verdict is NOT `READY`, do NOT proceed to step 10 - run another plan-hardening round.**
7. If `## Plan verdict` is `REVISED`, repeat with a fresh assignment subagent, fresh territory reviewers, and a fresh planning editor.
8. Repeat up to 5 rounds.

If the plan still is not judged ready after the 5th round: **STOP. Do NOT proceed to step 10.**
1. Stop looping.
2. Prepare the `nonconvergence-review` phase via the phase wrapper using template `<skill-directory>/subagents/prompt-nonconvergence-review.md`, `--set TRYCYCLE_SKILL_PATH=<skill-directory>/SKILL.md`, `--set NONCONVERGENCE_CONTEXT="Plan-hardening loop reached 5 rounds without a READY verdict."`, `--set WORKTREE_PATH={WORKTREE_PATH}`, `--set IMPLEMENTATION_PLAN_PATH={IMPLEMENTATION_PLAN_PATH}`, `--set TEST_PLAN_PATH="Not built yet; the plan-hardening loop did not converge before the test-plan phase."`, `--set-file PHASE_PROMPT_PATHS=<phase-prompt-paths-temp-file>`, `--set-file LOOP_OUTPUT_PATHS=<loop-outputs-temp-file>`, `--set IMPLEMENTATION_REPORT_PATHS="Not applicable; execution did not start."`, `--set-file USER_INTENT={USER_INTENT_PATH}`, and `--ignore-tag-for-placeholders user_intent`, then dispatch a subagent with the returned `prompt_path`. Monitor by checking every 5 minutes until 60 minutes have passed. Then, and only then, kill it and retry.
3. Present that report and the latest planning report to the user and **await user instructions before taking any further action.**

## 10) Build test plan (subagent-owned)

Now that the implementation plan has passed the plan load-bearing gate and the plan-hardening loop and is finalized, dispatch a subagent to reconcile the testing strategy against the plan and produce the concrete test plan, starting from high-value existing automated checks where they exist and adding new tests where coverage is missing.

Immediately before dispatch, prepare the `test-plan` phase via the phase wrapper using template `<skill-directory>/subagents/prompt-test-plan.md`, `--set IMPLEMENTATION_PLAN_PATH={IMPLEMENTATION_PLAN_PATH}`, `--set WORKTREE_PATH={WORKTREE_PATH}`, `--set-file USER_INTENT={USER_INTENT_PATH}`, `--set-file TESTING_STRATEGY={TESTING_STRATEGY_PATH}`, `--require-nonempty-tag user_intent`, `--require-nonempty-tag testing_strategy`, `--ignore-tag-for-placeholders user_intent`, and `--ignore-tag-for-placeholders testing_strategy`. If `{PLAN_LOAD_BEARING_LEDGER_PATH}` exists, also pass `--set-file PLAN_LOAD_BEARING_LEDGER={PLAN_LOAD_BEARING_LEDGER_PATH}`, `--require-nonempty-tag plan_load_bearing_ledger`, and `--ignore-tag-for-placeholders plan_load_bearing_ledger`.

Monitor by checking every 5 minutes until 60 minutes have passed. Then, and only then, kill it and retry.

When the subagent returns:

1. Update `{TEST_PLAN_PATH}` from `## Test plan path` in the latest test-plan report.
2. Confirm the test-plan report includes a `## Validation approval scope` section copied from the final section of the test plan. If it is missing, close the completed test-plan subagent and rerun the same `test-plan` phase wrapper command with the correction that the report and plan must include the final approval-scope section; do not ask the user to approve an incomplete report.
3. Present any `## Strategy changes requiring user approval` section and the `## Validation approval scope` section to the user verbatim, then ask for explicit approval of the current concrete test plan and validation approval scope.
4. If the user requests changes or redirects the approach, run the user-intent freshness check, close that completed test-plan subagent and clear any saved handle or `session_id` for it, then rerun the same `test-plan` phase wrapper command immediately before redispatching. Monitor by checking every 5 minutes until 60 minutes have passed. Then, and only then, kill it and retry. Update `{TEST_PLAN_PATH}` from the latest test-plan report and present the updated approval sections. Repeat until the user explicitly approves the current test plan and validation approval scope.
5. Do not proceed until the user explicitly approves the concrete test plan and its `## Validation approval scope`. Silence, implied approval, or the subagent's own recommendation does not count as agreement. Once approved, the validation approval scope carries forward for the duration of this Trycycle run. Later phases must not stop again for actions already covered by the approved categories, risk level, environment, and cost profile; they may ask again only for newly discovered actions materially outside that approved scope.
6. Run the workspace hygiene gate checks, verify the latest commit hash plus changed-file list match the test-plan subagent's report, and verify the test plan file exists at `{TEST_PLAN_PATH}`.
7. Close the completed test-plan subagent for the approved report and clear any saved handle or `session_id` for it.

## 11) Execute with trycycle-executing (subagent-owned)

Code implementation must be done by a new, dedicated subagent.

Before dispatching the implementation subagent, rebase onto the latest base branch to incorporate any changes merged by other agents during planning:

```bash
git -C {WORKTREE_PATH} fetch origin main
git -C {WORKTREE_PATH} rebase origin/main
```

If the rebase has conflicts, stop and present them to the user.

Spawn a fresh implementation subagent and give it the final excellent plan.

The implementation subagent stays in execute mode until the plan is complete, the work has gone through red/green/refactor cycles as needed, all required automated tests are passing for legitimate reasons, and the acceptance artifacts required by the test plan have been produced. Failed checks or acceptance-artifact gaps mean keep improving the code, tests, and evidence unless there is a genuine blocker. Do not accept weakened or deleted valid tests as a shortcut to green.

Immediately before dispatch, prepare the `executing` phase via the phase wrapper using template `<skill-directory>/subagents/prompt-executing.md`, `--set IMPLEMENTATION_PLAN_PATH={IMPLEMENTATION_PLAN_PATH}`, `--set TEST_PLAN_PATH={TEST_PLAN_PATH}`, `--set WORKTREE_PATH={WORKTREE_PATH}`, `--set-file USER_INTENT={USER_INTENT_PATH}`, and `--ignore-tag-for-placeholders user_intent`, then dispatch the implementation subagent with the returned `prompt_path`. Start a phase prompt paths temp file if needed, and append the returned `prompt_path`.

In fallback-runner mode, record the returned `dispatch.backend` as `{IMPLEMENTATION_BACKEND}` alongside the saved `session_id`.

Monitor by checking every 5 minutes until 180 minutes have passed. Then, and only then, kill it and retry.
If you kill and retry this implementation round, create a fresh implementation subagent or runner session and replace the saved implementation handle. In fallback-runner mode, also replace the saved `session_id` and `{IMPLEMENTATION_BACKEND}` with the fresh dispatch values.

Do not proceed to acceptance-artifact review until the implementation subagent has returned an implementation report. Start an implementation reports temp file if needed, save the report to a temp file immediately, append that path, and treat that saved file as the latest implementation report for the first acceptance-artifact review prompt.

After implementation completes, run the workspace hygiene gate checks and verify the latest commit hash plus changed-file list match the implementation subagent's report before launching acceptance-artifact review.

## 12) Acceptance-artifact and post-implementation review loop (up to 8 rounds by default)

After execution completes, start the verification loop. Every loop round begins with a post-execution load-bearing gate over the latest implementation report and acceptance artifacts. If that gate passes, continue to a fresh acceptance-artifact reviewer with no prior context. The acceptance-artifact reviewer receives the user intent, finalized test plan, latest implementation report, and produced artifacts. It must not rerun tests, recreate screenshots, launch services, regenerate files, or inspect implementation internals. Its only job is to decide whether the artifacts conclusively demonstrate that the user request was satisfied.

If the acceptance-artifact reviewer finds blocking gaps, treat them exactly like failed tests: skip the code-review gate for that round and send the extracted observations back to the implementation subagent. If the acceptance-artifact reviewer passes, then run the code-review gate with no prior context: a fresh assignment subagent carves the implementation's surface into review territories, fresh territory code reviewers go deep on those territories in parallel against the finalized implementation plan and finalized test plan, and a fresh review-merge subagent verifies and merges their observations into the single review result.

Create an empty temp file for `{REVIEW_LOOP_HISTORY}` before starting the first verification round, then append the implementation subagent's initial implementation report to it.

At the start of every verification round, run the post-execution load-bearing gate:
1. Run the full load-bearing gate helper with `{LOAD_BEARING_SCOPE}` set to `post-execution`.
2. If the self-consistent evaluator verdict is `VERIFIED` or `NO_TARGETS`, set `{POST_EXECUTION_LOAD_BEARING_LEDGER_PATH}` to `{LOAD_BEARING_LEDGER_PATH}`, append the evaluator report and ledger path to `{REVIEW_LOOP_HISTORY}`, and continue to acceptance-artifact review for this same verification round.
3. If the self-consistent evaluator verdict is `FALSIFIED` or `INCONCLUSIVE`, use the evaluator's normalized observations as the fix-loop input for this verification round. Append the evaluator report and normalized observations to `{REVIEW_LOOP_HISTORY}` as a completed verification round of type `load-bearing-post-execution`. Do not dispatch acceptance-artifact review or code review for this round. If the evaluator's required follow-up identifies a plan, test-plan, acceptance-evidence, or sequencing cause rather than direct implementation followthrough, treat plan reconsideration as due before the next fix round.
4. If the self-consistent evaluator verdict is `NEEDS_USER_APPROVAL`, present the blocked approval report to the user and await instructions. After the concrete test plan has been approved, this verdict is valid only for actions materially outside the approved validation scope; covered actions must not trigger another approval stop.

When the post-execution load-bearing gate passes for a round, run the acceptance-artifact review gate:
1. Immediately before dispatch, prepare the `acceptance-artifact-review` phase via the phase wrapper using template `<skill-directory>/subagents/prompt-acceptance-artifact-review.md`, `--set WORKTREE_PATH={WORKTREE_PATH}`, `--set TEST_PLAN_PATH={TEST_PLAN_PATH}`, `--set-file LATEST_IMPLEMENTATION_REPORT=<latest-implementation-report-temp-file>`, `--set-file USER_INTENT={USER_INTENT_PATH}`, `--ignore-tag-for-placeholders latest_implementation_report`, and `--ignore-tag-for-placeholders user_intent`, then dispatch a fresh acceptance-artifact review subagent with the returned `prompt_path`. Append the returned `prompt_path` to the phase prompt paths temp file.
2. Monitor by checking every 5 minutes until 60 minutes have passed. Then, and only then, kill it and retry.
3. Save the acceptance-artifact reviewer's raw stdout to a temp file immediately and extract a structured review-observations artifact from it using the extractor command below.
4. Close that completed acceptance-artifact review subagent and clear any saved handle or `session_id` for it.
5. If the extracted artifact reports `blocking_issue_count > 0`, use that acceptance-artifact review output as the fix-loop input for this verification round. Do not dispatch a code-review subagent for this round.
6. If the extracted artifact reports `blocking_issue_count: 0`, continue to code review for this same verification round.

When acceptance-artifact review passes for a round, run the code-review gate:
1. Prepare the `post-implementation-assign` phase via the phase wrapper using template `<skill-directory>/subagents/prompt-post-impl-assign.md`, `--set REVIEWER_COUNT=5`, `--set WORKTREE_PATH={WORKTREE_PATH}`, `--set IMPLEMENTATION_PLAN_PATH={IMPLEMENTATION_PLAN_PATH}`, `--set TEST_PLAN_PATH={TEST_PLAN_PATH}`, `--set-file USER_INTENT={USER_INTENT_PATH}`, `--require-nonempty-tag user_intent`, and `--ignore-tag-for-placeholders user_intent`, then dispatch a fresh assignment subagent with the returned `prompt_path`. Append the returned `prompt_path` to the phase prompt paths temp file. Monitor by checking every 5 minutes until 60 minutes have passed. Then, and only then, kill it and retry.
2. Save the assignment report to a temp file. Check only its final lines: the report must end with `COVERAGE: COMPLETE` followed by `TERRITORY_COUNT: <n>` where `<n>` is an integer from 1 to 5. If the check fails, dispatch one fresh assignment subagent; if the second report also fails the check, stop and surface both assignment reports to the user. Do not read the rest of the assignment report; only subagents interpret it. Close each completed assignment subagent and clear any saved handle or `session_id` for it.
3. Dispatch `<n>` fresh territory code reviewers in parallel, one per territory number from 1 through `<n>`. For each, prepare the `post-implementation-review` phase via the phase wrapper using template `<skill-directory>/subagents/prompt-post-impl-review.md`, `--set TERRITORY_NUMBER=<territory-number>`, `--set WORKTREE_PATH={WORKTREE_PATH}`, `--set IMPLEMENTATION_PLAN_PATH={IMPLEMENTATION_PLAN_PATH}`, `--set TEST_PLAN_PATH={TEST_PLAN_PATH}`, `--set-file ASSIGNMENT_REPORT=<assignment-report-temp-file>`, `--set-file LATEST_IMPLEMENTATION_REPORT=<latest-implementation-report-temp-file>`, `--set-file USER_INTENT={USER_INTENT_PATH}`, `--require-nonempty-tag assignment_report`, `--ignore-tag-for-placeholders assignment_report`, `--ignore-tag-for-placeholders latest_implementation_report`, and `--ignore-tag-for-placeholders user_intent`, then dispatch with the returned `prompt_path` and append that `prompt_path` to the phase prompt paths temp file. Monitor every territory reviewer by checking every 5 minutes until 60 minutes have passed. Then, and only then, kill that reviewer and retry it. Save each reviewer reply to its own temp file without reading it, write a newline-delimited list of those absolute paths to a territory-reports list temp file, then close each completed territory reviewer and clear its saved handle or `session_id`.
4. Prepare the `post-implementation-merge` phase via the phase wrapper using template `<skill-directory>/subagents/prompt-post-impl-merge.md`, `--set WORKTREE_PATH={WORKTREE_PATH}`, `--set IMPLEMENTATION_PLAN_PATH={IMPLEMENTATION_PLAN_PATH}`, `--set TEST_PLAN_PATH={TEST_PLAN_PATH}`, `--set-file ASSIGNMENT_REPORT=<assignment-report-temp-file>`, `--set-file TERRITORY_REVIEW_REPORTS=<territory-reports-list-temp-file>`, `--set-file USER_INTENT={USER_INTENT_PATH}`, `--require-nonempty-tag assignment_report`, `--require-nonempty-tag territory_review_reports`, `--ignore-tag-for-placeholders assignment_report`, `--ignore-tag-for-placeholders territory_review_reports`, and `--ignore-tag-for-placeholders user_intent`, then dispatch a fresh review-merge subagent with the returned `prompt_path`. Append the returned `prompt_path` to the phase prompt paths temp file. Monitor by checking every 5 minutes until 60 minutes have passed. Then, and only then, kill it and retry.
5. Save the review-merge subagent's raw stdout to a temp file immediately and extract a structured review-observations artifact from it using the extractor command below.
6. Use the merged review output as the code-review output and the fix-loop input for this verification round.
7. Close the completed review-merge subagent and clear any saved handle or `session_id` for it.

After every acceptance-artifact review or code-review output, extract a structured review-observations artifact:

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

Start a loop outputs temp file if needed. Append each acceptance-artifact review, code-review, or post-execution load-bearing evaluator reply path and extracted review-observations path to it.

After extraction succeeds, append the completed verification round number, the review type (`load-bearing-post-execution`, `acceptance-artifact`, or `code-review`), the reviewer's raw stdout, and the normalized review-observations JSON to `{REVIEW_LOOP_HISTORY}`.

When blocking issues remain after a verification round, first check whether the loop has reached its stop point. The default stop point is 8 completed verification rounds, but the user can override that like any other instruction.

Before either dispatching another fix round or running nonconvergence review, check whether plan reconsideration is due. Plan reconsideration is due when blocking issues remain and either:
- The completed verification round is even-numbered and greater than 2: the 4th, 6th, 8th, and every 2 rounds thereafter if the user overrides the stop point.
- The loop has reached its configured stop point. This means nonconvergence review always runs after a plan-reconsideration checkpoint when the loop stops with blockers, even if the user chose a stop point that would not otherwise trigger the even-round cadence.
- The latest post-execution load-bearing evaluator required follow-up identifies a plan, test-plan, acceptance-evidence, or sequencing cause that should be resolved before another implementation fix round.

If plan reconsideration is due, run this checkpoint before the next action:
- The latest blocking observations may come from post-execution load-bearing validation, acceptance-artifact review, or code review. All three use the same normalized review-observations schema, and all are passed through the existing `{POST_IMPLEMENTATION_REVIEW_OBSERVATIONS_JSON}` binding for plan reconsideration.
- Prepare the `planning-reconsider` phase via the phase wrapper using template `<skill-directory>/subagents/prompt-planning-reconsider.md`, `--set WORKTREE_PATH={WORKTREE_PATH}`, `--set IMPLEMENTATION_PLAN_PATH={IMPLEMENTATION_PLAN_PATH}`, `--set TEST_PLAN_PATH={TEST_PLAN_PATH}`, `--set REVIEW_ROUND_NUMBER=<completed-verification-round-number>`, `--set-file POST_IMPLEMENTATION_REVIEW_OBSERVATIONS_JSON=<review-observations-temp-file>`, `--set-file REVIEW_LOOP_HISTORY=<review-loop-history-temp-file>`, `--set-file USER_INTENT={USER_INTENT_PATH}`, `--require-nonempty-tag user_intent`, `--require-nonempty-tag review_loop_history`, `--ignore-tag-for-placeholders user_intent`, `--ignore-tag-for-placeholders post_implementation_review_observations_json`, and `--ignore-tag-for-placeholders review_loop_history`, then dispatch a fresh planning subagent with the returned `prompt_path`. Append the returned `prompt_path` to the phase prompt paths temp file.
- Monitor by checking every 5 minutes until 60 minutes have passed. Then, and only then, kill it and retry.
- Wait for either a report containing `## Plan reconsideration verdict`, `## Implementation plan path`, `## Test plan path`, `## Commit`, and `## Changed files`, or a report beginning with `USER DECISION REQUIRED:`.
- If the planning subagent returns `USER DECISION REQUIRED:`, present that question to the user, run the user-intent freshness check, send the user's answer back to that active planning subagent, and wait again for either a plan-reconsideration report or another `USER DECISION REQUIRED:` report. Monitor by checking every 5 minutes until 60 minutes have passed. Then, and only then, kill it and retry.
- Update `{IMPLEMENTATION_PLAN_PATH}` from `## Implementation plan path` and `{TEST_PLAN_PATH}` from `## Test plan path` in the latest plan-reconsideration report.
- If the plan-reconsideration report or updated test plan broadens the previously approved `## Validation approval scope`, present the broadened scope to the user for explicit approval before continuing. Later phases may rely only on the latest explicitly approved validation scope.
- Run the workspace hygiene gate checks and verify the latest commit hash plus changed-file list match the planning subagent's report.
- Save the plan-reconsideration report to a temp file and append that path to the loop outputs temp file.
- Append the plan-reconsideration report itself to `{REVIEW_LOOP_HISTORY}` under a clear plan-reconsideration heading so future plan-reconsideration checkpoints receive prior analyses. This history is for planning and final nonconvergence analysis; do not add it to executor or reviewer prompts.
- Close that planning subagent and clear any saved handle or `session_id` for it.

Stop when either condition is met:
1. The extracted review-observations artifact reports `blocking_issue_count: 0`.
2. The configured stop point has been reached. By default, this is 8 completed verification rounds.

Evaluate the stop condition only after the round's final review-observations artifact: the load-bearing artifact if post-execution load-bearing blocked before acceptance, the acceptance-artifact artifact if acceptance blocked and code review was skipped, or the code-review artifact if acceptance passed and code review ran. Do not finish the loop merely because post-execution load-bearing or acceptance-artifact review passed; code review must also pass for the same latest implementation report.

If the latest extracted review-observations artifact still reports `blocking_issue_count > 0` after the configured stop point:
1. Stop looping. Do not dispatch another implementation fix round.
2. Prepare the `nonconvergence-review` phase via the phase wrapper using template `<skill-directory>/subagents/prompt-nonconvergence-review.md`, `--set TRYCYCLE_SKILL_PATH=<skill-directory>/SKILL.md`, `--set NONCONVERGENCE_CONTEXT="Acceptance-artifact and post-implementation review loop stopped after <completed-verification-round-number> verification rounds while blockers remained."`, `--set WORKTREE_PATH={WORKTREE_PATH}`, `--set IMPLEMENTATION_PLAN_PATH={IMPLEMENTATION_PLAN_PATH}`, `--set TEST_PLAN_PATH={TEST_PLAN_PATH}`, `--set-file PHASE_PROMPT_PATHS=<phase-prompt-paths-temp-file>`, `--set-file LOOP_OUTPUT_PATHS=<loop-outputs-temp-file>`, `--set-file IMPLEMENTATION_REPORT_PATHS=<implementation-reports-temp-file>`, `--set-file USER_INTENT={USER_INTENT_PATH}`, and `--ignore-tag-for-placeholders user_intent`, then dispatch a subagent with the returned `prompt_path`. Monitor by checking every 5 minutes until 60 minutes have passed. Then, and only then, kill it and retry.
3. Present that report and the latest review output to the user and await user instructions.

If blockers remain and the configured stop point has not been reached, continue with the fix round:
1. Prepare the `executing` phase again via the phase wrapper using template `<skill-directory>/subagents/prompt-executing.md`, `--set IMPLEMENTATION_PLAN_PATH={IMPLEMENTATION_PLAN_PATH}`, `--set TEST_PLAN_PATH={TEST_PLAN_PATH}`, `--set WORKTREE_PATH={WORKTREE_PATH}`, `--set-file USER_INTENT={USER_INTENT_PATH}`, `--ignore-tag-for-placeholders user_intent`, and the latest blocking observation file:
   - If the latest blocking observations came from acceptance-artifact review, pass `--set-file ACCEPTANCE_ARTIFACT_REVIEW_OBSERVATIONS_JSON=<review-observations-temp-file>` and `--ignore-tag-for-placeholders acceptance_artifact_review_observations_json`.
   - If the latest blocking observations came from code review, pass `--set-file POST_IMPLEMENTATION_REVIEW_OBSERVATIONS_JSON=<review-observations-temp-file>` and `--ignore-tag-for-placeholders post_implementation_review_observations_json`.
   - If the latest blocking observations came from post-execution load-bearing validation, pass `--set-file LOAD_BEARING_REVIEW_OBSERVATIONS_JSON=<review-observations-temp-file>` and `--ignore-tag-for-placeholders load_bearing_review_observations_json`.
   Append the returned `prompt_path` to the phase prompt paths temp file. The executing prompt must treat only `critical` and `major` observations as critical issues and required fix targets; `minor` and `nit` observations are not required fix targets.
2. In native mode, resume the same implementation subagent and send the exact returned `prompt_path` contents verbatim. In fallback-runner mode, resume the implementation session through `python3 <skill-directory>/orchestrator/subagent_runner.py resume` using the saved `session_id`, `--backend {IMPLEMENTATION_BACKEND}`, and the wrapper-prepared `prompt_path`.
3. Monitor by checking every 5 minutes until 180 minutes have passed. Then, and only then, kill it and retry.
4. If you kill and retry this implementation round, create a fresh implementation subagent or runner session and replace the saved implementation handle. In fallback-runner mode, also replace the saved `session_id` and `{IMPLEMENTATION_BACKEND}` with the fresh dispatch values. Keep any paths already appended for the killed attempt; they are useful evidence if nonconvergence analysis is needed.

After each implementation-subagent fix round, save the returned implementation report to a temp file, append that path to the implementation reports temp file, treat that saved file as the latest implementation report for the next post-execution load-bearing and acceptance-artifact review prompts, append the report to `{REVIEW_LOOP_HISTORY}`, then run the workspace hygiene gate checks and verify the latest commit hash plus changed-file list match the implementation subagent's report before starting the next verification round. Every new verification round starts with the post-execution load-bearing gate; do not dispatch another code-review subagent until post-execution load-bearing and acceptance-artifact review both pass for the latest implementation report.

## 13) Finish

Once the post-execution load-bearing, acceptance-artifact, and post-implementation review loop passes (`blocking_issue_count: 0`):

Clean up temporary artifacts created during the loop (for example plan scratch files and temp notes), then run:
- `git -C {WORKTREE_PATH} status --short`
- `git -C {WORKTREE_PATH} rev-parse --short HEAD`
- `git -C {WORKTREE_PATH} diff --name-only main...HEAD`

If the implementation subagent is still open, close it and clear its saved handle or `session_id` before handing off to finishing.

Finally, in one paragraph, briefly describe what was built/accomplished/changed/fixed. Then Report the process to the user using concrete facts and returned artifacts: how many plan load-bearing rounds, how many plan-hardening rounds, how many post-execution load-bearing rounds, how many acceptance-artifact review rounds, how many code-review rounds, the current `HEAD`, the changed-file list, the implementation subagent's latest summary, verification results, acceptance artifacts, and any reviewer-reported residual issues.

Then read and follow `<skill-directory>/subskills/trycycle-finishing/SKILL.md` to present the user with options for integrating the implementation workspace (merge, PR, etc.).
