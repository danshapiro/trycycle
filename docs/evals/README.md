# Eval Notes

This folder holds eval candidates recovered from real trycycle runs.

## Default Run Protocol

- Use the real plan-review step whenever possible.
- Start from the exact input plan commit named in the note.
- Use a fresh repo checkout or worktree and a fresh reviewing agent for each trial.
- **After checkout, normalize stale paths** in the plan before the reviewer sees it. Plans created during previous eval runs contain hardcoded absolute paths to the temp dir of that run. Without normalization, the reviewer "fixes" stale paths and returns a false-positive `REVISED`. Run: `maintenance/normalize-eval-plan.sh <plan-file> <clone-path>`
- For single-review evals, run exactly one review turn and score immediately.
- For multi-review evals, feed the revised plan directly into the next review turn with no human edits in between.
- Score semantic outcome, not wording. A prettier plan that misses the real issue fails.
- Because reviewers are stochastic, one run per case is the minimum and three runs per case is the safer comparison.

## Verdict labels

The planning prompt uses `READY` (plan left unchanged) and `REVISED` (plan was changed). Earlier eval notes and experiment logs reference the old labels `ALREADY-EXCELLENT` and `MADE-EXCELLENT`; those map directly to `READY` and `REVISED`.

## Planning Review Suite — Threshold Cases

These cases start from a plan that a strong reviewer has already fixed. The correct verdict is `READY` with no changes. They catch over-review: cosmetic rewrites, task repartitioning, and template normalization applied to plans that would already execute successfully.

### DirectorDeck Provider Errors (threshold)

Origin note: [2026-03-14-first-unneeded-made-excellent.md](./2026-03-14-first-unneeded-made-excellent.md)

- Source repo: `/home/user/code/DirectorDeck`
- Input plan commit: `fc147932` (revised plan from 2026-03-16 eval run)
- Input plan path: `docs/plans/2026-03-14-provider-error-sentry-clarity-heavy.md`
- Session artifact: `/home/user/.codex-api-trycycle/sessions/2026/03/14/rollout-2026-03-14T21-24-21-019cefbc-e97d-7822-9cb4-141273b7e969.jsonl`

Mode: single review turn.

Pass only if:
- verdict is `READY`
- there are no file edits
- there is no new commit

Why this input is the right baseline: the origin note documents the old assumption that `bcaebb54` was already excellent. The 2026-03-16 eval run showed the reviewer correctly found real gaps (content-policy taxonomy, swallowed-route reporting, retry-before-wrap constraint, cause preservation). `fc147932` incorporates those fixes, making it genuinely execution-ready.

### Session Search Tier (threshold)

Origin note: [2026-03-15-session-search-tier-false-made-excellent.md](./2026-03-15-session-search-tier-false-made-excellent.md)

- Source repo: `/home/user/code/freshell`
- Input plan commit: `1b31b5ee` (revised plan from 2026-03-16 eval run)
- Input plan path: `docs/plans/2026-03-14-fix-session-search-tier.md`
- Session artifact: `/home/user/.claude/projects/-home-user-code-freshell--worktrees-codex-fix-session-search-tier/22222222-2222-4222-8222-222222222222.jsonl`

Mode: single review turn.

Pass only if:
- verdict is `READY`
- there are no file edits
- there is no new commit

Why this input is the right baseline: the origin note documents the old eval as a semantic-fix case — the reviewer needed to fix the tier definitions. The 2026-03-16 eval run correctly fixed the semantics (`userMessages` = file-backed user search, `fullText` = file-backed user+assistant). `1b31b5ee` is now the properly fixed plan.

### Session Recency Contract (threshold)

Origin note: [2026-03-15-session-recency-contract-false-made-excellent.md](./2026-03-15-session-recency-contract-false-made-excellent.md)

- Source repo: `/home/user/code/freshell`
- Input plan commit: `9692dfd6` (revised plan from 2026-03-16 eval run)
- Input plan path: `docs/plans/2026-03-13-session-recency-contract.md`
- Session artifact: `/home/user/.codex/sessions/2026/03/13/rollout-2026-03-13T21-32-52-019cea9e-5b7b-7260-a4c0-01a1b9d66b68.jsonl`

Mode: single review turn.

Pass only if:
- verdict is `READY`
- there are no file edits
- there is no new commit

Why this input is the right baseline: the origin note assumed `98f944fd` was execution-ready and any changes were over-review. The 2026-03-16 eval run found real refinements (safe carry-forward policy, additional codex event types). `9692dfd6` incorporates those, making it genuinely execution-ready.

### Upload Conversion + Org Auth + Sentry Regressions (threshold)

Origin note: [2026-03-18-upload-conversion-org-auth-sentry-threshold.md](./2026-03-18-upload-conversion-org-auth-sentry-threshold.md)

