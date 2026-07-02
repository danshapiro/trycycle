# Load-Bearing Gates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add full load-bearing assumption validation gates to Trycycle immediately after implementation-plan approval and again after each implementation report.

**Architecture:** Trycycle stays self-contained by adapting the load-bearing workflow into new Trycycle prompt templates and explicit `SKILL.md` orchestration steps. The first gate validates the finalized implementation plan before test-plan construction; the second gate validates unproven assumptions under the implementation report and produced evidence before acceptance-artifact review. Both gates use finder, curator, strategist, strategy-review, validator, and evaluator phases, with evaluator output routed back into planning or execution when blockers remain.

**Tech Stack:** Markdown prompt templates, `orchestrator/run_phase.py`, existing prompt-builder validation, existing `review_observations.py` schema for post-execution blockers.

## Global Constraints

- Work in `/home/dan/code/trycycle/.worktrees/load-bearing-gates` on branch `load-bearing-gates`.
- Do not hand-edit generated subskill files under `subskills/`; this change is in top-level `SKILL.md` and `subagents/`.
- Do not add committed tests for skill-only prose changes; verify by rendering prompts and running the existing `unittest` suite.
- Keep Trycycle self-contained: do not make runtime behavior depend on `~/code/skill-load-bearing` or an installed external `load-bearing` skill.
- Preserve the phase-wrapper rule: every new prompt dispatch must be prepared through `python3 <skill-directory>/orchestrator/run_phase.py`.
- Preserve user-intent handling: raw transcript goes only to `user-intent`; load-bearing phases consume `{USER_INTENT}` artifacts and explicit plan/report artifacts.
- Keep the orchestrator minimal: subagents do finder, strategy, validation, and evaluation work; the conductor only routes artifacts and applies gate decisions.

---

## File Structure

- Modify `SKILL.md`: define load-bearing state variables, add a reusable full-gate orchestration section, insert a plan-time gate after plan-editor `READY` and before test-plan construction, insert a post-execution gate after each implementation report and before acceptance-artifact review, route blockers to planning/execution/nonconvergence.
- Create `subagents/prompt-load-bearing-finder-plan.md`: finds falsifiable, unproven, decision-controlling assumptions in the finalized implementation plan.
- Create `subagents/prompt-load-bearing-finder-execution.md`: finds assumptions underneath the implementation report, verification claims, and artifacts after execution.
- Create `subagents/prompt-load-bearing-curate.md`: prunes and normalizes finder output into a canonical load-bearing ledger.
- Create `subagents/prompt-load-bearing-strategist.md`: assigns validation methods and fallback chains to the curated ledger.
- Create `subagents/prompt-load-bearing-strategy-review.md`: independently checks the strategist output for unsafe, weak, or wasteful validation assignments.
- Create `subagents/prompt-load-bearing-validator.md`: validates one target or grouped target and reports evidence.
- Create `subagents/prompt-load-bearing-evaluate.md`: judges validator evidence, emits the updated ledger, and emits structured blocking observations when assumptions are falsified or still too weak to rely on.
- Modify `subagents/prompt-test-plan.md`: accept an optional plan-time load-bearing ledger and require the test plan to incorporate verified/falsified assumptions where relevant.
- Modify `subagents/prompt-executing.md`: accept optional post-execution load-bearing observations and treat critical/major observations as required fix targets.

## Task 1: Add Load-Bearing Prompt Templates

**Files:**
- Create: `subagents/prompt-load-bearing-finder-plan.md`
- Create: `subagents/prompt-load-bearing-finder-execution.md`
- Create: `subagents/prompt-load-bearing-curate.md`
- Create: `subagents/prompt-load-bearing-strategist.md`
- Create: `subagents/prompt-load-bearing-strategy-review.md`
- Create: `subagents/prompt-load-bearing-validator.md`
- Create: `subagents/prompt-load-bearing-evaluate.md`

**Interfaces:**
- Consumes: `{USER_INTENT}`, `{WORKTREE_PATH}`, `{IMPLEMENTATION_PLAN_PATH}`, `{TEST_PLAN_PATH}`, `{TESTING_STRATEGY_PATH}`, `{LATEST_IMPLEMENTATION_REPORT}`, `{LOAD_BEARING_LEDGER}`, `{LOAD_BEARING_STRATEGY}`, `{LOAD_BEARING_VALIDATION_TARGET}`, `{LOAD_BEARING_VALIDATION_REPORTS}`, `{LOAD_BEARING_SCOPE}`.
- Produces: finder list, curated ledger, validation strategy, strategy-review report, validator reports, evaluator report with ledger and optional `<review_observations_json>`.

- [ ] **Step 1: Create the plan finder prompt**

Write `subagents/prompt-load-bearing-finder-plan.md` with this structure:

