# Load-Bearing Gates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add full load-bearing assumption validation gates to Trycycle immediately after implementation-plan approval and again after each implementation report.

**Architecture:** Trycycle stays self-contained by adapting the load-bearing workflow into new Trycycle prompt templates and explicit `SKILL.md` orchestration steps. The first gate validates the finalized implementation plan before test-plan construction; the second gate validates unproven assumptions under the implementation report and produced evidence before acceptance-artifact review. Both gates use finder, curator, strategist, strategy-review, validator, and evaluator phases; plan-time blockers route through a dedicated load-bearing plan-revision prompt, and post-execution blockers route through the existing implementation prompt with a new load-bearing observations input.

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
- Create `subagents/prompt-load-bearing-plan-revision.md`: revises the implementation plan when plan-time load-bearing validation falsifies or weakens assumptions.
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
- Create: `subagents/prompt-load-bearing-plan-revision.md`

**Interfaces:**
- Consumes: `{USER_INTENT}`, `{WORKTREE_PATH}`, `{IMPLEMENTATION_PLAN_PATH}`, `{TEST_PLAN_PATH}`, `{TESTING_STRATEGY_PATH}`, `{LATEST_IMPLEMENTATION_REPORT}`, `{LOAD_BEARING_LEDGER}`, `{LOAD_BEARING_LEDGER_PATH}`, `{LOAD_BEARING_STRATEGY}`, `{LOAD_BEARING_VALIDATION_TARGET}`, `{LOAD_BEARING_VALIDATION_REPORTS}`, `{LOAD_BEARING_EVALUATION_REPORT}`, `{LOAD_BEARING_SCOPE}`.
- Produces: finder list, curated ledger file, validation strategy with strict validation-target blocks, strategy-review report, validator reports, evaluator report, canonical ledger file, optional `<review_observations_json>`, and plan-revision reports.

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
- Treat a missing, incomplete, stale, or unclear acceptance-artifact manifest as a blocking load-bearing assumption/gap. The report does not have to be mechanically schema-enforced; this phase must fail closed when provenance is not inspectable.
- Do not perform acceptance-artifact review or code review. Do not rerun tests or recreate artifacts in this phase.
- Do not validate assumptions in this phase.

Return a markdown report with:
- `## Scope` — `post-execution`
- `## Assumptions` — one numbered item per assumption, each with claim, decision controlled, current evidence or uncertainty, late-falsification cost, what changes if false, and why currently unproven
- `## Non-load-bearing notes` — relevant but pruned facts, or `None`
```

- [ ] **Step 3: Create the curator prompt**

Write `subagents/prompt-load-bearing-curate.md` so it receives `<finder_report>`, `{USER_INTENT}`, `{WORKTREE_PATH}`, and `{LOAD_BEARING_SCOPE}`, then prunes anything that is not decision-controlling, currently unproven, and falsifiable. It must merge assumptions that one safe validation can answer, assign stable IDs like `LB1`, and write a canonical markdown ledger to `{LOAD_BEARING_LEDGER_PATH}` with columns `ID`, `Assumption`, `Decision controlled`, `Current evidence / uncertainty`, `Late-falsification cost`, `What changes if false`, and `Status`. It returns a short report with `## Load-bearing ledger path`, byte count, and any pruned notes. Downstream prompts consume this canonical ledger file, not the curator's prose report.

- [ ] **Step 4: Create the strategist prompt**

Write `subagents/prompt-load-bearing-strategist.md` so it receives `<load_bearing_ledger>`, `{WORKTREE_PATH}`, and `{LOAD_BEARING_SCOPE}`. It must assign `validate now`, `grouped with`, or `defer`, choose the cheapest reliable method and fallback chain, prefer run > inspect > official docs > broader internet, and mark any state-changing validation as `needs user approval`.

The strategy must include strict fenced target blocks so the conductor can create one temp file per validator without parsing free prose. Use exactly this shape for every target:

````markdown
```load-bearing-validation-target
Target: LBT1
Assumptions: LB1, LB3
Decision controlled: Name the architecture, boundary, data, lifecycle, safety, or verification decision that depends on these assumptions.
Current evidence / uncertainty: State what is currently known and what remains unproven.
Late-falsification cost: high
What would have to change if false: State the concrete plan, test-plan, execution, or artifact-routing change required if validation falsifies the assumptions.
Assigned method + fallback chain: inspect the named local files first, then run the named read-only command if inspection is inconclusive.
Context needed: List the repository path, relevant file paths, commands, and any artifact paths required to validate this target.
Safety constraints: read-only/non-destructive; report blocked state-changing actions
```
````

Assumptions marked `defer` must appear in a `## Deferred assumptions` section with a one-sentence reason.

- [ ] **Step 5: Create the strategy-review prompt**