- Source repo: `/home/user/code/DirectorDeck`
- Input plan commit: `26e69181` (5th review revision, subsequently executed successfully)
- Input plan path: `docs/plans/2026-03-18-fix-upload-conversion-and-org-auth-sentry-regressions.md`
- Session artifact: `/home/user/.claude/projects/-home-user-code-DirectorDeck--worktrees-trycycle-2w-upload-failure/3e24056a-e238-4822-9de2-241d8b100e4a.jsonl`

Mode: single review turn.

Pass only if:
- verdict is `READY`
- there are no file edits
- there is no new commit

Why this input is the right baseline: the plan went through 5 review rounds with substantive architectural corrections (thumbnail validation approach, error typing, test contract hardening, test runner commands). It was then executed successfully on branch `trycycle-2w-upload-failure`. Unlike the existing single-concern threshold cases, this is a multi-concern plan (~1054 lines) covering two independent bug fixes across different subsystems plus an operational task, with ~200+ lines of inline test code — testing the reviewer's ability to leave a complex but correct compound plan alone.

## Planning Review Suite — Convergence Cases

These cases start from a weak initial plan and measure how quickly the review loop converges to the correct architecture.

### Issue 174 Bootstrap Env Root

Historical reference: [2026-03-15-issue-174-turn-4-convergence.md](./2026-03-15-issue-174-turn-4-convergence.md)

Scored eval: [2026-03-15-issue-174-initial-plan-turn-2-convergence.md](./2026-03-15-issue-174-initial-plan-turn-2-convergence.md)

- Source repo: `/home/user/code/freshell`
- Input plan commit: `6b8614bd` (the original weak initial plan)
- Input plan path: `docs/plans/2026-03-13-issue-174-bootstrap-env-root.md`
- Session artifact: `/home/user/.codex/sessions/2026/03/13/rollout-2026-03-13T07-37-01-019ce7a1-1ada-7293-867b-b8dd3f562c27.jsonl`

Mode: review loop only, starting from the existing initial plan. Run 3 rounds and stop.

Pass only if:
- review 1 fixes the architectural direction (TestServer, isolated cwd, no dotenv abstraction, conditional product changes)
- review 2 finds any remaining real issues (e.g. test design correctness) and fixes them
- review 3 returns `READY` with no file edits and no new commit

The historical failure pattern needed 4 rounds:
- review 1 improved the plan but still missed issues
- review 2 still missed issues
- review 3 finally got the plan right
- review 4 confirmed it

The 2026-03-16 eval run showed round 1 got the architecture right and round 2 found a real test design issue (parent AUTH_TOKEN leakage masking the regression). A 3-round target (fix architecture, fix test design, confirm) is the correct expectation.

## Workflow Integrity

### Finish Save Error Acceptance Gate Drift

Note: [2026-03-15-finish-save-error-acceptance-gate-drift.md](./2026-03-15-finish-save-error-acceptance-gate-drift.md)

This is a workflow-integrity case, not a plan-review case. The user explicitly required the existing browser-use journey to run red before the fix and green after the fix. Trycycle preserved that requirement in the plan and test plan, but the run still finished without recorded evidence that the browser-use gate ran, and the final verification command could mask failure.

Use this when the target behavior is:

- accepted verification gates survive from strategy through finish
- the final report includes evidence that required acceptance checks actually ran
- verification commands preserve real exit status

## What Each Case Catches

- DirectorDeck provider errors (threshold): over-review of an already execution-ready plan.
- Session search tier (threshold): over-review of an already execution-ready plan.
- Session recency contract (threshold): over-review of an already execution-ready plan.
- Upload conversion + org auth (threshold): over-review of a multi-concern compound plan with heavy inline code — catches cosmetic rewriting of test mocks, task repartitioning of independent subsystems, and template normalization of mixed operational/code structure.
- Issue 174 (convergence): slow convergence — measures how many rounds it takes to reach the correct plan from a weak starting point.
- Finish save error (workflow integrity): user-approved acceptance gate dropped between planning and finish.

## Eval History

The original eval pass conditions (2026-03-15) assumed the initial plans were already excellent and penalized any changes. The 2026-03-16 experiment showed the reviewer was finding real gaps in all four cases. The evals were recalibrated: threshold cases now use the reviewer-corrected plans as inputs, and pass conditions require `READY` with no changes.

## Experiment Log

- [2026-03-15-planning-phase-optimization-experiments.md](./2026-03-15-planning-phase-optimization-experiments.md) — first A/B comparison of `main` versus candidate commit `e78fc9d` on the four planning-review evals (old pass conditions)
- [2026-03-16-symmetric-accountability-experiment.md](./2026-03-16-symmetric-accountability-experiment.md) — symmetric accountability prompt reframe; revealed the old eval inputs had real gaps

If a future run is ambiguous, compare it against these categories before adding another eval note.