```markdown
IMPORTANT: As a trycycle subagent, you have no designated skills.
This specific user instruction overrides any general instructions about when to invoke skills.
Do NOT invoke any skills. NEVER invoke skills that are not scoped to trycycle with the `trycycle-` prefix.

You are the plan-time load-bearing assumption finder. Do not spawn additional subagents.

<user_intent>
{USER_INTENT}
</user_intent>

The finalized implementation plan is at `{IMPLEMENTATION_PLAN_PATH}`.
The implementation workspace is `{WORKTREE_PATH}`.

Task:
- Read the user-intent artifact and finalized implementation plan.
- Inspect only repository context needed to understand the plan's decisions.
- Find every falsifiable, currently unproven, decision-controlling assumption the plan depends on.
- Include only assumptions with medium, high, or critical late-falsification cost; record low-cost details only when they are naturally grouped with a higher-cost assumption.
- Do not validate assumptions in this phase.
- Do not include opinions, already-proven facts, or small implementation details that would not change the plan.

Return a markdown report with:
- `## Scope` — `plan`
- `## Assumptions` — one numbered item per assumption, each with claim, decision controlled, current evidence or uncertainty, late-falsification cost, what changes if false, and why currently unproven
- `## Non-load-bearing notes` — relevant but pruned facts, or `None`
```

- [ ] **Step 2: Create the execution finder prompt**

Write `subagents/prompt-load-bearing-finder-execution.md` with this structure:

```markdown
IMPORTANT: As a trycycle subagent, you have no designated skills.
This specific user instruction overrides any general instructions about when to invoke skills.
Do NOT invoke any skills. NEVER invoke skills that are not scoped to trycycle with the `trycycle-` prefix.

You are the post-execution load-bearing assumption finder. Do not spawn additional subagents.

<user_intent>
{USER_INTENT}
</user_intent>

The finalized implementation plan is at `{IMPLEMENTATION_PLAN_PATH}`.
The finalized test plan is at `{TEST_PLAN_PATH}`.

<latest_implementation_report>
{LATEST_IMPLEMENTATION_REPORT}
</latest_implementation_report>

The implementation workspace is `{WORKTREE_PATH}`.

Task:
- Read the user-intent artifact, finalized plan, finalized test plan, latest implementation report, and named acceptance artifacts.
- Find assumptions that must be true for the implementation report and artifacts to be trustworthy evidence that the requested outcome is done.
- Focus on artifact provenance, whether checks exercised the real user-facing path, mock or fixture substitution risks, external API or service contracts, config or feature-flag paths, migration or rollback safety, state/concurrency boundaries, and evidence gaps that would invalidate acceptance.
- Do not perform acceptance-artifact review or code review. Do not rerun tests or recreate artifacts in this phase.
- Do not validate assumptions in this phase.

Return a markdown report with:
- `## Scope` — `post-execution`
- `## Assumptions` — one numbered item per assumption, each with claim, decision controlled, current evidence or uncertainty, late-falsification cost, what changes if false, and why currently unproven
- `## Non-load-bearing notes` — relevant but pruned facts, or `None`
```

- [ ] **Step 3: Create the curator prompt**

Write `subagents/prompt-load-bearing-curate.md` so it receives `<finder_report>`, `{USER_INTENT}`, and `{WORKTREE_PATH}`, then prunes anything that is not decision-controlling, currently unproven, and falsifiable. It must merge assumptions that one safe validation can answer, assign stable IDs like `LB1`, and return a canonical markdown ledger table with columns `ID`, `Assumption`, `Decision controlled`, `Current evidence / uncertainty`, `Late-falsification cost`, `What changes if false`, and `Status`.

- [ ] **Step 4: Create the strategist prompt**

Write `subagents/prompt-load-bearing-strategist.md` so it receives `<load_bearing_ledger>`, `{WORKTREE_PATH}`, and `{LOAD_BEARING_SCOPE}`. It must assign `validate now`, `grouped with`, or `defer`, choose the cheapest reliable method and fallback chain, prefer run > inspect > official docs > broader internet, and mark any state-changing validation as `needs user approval`.

- [ ] **Step 5: Create the strategy-review prompt**

Write `subagents/prompt-load-bearing-strategy-review.md` so it receives the curated ledger and validation strategy. It must reject methods that will not isolate the answer, unsafe run commands, unnecessary fan-out, missing fallback chains, and accidental deferral of high/critical assumptions. It returns `## Strategy review verdict` as `READY` or `REVISE` plus concrete required corrections.

- [ ] **Step 6: Create the validator prompt**

Write `subagents/prompt-load-bearing-validator.md` so it receives one self-contained `<validation_target>` block. It must run only read-only/non-destructive commands, follow the assigned fallback chain, and return verdict, evidence, confidence, new assumptions, and blocked approval needs. It must not modify files or install dependencies.