Write `subagents/prompt-load-bearing-strategy-review.md` so it receives `{LOAD_BEARING_SCOPE}`, the curated ledger, and validation strategy. It must reject methods that will not isolate the answer, unsafe run commands, unnecessary fan-out, missing fallback chains, missing or malformed fenced `load-bearing-validation-target` blocks, and accidental deferral of high/critical assumptions. It returns `## Strategy review verdict` as `READY` or `REVISE` plus concrete required corrections.

- [ ] **Step 6: Create the validator prompt**

Write `subagents/prompt-load-bearing-validator.md` so it receives `{LOAD_BEARING_SCOPE}` and one self-contained `<validation_target>` block copied verbatim from a fenced `load-bearing-validation-target` block. It must run only read-only/non-destructive commands, follow the assigned fallback chain, and return verdict, evidence, confidence, new assumptions, and blocked approval needs. It must not modify files or install dependencies.

- [ ] **Step 7: Create the evaluator prompt**

Write `subagents/prompt-load-bearing-evaluate.md` so it receives the canonical ledger file, validation strategy, all validator reports, `{USER_INTENT}`, `{LOAD_BEARING_SCOPE}`, and `{LOAD_BEARING_LEDGER_PATH}`. It must judge whether evidence really proves each claim, update ledger statuses, write the updated canonical ledger back to `{LOAD_BEARING_LEDGER_PATH}`, and return:

```markdown
## Load-bearing verdict
VERIFIED | NO_TARGETS | FALSIFIED | INCONCLUSIVE | NEEDS_USER_APPROVAL

## Load-bearing ledger path
{LOAD_BEARING_LEDGER_PATH}

## Ledger
The evaluator must include the updated canonical ledger table, with every assumption status set to verified, falsified, inconclusive, accepted-risk-needed, or deferred.

## Required follow-up
The evaluator must name the exact next routing action: continue, revise plan, resume execution with observations, ask the user for approval, or rerun validation with a stronger method.

<review_observations_json>
{
  "status": "no_issues",
  "summary": "All load-bearing assumptions are verified or no targets remain.",
  "observations": []
}
</review_observations_json>
```

For `FALSIFIED`, `INCONCLUSIVE`, or `NEEDS_USER_APPROVAL`, the JSON must use `status: "issues_found"` with critical or major observations. Use existing categories only: `implementation_plan_mismatch`, `test_plan_mismatch`, `artifact_gap`, `behavior`, or `other`.

The prompt must state that the markdown verdict and JSON must be self-consistent:
- `VERIFIED` and `NO_TARGETS` require JSON `status: "no_issues"` with an empty observations array.
- `FALSIFIED` and `INCONCLUSIVE` require JSON `status: "issues_found"` with at least one critical or major observation.
- `NEEDS_USER_APPROVAL` requires the report to begin with `USER DECISION REQUIRED:` or JSON `status: "issues_found"` with a critical/major `other` observation naming the blocked state-changing validation.

The conductor still runs `review_observations.py extract`, but it must also check this consistency rule before routing. If the markdown verdict and normalized JSON conflict, stop and surface the evaluator report plus extractor output instead of guessing.

- [ ] **Step 8: Create the plan-revision prompt**

Write `subagents/prompt-load-bearing-plan-revision.md` so it receives `{USER_INTENT}`, `{WORKTREE_PATH}`, `{IMPLEMENTATION_PLAN_PATH}`, and `{LOAD_BEARING_EVALUATION_REPORT}`. It must use only the `trycycle-planning` subskill, revise the implementation plan to remove, verify, or explicitly route around falsified/inconclusive plan-time assumptions, commit the revised plan, and return:

```markdown
## Plan revision verdict
UPDATED | USER_DECISION_REQUIRED

## Load-bearing issues addressed
List every critical or major load-bearing observation addressed and the plan section changed for it.

## Plan path
Absolute path to the revised implementation plan.

## Commit
Latest short commit hash after committing the revised plan.

## Changed files
One changed path per line.
```

If user judgment is genuinely required, it must return a report beginning `USER DECISION REQUIRED:` and must not modify files.

- [ ] **Step 9: Render-smoke each new prompt**

Run `python3 orchestrator/run_phase.py prepare` for each new template with temp input files and representative placeholder bindings. Expected: every command exits 0 and the rendered prompt path exists.

- [ ] **Step 10: Commit**

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
- `{LOAD_BEARING_LEDGER_PATH}` — current gate's canonical ledger output path, passed to curator and evaluator.
- `{LOAD_BEARING_EVALUATION_REPORT}` — latest evaluator report used by plan revision or execution fix routing.

- [ ] **Step 2: Add a reusable full-gate procedure**

