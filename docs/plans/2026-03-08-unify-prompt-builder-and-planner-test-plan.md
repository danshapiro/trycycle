# Unified Prompt Builder And Planner Test Plan

The approved heavy strategy still holds after reconciling it with the implementation plan. The plan narrows the architecture to one runtime prompt builder, one planning template, one execution template, fresh planning agents only after failed plan review, and verification via render probes plus disposable clean smoke repos under `/tmp`; those are all within the already approved heavy scope and do not require new user approval.

## Harness requirements

### 1. Prompt builder CLI harness
- **What it does:** Runs `python3 orchestrator/prompt_builder/build.py` directly against checked-in templates and temporary templates.
- **What it exposes:** Rendered prompt stdout, prefixed stderr on failure, exit codes, and wall-clock render duration.
- **Estimated complexity to build:** Low. Reuses the production CLI with small temp files under `/tmp`.
- **Which tests depend on it:** 2, 3, 4, 6, 8, 9, 10, 11, 12.

### 2. Render probe and output-capture harness
- **What it does:** Creates transcript/review temp files, renders every prompt variant the orchestrator dispatches, and inspects the resulting text with `rg`.
- **What it exposes:** Presence or absence of review-only XML blocks, conditional task wording, unresolved placeholder markers, and stale split-template references.
- **Estimated complexity to build:** Low. Shell commands only.
- **Which tests depend on it:** 1, 2, 3, 4, 6, 7, 8, 10, 11, 12.

### 3. Clean smoke repo harness
- **What it does:** Creates disposable git repos outside this repo, installs or points them at the worktree copy of trycycle, and runs trivial end-to-end tasks so the skill operates without nearby repo context.
- **What it exposes:** Real subagent dispatch, worktree creation, plan/test-plan artifact generation, implementation artifacts, review-loop behavior, and final report artifacts.
- **Estimated complexity to build:** Medium. Requires repo bootstrap, cleanup, and at least two smoke runs in separate `/tmp` directories.
- **Which tests depend on it:** 1, 4, 5.

### 4. Reference comparison harness
- **What it does:** Renders equivalent inputs through the unified worktree and compares the results semantically to the intent expressed by `/home/user/code/trycycle/.worktrees/fresh-impl-after-review-failure` and `/home/user/code/trycycle/.worktrees/python-prompt-builder`.
- **What it exposes:** Whether the unified implementation preserved the intended initial vs revision/fix behavior without reintroducing split planning prompts or manual prompt reconstruction.
- **Estimated complexity to build:** Medium. Requires temp fixtures and careful semantic comparison rather than byte-for-byte equality.
- **Which tests depend on it:** 9, 10, 11.

### 5. Worktree hygiene inspection harness
- **What it does:** Runs the branch/status/head/diff checks that `SKILL.md` requires before and after major phases and after each subagent completion.
- **What it exposes:** Branch identity, cleanliness, latest short hash, and changed-file list alignment with subagent reports.
- **Estimated complexity to build:** Low.
- **Which tests depend on it:** 1, 4, 5, 7.

## Test plan

1. **Name:** Trivial trycycle run in a clean repo completes with rendered prompts and no nearby-repo leakage
   - **Type:** scenario
   - **Harness:** Clean smoke repo harness plus worktree hygiene inspection harness
   - **Preconditions:** Create a disposable repo under `/tmp` with a minimal README or text file, no uncommitted changes, and the repo version of trycycle available from `/home/user/code/trycycle/.worktrees/unify-prompt-builder-and-planner`. Start from a clean trycycle worktree.
   - **Actions:** Invoke trycycle on a trivial request in that clean repo; let it run through planning, plan review, test-plan generation, implementation, and post-implementation review; capture the final artifacts and worktree hygiene outputs.
   - **Expected outcome:** Per the approved heavy strategy in the transcript and the implementation plan architecture/Task 3, trycycle should operate successfully from a clean external repo, create an isolated implementation worktree, produce a plan file and test-plan file, dispatch subagents using rendered prompts rather than template-name reconstruction, and finish with hygiene outputs whose changed-file list matches the final subagent report.
   - **Interactions:** External clean repo bootstrap, trycycle worktree creation, transcript helper, prompt builder CLI, planning reviewer, test-plan builder, implementation subagent, post-implementation reviewer.

