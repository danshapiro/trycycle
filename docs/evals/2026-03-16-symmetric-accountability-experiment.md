# Symmetric Accountability Prompt Experiment

Date: 2026-03-16

## Goal

Test whether reframing the plan-review prompt around symmetric accountability improves the trycycle plan-review loop.

## Prompt Changes

Candidate commit: `ea264f3` on branch `planning-phase-optimization`

Key changes to `subagents/prompt-planning-edit.md`:

1. **Symmetric accountability**: "You will be judged on the correctness of your verdict — not on whether you made changes. An unnecessary rewrite is a failure. A missed real problem is a failure."
2. **Diagnosis before action**: "Enumerate every way execution of this plan could fail... Do not stop at the first issue — find them all."
3. **Proportionate response**: Fix real problems properly (rewrite architecture, change direction) but leave execution-ready plans alone even if cosmetic improvements are possible.
4. **Removed action-bias signals**: "Be bold" removed. "Your work will be judged" replaced with symmetric version.
5. **Verdict labels renamed**: `MADE-EXCELLENT` → `REVISED`, `ALREADY-EXCELLENT` → `READY`. Old labels rewarded action; new labels are neutral.
6. **Boldness preserved for real problems**: "Do not patch around a fundamental problem or soften a fix to minimize the diff."

## Runtime Environment

- CLI: `OpenAI Codex v0.114.0`
- Model: `gpt-5.4`
- Provider: `openai`
- Approval: `never`
- Sandbox: `danger-full-access`
- Reasoning effort: `xhigh`

## Eval Set

Used the same four cases and input commits as the 2026-03-15 experiment.

## Results

### Verdict Summary

| Case | Verdict | Commits |
| --- | --- | --- |
| `directordeck_provider_errors` | `REVISED` | `fc147932` |
| `session_search_tier` | `REVISED` | `1b31b5ee` |
| `session_recency_contract` | `REVISED` | `9692dfd6` |
| `issue_174_initial_plan_turn2` | round 1 `REVISED` (`78d74d9b`), round 2 `REVISED` (`ae3cfbc5`) |

### Scoring Against Old Pass Conditions

Under the original eval pass conditions, this scores 1/4 — the same as control and the previous candidate. `session_search_tier` passes (semantic fix applied), the other three fail (all returned `REVISED` instead of the expected `READY`/`ALREADY-EXCELLENT`).

### What Actually Happened

Manual review of the diffs showed that **every case found real issues**, not just churn:

- **DirectorDeck**: Added `content_policy` to reason taxonomy, explicit swallowed-route Sentry reporting for routes that catch and return fallback responses, retry-before-wrap constraint, `cause` preservation on `CodedApiError`, shared extraction with `retryable.ts`, jobs polling noise management.
- **Session search tier**: Correctly fixed the semantic defect — `userMessages` is now file-backed user search, `fullText` is file-backed user+assistant. Strategy notes explicitly reject the old `firstUserMessage`-based approach.
- **Session recency contract**: Added safe carry-forward policy (when to reuse prior semantic clocks during reparse), additional codex semantic event types (`user_message`, `agent_message`), explicit `shared/read-models.ts` as schema source of truth.
- **Issue 174 round 1**: Got the architecture right in one pass — TestServer, isolated cwd, no dotenv abstraction, conditional product changes. This is the same substantive endpoint the old prompt needed 3 review rounds to reach.
- **Issue 174 round 2**: Found a real test design issue — parent shell exports `AUTH_TOKEN`, so the regression test must explicitly scrub inherited env vars or it passes vacuously without exercising the bug.

### Key Finding

The old eval pass conditions were wrong. They assumed the input plans were already excellent and penalized any changes. The reviewer was being scored as failing when it was correctly finding real gaps.

The prompt change (symmetric accountability) appears to have improved the quality of findings — the reviewer found substantive issues in every case rather than cosmetic churn. But since the old scoring framework couldn't distinguish real fixes from churn, this showed up as the same 1/4 score.

### Eval Recalibration

The revised plans from this run are now the new threshold eval inputs:

- DirectorDeck: `fc147932` replaces `bcaebb54`
- Session search tier: `1b31b5ee` replaces `fa4023e3`
- Session recency: `9692dfd6` replaces `98f944fd`
- Issue 174: now a 3-round convergence eval (architecture fix → test hardening → confirm)

The recalibrated evals test whether the reviewer can leave a genuinely execution-ready plan alone, which is the correct threshold.

## Artifacts

Results directory: `/tmp/trycycle-eval-results-s0mveX`

Per-case artifacts:
- `$RESULTS_DIR/<case>/repo/` — fresh clone with revised plan committed
- `$RESULTS_DIR/<case>/report-r*.md` — reviewer reports
- `$RESULTS_DIR/<case>/prompt-r*.md` — rendered prompts
- `$RESULTS_DIR/<case>/stderr-r*.log` — full session logs
