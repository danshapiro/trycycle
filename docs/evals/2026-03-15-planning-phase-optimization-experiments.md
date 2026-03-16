# Planning Phase Optimization Experiments

Date: 2026-03-15

## Goal

Measure whether planning-phase prompt edits improve the trycycle plan-review loop on real recovered cases.

This experiment isolates the review step. Every case starts from an existing implementation plan, so the only prompt under test here is `subagents/prompt-planning-edit.md`. Changes to `subagents/prompt-planning-initial.md` were out of scope for this batch.

## Prompt Versions Compared

### Control

- Trycycle checkout: `/home/user/code/trycycle`
- Commit under test: `4098c1c` (`docs: rebalance trycycle test prompts`)
- Prompt under test: `/home/user/code/trycycle/subagents/prompt-planning-edit.md`

### Candidate

- Trycycle checkout: `/home/user/code/trycycle/.worktrees/codex-plan-thoroughness-threshold`
- Candidate commit under test: `e78fc9d` (`prompt(planning): tighten plan review judgment`)
- Prompt under test: `/home/user/code/trycycle/.worktrees/codex-plan-thoroughness-threshold/subagents/prompt-planning-edit.md`
- Exact reproduction note: to replay this exact candidate later, check out trycycle commit `e78fc9d` in any clone and use that checkout as `TRYCYCLE_ROOT`.

## Runtime Environment

- CLI: `OpenAI Codex v0.114.0`
- Model: `gpt-5.4`
- Provider: `openai`
- Approval: `never`
- Sandbox: `danger-full-access`
- Reasoning effort: `xhigh`

## Eval Set

### `directordeck_provider_errors`

- Eval note: [2026-03-14-first-unneeded-made-excellent.md](./2026-03-14-first-unneeded-made-excellent.md)
- Source repo: `/home/user/code/DirectorDeck`
- Input plan commit: `bcaebb54`
- Input plan path: `docs/plans/2026-03-14-provider-error-sentry-clarity-heavy.md`
- Recovered transcript artifact: `/home/user/.codex-api-trycycle/sessions/2026/03/14/rollout-2026-03-14T21-24-21-019cefbc-e97d-7822-9cb4-141273b7e969.jsonl`
- Mode: single review turn
- Pass condition: `ALREADY-EXCELLENT`, no file edits, no new commit

### `session_search_tier`

- Eval note: [2026-03-15-session-search-tier-false-made-excellent.md](./2026-03-15-session-search-tier-false-made-excellent.md)
- Source repo: `/home/user/code/freshell`
- Input plan commit: `fa4023e3`
- Input plan path: `docs/plans/2026-03-14-fix-session-search-tier.md`
- Recovered transcript artifact: `/home/user/.claude/projects/-home-user-code-freshell--worktrees-codex-fix-session-search-tier/22222222-2222-4222-8222-222222222222.jsonl`
- Mode: single review turn
- Pass condition: the rewritten plan materially fixes the tier semantics

### `session_recency_contract`

- Eval note: [2026-03-15-session-recency-contract-false-made-excellent.md](./2026-03-15-session-recency-contract-false-made-excellent.md)
- Source repo: `/home/user/code/freshell`
- Input plan commit: `98f944fd`
- Input plan path: `docs/plans/2026-03-13-session-recency-contract.md`
- Recovered transcript artifact: `/home/user/.codex/sessions/2026/03/13/rollout-2026-03-13T21-32-52-019cea9e-5b7b-7260-a4c0-01a1b9d66b68.jsonl`
- Mode: single review turn
- Pass condition: `ALREADY-EXCELLENT`, no file edits, no new commit

### `issue_174_initial_plan_turn2`