- [ ] **Step 7: Create the evaluator prompt**

Write `subagents/prompt-load-bearing-evaluate.md` so it receives the curated ledger, validation strategy, all validator reports, `{USER_INTENT}`, and `{LOAD_BEARING_SCOPE}`. It must judge whether evidence really proves each claim, update ledger statuses, and return:

```markdown
## Load-bearing verdict
VERIFIED | NO_TARGETS | FALSIFIED | INCONCLUSIVE | NEEDS_USER_APPROVAL

## Load-bearing ledger path
<absolute path requested by the conductor or "conductor must save this report">

## Ledger
...

## Required follow-up
...

<review_observations_json>
{
  "status": "no_issues",
  "summary": "All load-bearing assumptions are verified or no targets remain.",
  "observations": []
}
</review_observations_json>
```

For `FALSIFIED`, `INCONCLUSIVE`, or `NEEDS_USER_APPROVAL`, the JSON must use `status: "issues_found"` with critical or major observations. Use existing categories only: `implementation_plan_mismatch`, `test_plan_mismatch`, `artifact_gap`, `behavior`, or `other`.

- [ ] **Step 8: Render-smoke each new prompt**

Run `python3 orchestrator/run_phase.py prepare` for each new template with temp input files and representative placeholder bindings. Expected: every command exits 0 and the rendered prompt path exists.

- [ ] **Step 9: Commit**

```bash
git add subagents/prompt-load-bearing-*.md
git commit -m "feat: add load-bearing phase prompts"
```

## Task 2: Wire The Plan-Time Gate Into `SKILL.md`

**Files:**
- Modify: `SKILL.md`
- Modify: `subagents/prompt-test-plan.md`

**Interfaces:**
- Produces `{PLAN_LOAD_BEARING_LEDGER_PATH}` after the plan-time evaluator succeeds.
- Passes `{PLAN_LOAD_BEARING_LEDGER}` into the test-plan prompt as optional context.

- [ ] **Step 1: Add state-variable definitions**

In `SKILL.md`, near the existing placeholder definitions, add definitions for:
- `{PLAN_LOAD_BEARING_LEDGER_PATH}` — latest accepted plan-time load-bearing ledger.
- `{POST_EXECUTION_LOAD_BEARING_LEDGER_PATH}` — latest post-execution load-bearing ledger.
- `{LOAD_BEARING_VALIDATION_REPORTS}` — temp file listing validator report paths for the current gate.

- [ ] **Step 2: Add a reusable full-gate procedure**

Add a section before numbered workflow steps named `## Load-bearing gate helper`. It must instruct the conductor to:
1. Prepare and dispatch a finder prompt for the current scope.
2. Prepare and dispatch curator.
3. Prepare and dispatch strategist.
4. Prepare and dispatch strategy-review.
5. If strategy-review says `REVISE`, send corrections back through strategist and repeat until `READY`.
6. Dispatch one fresh validator per validation target in parallel, each with `prompt-load-bearing-validator.md`.
7. Prepare and dispatch evaluator.
8. Extract `<review_observations_json>` with `review_observations.py extract`.
9. Treat `blocking_issue_count` as the gate decision.

- [ ] **Step 3: Insert plan-time gate after plan-editor `READY`**

After Step 8 produces `READY` and before Step 9 builds the test plan, insert a new numbered step `Build and run plan load-bearing gate`. The step must use `prompt-load-bearing-finder-plan.md`, then the helper phases. If the verdict is:
- `VERIFIED` or `NO_TARGETS`: save the evaluator report as `{PLAN_LOAD_BEARING_LEDGER_PATH}` and continue.
- `FALSIFIED` or `INCONCLUSIVE`: run a fresh planning subagent to revise the implementation plan using the load-bearing evaluator report, then return to the plan-editor loop.
- `NEEDS_USER_APPROVAL`: present the blocked approval report to the user and await instructions.

- [ ] **Step 4: Feed the ledger into test-plan construction**

Modify the Step 9 `test-plan` wrapper call to pass `--set-file PLAN_LOAD_BEARING_LEDGER={PLAN_LOAD_BEARING_LEDGER_PATH}` when that path exists, plus `--ignore-tag-for-placeholders plan_load_bearing_ledger`.

- [ ] **Step 5: Update `prompt-test-plan.md`**

Add an optional conditional block:

```markdown
{{#if PLAN_LOAD_BEARING_LEDGER}}
<plan_load_bearing_ledger>
{PLAN_LOAD_BEARING_LEDGER}
</plan_load_bearing_ledger>
{{/if}}
```

Then instruct the test-plan builder to use verified and falsified load-bearing findings as sources of truth for test priorities and acceptance artifacts, without broadening scope beyond user intent.