2. **Name:** Failed plan review path respawns a fresh planning agent and renders the revision-only prompt content
   - **Type:** scenario
   - **Harness:** Render probe and output-capture harness plus prompt builder CLI harness
   - **Preconditions:** The unified worktree contains the new prompt builder and updated `SKILL.md`; temp transcript JSON and plan-review findings files exist under `/tmp`.
   - **Actions:** Render `subagents/prompt-planning.md` once with only `USER_REQUEST_TRANSCRIPT` and `WORKTREE_PATH`, then again with `USER_REQUEST_TRANSCRIPT`, `WORKTREE_PATH`, `IMPLEMENTATION_PLAN_PATH`, and `PLAN_REVIEW_FINDINGS_VERBATIM`; inspect the rendered outputs and the corresponding `SKILL.md` Step 6/7 instructions.
   - **Expected outcome:** Per implementation plan Task 2 Step 1, Task 3 Step 2, and the planning reset reference in `/home/user/code/trycycle/.worktrees/fresh-impl-after-review-failure/SKILL.md` plus its split planning prompts, the initial render must omit the current-plan and review-findings blocks and instruct the agent to produce a complete plan, while the revision render must include both blocks, switch to revise-the-current-plan wording, and `SKILL.md` must instruct the orchestrator to spawn a fresh planning subagent after a failed review instead of resuming the old one.
   - **Interactions:** Prompt builder parser, planning template, orchestrator Step 6/7 loop text, plan-review output capture.

3. **Name:** Initial implementation round stays branch-free while fix rounds inject reviewer findings into the same execution template
   - **Type:** scenario
   - **Harness:** Render probe and output-capture harness plus prompt builder CLI harness
   - **Preconditions:** Temp plan path, test-plan path, and post-implementation review findings file exist under `/tmp`.
   - **Actions:** Render `subagents/prompt-executing.md` once with `IMPLEMENTATION_PLAN_PATH`, `TEST_PLAN_PATH`, and `WORKTREE_PATH`, then again with those same bindings plus `POST_IMPLEMENTATION_REVIEW_FINDINGS_VERBATIM`; inspect both outputs and the corresponding `SKILL.md` Step 9/10 instructions.
   - **Expected outcome:** Per implementation plan Task 2 Step 2, Task 3 Step 3, and the reference behavior in `/home/user/code/trycycle/.worktrees/python-prompt-builder/subagents/prompt-executing.md`, the initial render must omit the post-review findings block and any fix-round-only instruction, while the fix render must include the verbatim findings block and direct the existing implementation agent to fix against the attached review report. `SKILL.md` must continue to keep implementation agents persistent across fix rounds.
   - **Interactions:** Prompt builder parser, execution template, post-implementation review output capture, orchestrator Step 9/10 loop text.

4. **Name:** Review-loop smoke run in a second clean repo preserves persistent implementation agents while exercising deterministic revision and fix prompts
   - **Type:** scenario
   - **Harness:** Clean smoke repo harness plus render probe and output-capture harness plus worktree hygiene inspection harness
   - **Preconditions:** Create a second disposable repo under `/tmp` separate from Test 1. Have temp review findings files ready so the planning-revision and execution-fix renders can be exercised deterministically even if the organic smoke run does not naturally fail review.
   - **Actions:** Run a second trivial trycycle smoke task in the clean repo. Independently render the planning revision prompt and execution fix prompt with representative review findings, then inspect the smoke-run artifacts and `SKILL.md` loop instructions together.
   - **Expected outcome:** Per the approved heavy strategy, the implementation plan Task 3, and the transcript instruction to test in clean folders, the repo should prove both that trycycle still works end-to-end in a clean external repo and that the two review-driven prompt branches are wired correctly without relying on nondeterministic reviewer failures. Planning must be fresh across failed plan reviews; implementation must remain persistent across failed code reviews.
   - **Interactions:** External clean repo bootstrap, trycycle worktree creation, smoke-run artifacts, planning/execution revision renders, hygiene checks.