- Eval note: [2026-03-15-issue-174-initial-plan-turn-2-convergence.md](./2026-03-15-issue-174-initial-plan-turn-2-convergence.md)
- Historical baseline: [2026-03-15-issue-174-turn-4-convergence.md](./2026-03-15-issue-174-turn-4-convergence.md)
- Source repo: `/home/user/code/freshell`
- Input plan commit: `6b8614bd`
- Input plan path: `docs/plans/2026-03-13-issue-174-bootstrap-env-root.md`
- Recovered transcript artifact: `/home/user/.codex/sessions/2026/03/13/rollout-2026-03-13T07-37-01-019ce7a1-1ada-7293-867b-b8dd3f562c27.jsonl`
- Mode: review loop only, starting from the existing initial plan
- Pass condition: review 1 reaches the final correct plan substance, and review 2 returns `ALREADY-EXCELLENT` with no new edits

## Replay Protocol

The stable part of the experiment is the replay protocol, not the temporary wrapper script that happened to run it.

Use the same steps for every case:

1. Create a fresh local clone from the source repo and check out the exact input plan commit on a throwaway branch.
2. Extract the exact `<task_input_json>` payload from the recovered session artifact.
3. Render the selected `prompt-planning-edit.md` with the real trycycle prompt builder.
4. Run a fresh non-interactive planning subagent with `codex exec`.
5. Score the result against the eval note.
6. For `issue_174_initial_plan_turn2` only, feed the revised plan directly into a second review round and stop after round 2.

Parallelization is optional. It changes throughput, not scoring.

## Reproduction Commands

These commands are the simplest durable way to replay one case. Use `bash`. If you automate multiple cases, prefer a temp script or one owning shell rather than a long inline cross-shell command.

Set per-case variables first:

```bash
TRYCYCLE_ROOT=/home/user/code/trycycle
SOURCE_REPO=/home/user/code/freshell
CASE_ID=session_search_tier
INPUT_COMMIT=fa4023e3
PLAN_RELPATH=docs/plans/2026-03-14-fix-session-search-tier.md
SESSION_ARTIFACT=/home/user/.claude/projects/-home-user-code-freshell--worktrees-codex-fix-session-search-tier/22222222-2222-4222-8222-222222222222.jsonl
SCRATCH_ROOT=$(mktemp -d /tmp/trycycle-planning-eval-XXXXXX)
CLONE_DIR="$SCRATCH_ROOT/repo"
```

Create the fresh repo state:

```bash
git clone --local "$SOURCE_REPO" "$CLONE_DIR"
git -C "$CLONE_DIR" checkout -q "$INPUT_COMMIT"
git -C "$CLONE_DIR" switch -c "eval-$CASE_ID"
git -C "$CLONE_DIR" config user.name "Codex Eval"
git -C "$CLONE_DIR" config user.email "codex-eval@example.com"
git -C "$CLONE_DIR" config commit.gpgsign false
```

Extract the exact transcript payload:

```bash
python3 - <<'PY' "$SESSION_ARTIFACT" > "$SCRATCH_ROOT/task-input.json"
from pathlib import Path
import json
import re
import sys

text = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
match = re.search(r"<task_input_json>\s*(.*?)\s*</task_input_json>", text, flags=re.S)
if not match:
    raise SystemExit("task_input_json block not found")
payload = match.group(1).strip().encode("utf-8").decode("unicode_escape").strip()
json.loads(payload)
sys.stdout.write(payload + "\n")
PY
```

Render the real prompt:

```bash
python3 "$TRYCYCLE_ROOT/orchestrator/prompt_builder/build.py" \
  --template "$TRYCYCLE_ROOT/subagents/prompt-planning-edit.md" \
  --set "WORKTREE_PATH=$CLONE_DIR" \
  --set "IMPLEMENTATION_PLAN_PATH=$CLONE_DIR/$PLAN_RELPATH" \
  --set-file "USER_REQUEST_TRANSCRIPT=$SCRATCH_ROOT/task-input.json" \
  --require-nonempty-tag task_input_json \
  > "$SCRATCH_ROOT/prompt.md"
```

Dispatch the review:

```bash
codex exec --ephemeral --dangerously-bypass-approvals-and-sandbox --color never \
  -C "$CLONE_DIR" \
  -o "$SCRATCH_ROOT/final.md" \
  - < "$SCRATCH_ROOT/prompt.md"
```