Add a section before numbered workflow steps named `## Load-bearing gate helper`. It must instruct the conductor to:
1. Prepare and dispatch a finder prompt for the current scope.
2. Prepare and dispatch curator.
3. Prepare and dispatch strategist.
4. Prepare and dispatch strategy-review.
5. If strategy-review says `REVISE`, send corrections back through strategist and repeat until `READY`, up to 3 strategy-review rounds.
6. If strategy review is still not `READY` after 3 rounds, run `prompt-nonconvergence-review.md` with context `Load-bearing strategy-review loop reached 3 rounds without a READY verdict`, present that report and the latest strategy-review report to the user, and await instructions.
7. Copy each fenced `load-bearing-validation-target` block from the accepted strategy to its own temp file and dispatch one fresh validator per target in parallel using `prompt-load-bearing-validator.md`.
8. Prepare and dispatch evaluator.
9. Extract `<review_observations_json>` with `review_observations.py extract`.
10. Verify evaluator verdict and normalized JSON are self-consistent. If they conflict, stop and surface both artifacts.
11. Treat the self-consistent normalized JSON's `blocking_issue_count` as the gate decision.

- [ ] **Step 3: Insert plan-time gate after plan-editor `READY`**

After Step 8 produces `READY` and before Step 9 builds the test plan, insert a new numbered step `Build and run plan load-bearing gate`. The step must use `prompt-load-bearing-finder-plan.md`, then the helper phases. If the self-consistent evaluator result is:
- `VERIFIED` or `NO_TARGETS`: save the evaluator report as `{PLAN_LOAD_BEARING_LEDGER_PATH}` and continue.
- `FALSIFIED` or `INCONCLUSIVE`: run a fresh planning subagent with `prompt-load-bearing-plan-revision.md`, passing `--set-file LOAD_BEARING_EVALUATION_REPORT=<evaluator-report-temp-file>` and `--ignore-tag-for-placeholders load_bearing_evaluation_report`, then return to the plan-editor loop with the revised implementation plan path.
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

In Step 11, after each implementation report is saved and workspace hygiene passes, run the full load-bearing helper using `prompt-load-bearing-finder-execution.md`. This applies to the initial implementation report and every fix-round implementation report before the next acceptance-artifact review. The helper must treat a missing or incomplete artifact manifest in the implementation report as a blocking post-execution load-bearing issue, because the gate cannot validate evidence that is not inspectable.

- [ ] **Step 2: Define post-execution routing**

If the self-consistent post-execution load-bearing evaluator result is:
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

Update nonconvergence-review instructions in `SKILL.md` so load-bearing phase prompt paths and load-bearing reports are appended to the existing phase prompt paths and loop outputs temp files with clear labels such as `load-bearing-plan evaluator report:` and `load-bearing-post-execution validator report:`. The existing nonconvergence prompt already accepts generic run context and artifact lists, so no new dedicated artifact placeholder is required.

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

Use temporary files under `/tmp` for representative `{USER_INTENT}`, finder report, canonical ledger, validation strategy with two fenced `load-bearing-validation-target` blocks, one copied validation target, validation reports, load-bearing evaluation report, testing strategy, test plan, and latest implementation report. Render every new prompt with `python3 orchestrator/run_phase.py prepare`.

- [ ] **Step 2: Render modified existing prompts through the phase wrapper**

Render `prompt-test-plan.md` with optional ledger and `prompt-executing.md` with optional load-bearing observations.

- [ ] **Step 3: Run existing test suite**

```bash
python3 -m unittest discover -s tests
```

Expected: exits 0. Existing baseline result was `Ran 126 tests in 14.981s` and `OK (skipped=4)`.

- [ ] **Step 4: Inspect flow references**

Run:

```bash
rg -n "load-bearing|LOAD_BEARING|PLAN_LOAD_BEARING|POST_EXECUTION_LOAD_BEARING" SKILL.md subagents
```

Expected: references are coherent, each placeholder defined in `SKILL.md` is either bound in wrapper calls or intentionally written as a literal inside an ignored tag.

- [ ] **Step 5: Run the extractor consistency probe**

Run a local probe equivalent to:

```bash
PYTHONPATH=orchestrator python3 - <<'PY'
from review_observations import _extract_tagged_json, normalize_payload
reply = '<review_observations_json>{"status":"issues_found","summary":"lb","observations":[{"id":"LB1","severity":"critical","category":"implementation_plan_mismatch","expected":"verified assumption","observed":"falsified assumption"}]}</review_observations_json>'
payload = normalize_payload(_extract_tagged_json(reply))
assert payload["blocking_issue_count"] == 1
print("ok")
PY
```

Expected: `ok`. This proves the JSON side of load-bearing evaluator output can route blockers; the prompt and `SKILL.md` consistency rule handles the markdown verdict side.

- [ ] **Step 6: Commit any fixes**

If verification requires corrections:

```bash
git add SKILL.md subagents/prompt-*.md
git commit -m "fix: tighten load-bearing prompt wiring"
```