5. **Name:** Human-facing and maintainer-facing documentation match the new runtime-rendering and fresh-planner behavior
   - **Type:** scenario
   - **Harness:** Render probe and output-capture harness
   - **Preconditions:** The worktree includes the updated `README.md` and `maintenance/skill-instructions/trycycle-planning.txt`.
   - **Actions:** Read `README.md` and `maintenance/skill-instructions/trycycle-planning.txt` after the implementation lands; compare their behavior summaries against the implemented `SKILL.md`.
   - **Expected outcome:** Per implementation plan Task 4 and the earlier branch intention captured in `/home/user/code/trycycle/.worktrees/fresh-impl-after-review-failure/README.md` and `maintenance/skill-instructions/trycycle-planning.txt`, the README must say reviewers are fresh and failed plan-review rounds respawn a fresh planning agent, while the maintenance note must state that failed plan review causes a fresh planning subagent rather than resuming the old one.
   - **Interactions:** User-facing docs, maintainer docs, orchestrator skill text.

6. **Name:** Builder CLI accepts scalar and multiline bindings and renders every dispatch template the orchestrator uses
   - **Type:** integration
   - **Harness:** Prompt builder CLI harness plus render probe and output-capture harness
   - **Preconditions:** Temp transcript, plan-review findings, and post-implementation review findings files exist. The new builder script exists at `orchestrator/prompt_builder/build.py`.
   - **Actions:** Run `python3 -m py_compile orchestrator/prompt_builder/build.py`, then render each template used by `SKILL.md`: `prompt-test-strategy.md`, `prompt-planning.md` initial, `prompt-planning.md` revision, `prompt-plan-review.md`, `prompt-test-plan.md`, `prompt-executing.md` initial, `prompt-executing.md` fix round, and `prompt-post-impl-review.md`.
   - **Expected outcome:** Per implementation plan Task 1 Step 2, Task 2 Step 3, and Task 3 Step 3, the builder must compile cleanly, accept `--set` for short scalar values and `--set-file` for multiline values, and successfully render every prompt the orchestrator dispatches using the new runtime-rendering model.
   - **Interactions:** Builder CLI, all subagent templates, transcript temp files, reviewer-output temp files.

7. **Name:** `SKILL.md` dispatch sites all render prompts before dispatch and use the correct binding channel for each placeholder kind
   - **Type:** integration
   - **Harness:** Render probe and output-capture harness plus worktree hygiene inspection harness
   - **Preconditions:** Implementation changes to `SKILL.md` are present.
   - **Actions:** Inspect `SKILL.md` dispatch instructions for Steps 3, 6, 7, 8, 9, and 10. Verify each step names the builder command, uses `--set` for scalar paths, uses `--set-file` for transcripts and review outputs, saves multiline command/subagent stdout to temp files before binding, and says builder stdout is the exact prompt to send.
   - **Expected outcome:** Per implementation plan Task 3 Step 1 and Step 3, `SKILL.md` must replace the old "pass the prompt template together with the parameters it names" model with explicit render-time instructions and must do so at every prompt-dispatch site listed in the plan.
   - **Interactions:** Orchestrator instructions, transcript helper outputs, temp-file workflow, prompt builder CLI contract.

8. **Name:** Transcript placeholder integration is rebuilt immediately before each rendered prompt that consumes it
   - **Type:** integration
   - **Harness:** Render probe and output-capture harness
   - **Preconditions:** `SKILL.md` and the existing transcript helper scripts are present.
   - **Actions:** Inspect the transcript-helper guidance in `SKILL.md` and each transcript-consuming dispatch step. Verify that each rendered prompt path that uses `{USER_REQUEST_TRANSCRIPT}`, `{INITIAL_REQUEST_AND_SUBSEQUENT_CONVERSATION}`, or `{FULL_CONVERSATION_VERBATIM}` rebuilds the transcript immediately before rendering and binds the resulting multiline value via temp file plus `--set-file`.
   - **Expected outcome:** Per the existing transcript-helper contract in the current worktree `SKILL.md`, implementation plan Task 3 Step 3, and the prompt-builder reference `SKILL.md` in `/home/user/code/trycycle/.worktrees/python-prompt-builder`, transcript values must be regenerated immediately before each relevant render so the builder consumes current conversation state rather than stale session text.
   - **Interactions:** `orchestrator/user-request-transcript/build.py`, `mark_with_canary.py`, `SKILL.md`, prompt builder binding rules.