For `issue_174_initial_plan_turn2`, run the same render-and-dispatch sequence a second time against the same clone after round 1, then stop and score.

## Scoring Rules Used

### Threshold cases

- `directordeck_provider_errors`: pass only if the reviewer says `ALREADY-EXCELLENT` and leaves the repo unchanged.
- `session_recency_contract`: same rule as DirectorDeck.

### Semantic-fix case

- `session_search_tier`: pass if the resulting plan fixes the actual contract:
  - `title` stays metadata-only
  - `userMessages` is file-backed user-message search
  - `fullText` is file-backed user + assistant search
  - no metadata fallback for file-backed tiers

Important manual-scoring note:

- Mentioning `firstUserMessage` in a negative clause or a backward-compatibility clause is not a failure by itself.
- This case produced false negatives when scored by naive keyword matching alone. Manual semantic review is required.

### Lazy-factor case

- `issue_174_initial_plan_turn2`: pass only if:
  - round 1 reaches the same substantive endpoint as the final correct historical plan
  - round 2 returns `ALREADY-EXCELLENT`
  - round 2 creates no new commit and edits no files

The critical round-1 decisions are:

- treat the bug as a compiled-start boundary problem, not a source-only cleanup
- recognize that the preferred `process.cwd()` product fix already exists
- extend the existing `TestServer`
- stage the runtime root under the worktree
- avoid symlink-based staging
- keep product-code changes conditional on the new regression still proving a real bug
- prove `.env` placement and authenticated startup behavior at the compiled boundary

## Results

### Summary

- Control score: `1/4`
- Candidate score: `1/4`
- Net result: no measured improvement from this candidate prompt revision

### Case-by-Case Outcome

| Case | Control (`main`) | Candidate (worktree) | Interpretation |
| --- | --- | --- | --- |
| `directordeck_provider_errors` | Fail: `MADE-EXCELLENT`, commit `62f6a704` | Fail: `MADE-EXCELLENT`, commit `16e069f3` | No improvement. Both versions still rewrote an already-excellent plan. |
| `session_search_tier` | Pass after manual review: `MADE-EXCELLENT`, commit `fcbd8b13` | Pass after manual review: `MADE-EXCELLENT`, commit `0f6b9d43` | No meaningful change. Both versions repaired the semantic defect. |
| `session_recency_contract` | Fail: `MADE-EXCELLENT`, commit `34ee135d` | Fail: `MADE-EXCELLENT`, commit `2dde8978` | No improvement. Both versions still over-reviewed a plan that had crossed the execution-ready threshold. |
| `issue_174_initial_plan_turn2` | Fail: round 1 `b0fd3b0a`, round 2 `9762fffd`, both `MADE-EXCELLENT` | Fail: round 1 `ab60f0b6`, round 2 `fa72c376`, both `MADE-EXCELLENT` | Slight directional improvement in wording, but still not enough. The candidate still needed a second rewrite and did not converge by round 2. |

## What Was Learned

- The candidate prompt revision did not change the measured pass rate.
- The two threshold failures are still the same:
  - plans that are already good enough still get rewritten
  - plans that have crossed the execution-ready threshold still get repartitioned
- The lazy-factor failure is also still present:
  - the reviewer still does not catch all real problems on the first pass
  - the second pass still rewrites instead of confirming
- `session_search_tier` is still useful, but only if it is scored semantically by a human. A simplistic keyword-based scorer will mislabel good outputs as failures.

## How To Repeat This Experiment Safely

- If you care about exact candidate reproduction, commit or snapshot the prompt files before rerunning.
- This specific candidate is now snapshotted at trycycle commit `e78fc9d`.
- Record the exact trycycle prompt path, repo commit, CLI version, model, and source transcript artifact for every arm.
- Save, at minimum, these artifacts for each run:
  - rendered prompt
  - final markdown report
  - final plan text
  - pre/post `HEAD`
  - score notes, especially any manual overrides
- Treat any rerun against a different model, different CLI version, different prompt text, or changed worktree state as a new experiment, not as the same data point.