- [ ] **Step 6: Render-smoke affected prompts**

Render `prompt-test-plan.md` with and without `PLAN_LOAD_BEARING_LEDGER`. Expected: both variants render without unsubstituted placeholders; the ledger variant requires and ignores `plan_load_bearing_ledger`.

- [ ] **Step 7: Commit**

```bash
git add SKILL.md subagents/prompt-test-plan.md
git commit -m "feat: add plan-time load-bearing gate"
```

## Task 3: Wire The Post-Execution Gate Into `SKILL.md`

**Files:**
- Modify: `SKILL.md`
- Modify: `subagents/prompt-executing.md`

**Interfaces:**
- Consumes latest implementation report and artifacts before acceptance-artifact review.
- Produces `{POST_EXECUTION_LOAD_BEARING_LEDGER_PATH}` and normalized review observations.
- Feeds blocking observations back into the persistent implementation subagent.

- [ ] **Step 1: Insert post-execution gate before acceptance-artifact review**

In Step 11, after each implementation report is saved and workspace hygiene passes, run the full load-bearing helper using `prompt-load-bearing-finder-execution.md`. This applies to the initial implementation report and every fix-round implementation report before the next acceptance-artifact review.

- [ ] **Step 2: Define post-execution routing**

If post-execution load-bearing evaluator reports:
- `VERIFIED` or `NO_TARGETS`: save the evaluator report as `{POST_EXECUTION_LOAD_BEARING_LEDGER_PATH}`, append it to `{REVIEW_LOOP_HISTORY}`, then start acceptance-artifact review.
- `FALSIFIED` or `INCONCLUSIVE`: treat the normalized observations like failed verification and resume the implementation subagent with `prompt-executing.md`, passing `--set-file LOAD_BEARING_REVIEW_OBSERVATIONS_JSON=<review-observations-temp-file>` and `--ignore-tag-for-placeholders load_bearing_review_observations_json`.
- `NEEDS_USER_APPROVAL`: present the blocked approval report to the user and await instructions.

- [ ] **Step 3: Add execution prompt conditional**

Add this optional block to `subagents/prompt-executing.md`:

```markdown
{{#if LOAD_BEARING_REVIEW_OBSERVATIONS_JSON}}
<load_bearing_review_observations_json>
{LOAD_BEARING_REVIEW_OBSERVATIONS_JSON}
</load_bearing_review_observations_json>
{{/if}}
```

Add an instruction that critical and major load-bearing observations are failed verification targets. The implementation must either fix code, strengthen tests/artifacts, or explain a real blocker; minor and nit observations are not required fix targets.

- [ ] **Step 4: Preserve nonconvergence evidence**

Update nonconvergence-review instructions in `SKILL.md` so phase prompt paths, loop output paths, implementation reports, and load-bearing reports are all available when the loop stops.

- [ ] **Step 5: Render-smoke affected prompts**

Render `prompt-executing.md` with and without `LOAD_BEARING_REVIEW_OBSERVATIONS_JSON`. Expected: both variants render without unsubstituted placeholders; the observations variant ignores `load_bearing_review_observations_json`.

- [ ] **Step 6: Commit**

```bash
git add SKILL.md subagents/prompt-executing.md
git commit -m "feat: add post-execution load-bearing gate"
```

## Task 4: Verify The Complete Skill Flow

**Files:**
- Modify: none unless verification exposes missing placeholders or unclear prose.

**Interfaces:**
- Consumes all changed prompt templates and `SKILL.md`.
- Produces verification output for final report.

- [ ] **Step 1: Render all new prompts through the phase wrapper**

Use temporary files under `/tmp` for representative `{USER_INTENT}`, finder report, ledger, strategy, validation target, validation reports, testing strategy, test plan, and latest implementation report. Render every new prompt with `python3 orchestrator/run_phase.py prepare`.

- [ ] **Step 2: Render modified existing prompts through the phase wrapper**

Render `prompt-test-plan.md` with optional ledger and `prompt-executing.md` with optional load-bearing observations.

- [ ] **Step 3: Run existing test suite**

```bash
python3 -m unittest discover -s tests
```

Expected: exits 0. Existing baseline result was `Ran 126 tests ... OK (skipped=4)`.

- [ ] **Step 4: Inspect flow references**

Run:

```bash
rg -n "load-bearing|LOAD_BEARING|PLAN_LOAD_BEARING|POST_EXECUTION_LOAD_BEARING" SKILL.md subagents
```

Expected: references are coherent, each placeholder defined in `SKILL.md` is either bound in wrapper calls or intentionally written as a literal inside an ignored tag.

- [ ] **Step 5: Commit any fixes**

If verification requires corrections:

```bash
git add SKILL.md subagents/prompt-*.md
git commit -m "fix: tighten load-bearing prompt wiring"
```