9. **Name:** Unified planning template preserves the semantic behavior of the split planning prompts from the fresh-planner reference branch
   - **Type:** differential
   - **Harness:** Reference comparison harness plus prompt builder CLI harness
   - **Preconditions:** The unified worktree and `/home/user/code/trycycle/.worktrees/fresh-impl-after-review-failure` are both readable. Shared temp transcript and review-findings fixtures exist.
   - **Actions:** Render the unified `subagents/prompt-planning.md` in initial and revision modes. Read `/home/user/code/trycycle/.worktrees/fresh-impl-after-review-failure/subagents/prompt-planning-initial.md` and `prompt-planning-revision.md` with the same semantic inputs and compare the resulting sections, required blocks, and task wording.
   - **Expected outcome:** Per implementation plan Task 2 Step 1 and the split-prompt reference branch, the unified initial render must preserve the initial prompt’s semantics, and the unified revision render must preserve the revision prompt’s semantics, while eliminating the need for separate planning prompt files.
   - **Interactions:** Prompt builder, unified planning template, split planning reference files.

10. **Name:** Unified execution template preserves the semantic behavior of the prompt-builder reference branch for both initial and fix rounds
   - **Type:** differential
   - **Harness:** Reference comparison harness plus prompt builder CLI harness
   - **Preconditions:** The unified worktree and `/home/user/code/trycycle/.worktrees/python-prompt-builder` are both readable. Shared temp plan/test-plan/review fixtures exist.
   - **Actions:** Render unified `subagents/prompt-executing.md` in initial and fix-round modes. Compare the rendered results semantically to `/home/user/code/trycycle/.worktrees/python-prompt-builder/subagents/prompt-executing.md` and its `SKILL.md` dispatch expectations.
   - **Expected outcome:** Per implementation plan Task 2 Step 2 and Task 3 Step 3, plus the prompt-builder reference branch, the unified template must preserve the reference branch’s behavior: one template, initial prompt branch-free, fix prompt includes the review block and fix-against-review instruction, and the orchestrator sends the rendered prompt verbatim.
   - **Interactions:** Prompt builder, unified execution template, prompt-builder reference branch, orchestrator Step 9/10 behavior.

11. **Name:** New builder behavior matches the prompt-builder reference for direct render probes and failure probes
   - **Type:** differential
   - **Harness:** Reference comparison harness plus prompt builder CLI harness
   - **Preconditions:** The unified worktree and `/home/user/code/trycycle/.worktrees/python-prompt-builder/orchestrator/prompt_builder/build.py` are both readable. Temp templates exist for success and failure probes.
   - **Actions:** Run the implementation plan’s direct builder probes in the unified worktree and compare the outcomes to the same probe expectations derived from the reference builder implementation.
   - **Expected outcome:** Per implementation plan Task 1 Steps 1 and 3 and the reference builder in `/home/user/code/trycycle/.worktrees/python-prompt-builder/orchestrator/prompt_builder/build.py`, the unified builder must render the success cases exactly, treat non-empty bindings as truthy, and fail with `prompt builder error: ...` on unresolved placeholders rather than silently leaving markers behind.
   - **Interactions:** Builder CLI parser, temp templates, success and failure output capture.

12. **Name:** Every rendered prompt is fully resolved and free of leftover control markers
   - **Type:** invariant
   - **Harness:** Render probe and output-capture harness plus prompt builder CLI harness
   - **Preconditions:** All prompt variants have been rendered successfully into temp output files.
   - **Actions:** Search each rendered output for unresolved `{[A-Z...]}` placeholders, `{{#if`, `{{else}}`, `{{/if}}`, and stale split-template names such as `prompt-planning-initial.md` and `prompt-planning-revision.md`.
   - **Expected outcome:** Per implementation plan Task 1 Step 1, Task 3 Step 4, and the transcript’s stated goal of having Python insert the right prompt content instead of relying on the LLM to reconstruct it, no rendered prompt may contain unresolved placeholders, control markers, or references to the deleted split planning prompt model.
   - **Interactions:** Builder output, all rendered prompt variants, stale-orchestration wording removal.

13. **Name:** Invalid builder inputs fail loudly and specifically instead of producing ambiguous output
   - **Type:** boundary
   - **Harness:** Prompt builder CLI harness
   - **Preconditions:** Temp templates and temp binding files exist for malformed binding, duplicate binding, unreadable file, missing placeholder, and unbalanced conditional cases.
   - **Actions:** Invoke the builder with each invalid case separately and capture exit code and stderr.
   - **Expected outcome:** Per implementation plan Task 1 Step 1, each invalid case must exit with code `1` and print a stderr line prefixed with `prompt builder error:`, covering malformed `NAME=VALUE`, duplicate bindings across `--set`/`--set-file`, unreadable `--set-file` paths, missing required placeholders, and unbalanced conditional blocks.
   - **Interactions:** Builder argument parser, file loading, tokenizer/parser, stderr handling.

14. **Name:** Render-all performance stays comfortably below a catastrophic-regression threshold
   - **Type:** boundary
   - **Harness:** Prompt builder CLI harness
   - **Preconditions:** All prompt render commands from Test 6 are available and the local machine is otherwise idle enough for a coarse timing check.
   - **Actions:** Time a batch that renders all prompt variants once in sequence.
   - **Expected outcome:** Per the approved strategy’s low-performance-risk guidance and the implementation plan’s small, dependency-free Python helper architecture, the full render batch should complete in under 5 seconds on the local machine. Anything slower indicates a severe regression in a code path that should be near-instant.
   - **Interactions:** Builder startup cost, template parsing, multiline file reads.

15. **Name:** Legacy prompt-handoff and persistent-planner wording is removed from the unified orchestrator
   - **Type:** regression
   - **Harness:** Render probe and output-capture harness
   - **Preconditions:** Implementation changes to `SKILL.md` have landed.
   - **Actions:** Run the exact stale-wording search from implementation plan Task 3 Step 4, and also search for the persistent-planner sentence from the current baseline `SKILL.md`.
   - **Expected outcome:** Per implementation plan Task 3 Step 4 and the transcript decision that planning agents, not implementation agents, become ephemeral across failed plan reviews, `SKILL.md` must have no remaining references to `prompt-planning-initial.md`, `prompt-planning-revision.md`, raw template-path-plus-parameter dispatch, inline manual revision/fix messages that belong in rendered templates, or the old "Planning subagents are persistent" behavior.
   - **Interactions:** `SKILL.md`, ripgrep-based stale-wording check, old orchestration model removal.

## Coverage summary

Covered action space:
- Initial planning dispatch from a unified planning template
- Planning revision dispatch after failed plan review, including fresh-planner lifecycle
- Initial implementation dispatch from a unified execution template
- Implementation fix-round dispatch with persistent implementation agent behavior
- Runtime prompt rendering for every prompt-dispatch site in `SKILL.md`
- Transcript-helper integration with render-time temp-file binding
- Direct builder compilation, success probes, failure probes, and catastrophic-regression timing
- Human-facing and maintainer-facing docs synchronization
- End-to-end trycycle behavior in two disposable clean repos outside this repo
- Removal of stale split-prompt and manual prompt-reconstruction wording

Explicit exclusions:
- No committed automated tests are added to this repo, because the repo instructions forbid it.
- No cross-platform OS validation is included beyond keeping the helper dependency-free Python and smoke-running locally; Windows compatibility remains an inference from architecture, not a live test here.
- No attempt is made to force a real reviewer to fail organically during smoke runs; deterministic revision/fix render probes cover those branches instead.

Risk carried by exclusions:
- Without committed automated coverage, future regressions depend on maintainers re-running these probes and smoke tests.
- Without live Windows validation, platform-specific shell-invocation mistakes could still slip through even if the Python helper itself is portable.
- Without nondeterministic real review failures, there is still a small residual risk in the exact operator loop behavior around failed reviews, mitigated here by direct prompt rendering checks plus `SKILL.md` loop inspection.
