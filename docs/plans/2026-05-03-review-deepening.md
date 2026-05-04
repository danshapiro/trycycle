# Review Deepening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use trycycle-executing to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add same-agent review deepening after plan-editor and post-implementation reviewers find blocking issues, so Trycycle can harvest additional related findings before paying for another fresh reviewer round.

**Architecture:** Keep the existing fresh-reviewer loops intact, but add an intra-review deepening loop that resumes the same reviewer only after it has already found blocking issues. Add explicit follow-up prompt templates, deterministic review-observation accumulation, longer review-agent timeouts, and testing-time halt behavior when the deepening loop reaches 10 major-or-critical-producing passes. Do not change the `READY` / no-blocker path.

**Tech Stack:** Markdown orchestrator instructions, Trycycle prompt templates, Python 3 stdlib, `unittest`

---

## Design Decisions

### Deepening is not a fresh review round

A deepening pass belongs to the same plan-editor round or post-implementation review round that produced the first blocking findings. It should not increment the existing plan-editor round count or post-implementation review round count. The existing fresh reviewer loops remain the independent cross-check; deepening only exploits the current reviewer's warm context before closing it.

### Do not change the no-issue path

The user explicitly does not want a new "challenge READY" behavior. Therefore:

- if a plan editor returns `READY` on its normal first response, close it and proceed exactly as Trycycle does today
- if a post-implementation reviewer returns `blocking_issue_count: 0` on its normal first response, close it and proceed exactly as Trycycle does today
- deepening starts only after a reviewer has already returned a blocking result:
  - plan editor: `## Plan verdict` is `REVISED`
  - post-implementation reviewer: extracted `blocking_issue_count > 0`

### The follow-up response is a delta

The follow-up prompt must briefly restate the already-shared output contract and ask for additional findings only. This is not because the reviewer is expected to duplicate findings; it is so the orchestrator can treat each follow-up response as a deterministic delta and accumulate it without guessing whether the response is a restatement or a replacement.

### Halt at 10 deepening passes while testing

During this feature's testing period, if the same reviewer produces a 10th deepening response that still contains any `critical` or `major` finding, Trycycle must halt and surface the unexpected condition to the user. Do not hand the accumulated findings to execution at that point. Include the accumulated reply paths, observation paths, combined observation artifact if available, the active review agent/session identifier if available, and the latest response. Keep the same review agent/session available where the host supports it so the user can choose whether to continue.

Later, this policy can be changed to "hand accumulated findings to execution," but that is not part of this plan.

### Completed pass output must be saved before continuing

Every completed normal review response and every completed deepening response must be saved, extracted, and appended to the relevant artifact lists before sending the next deepening prompt. If a later deepening attempt times out, Trycycle should halt with all completed-pass artifacts preserved plus the timed-out attempt's runner artifacts. Partial in-progress output is not reliable enough to parse as findings.

### Post-implementation findings need a combined artifact

`orchestrator/review_observations.py extract` validates one reviewer response at a time. After post-implementation deepening produces multiple response artifacts, the implementation subagent and plan-reconsideration checkpoint need a single observation JSON containing the accumulated findings from the full review round. Add a small combine command to `review_observations.py` that reads normalized extraction outputs and writes a combined normalized output.

The combined output should renumber observations as `R1`, `R2`, ... in encounter order and preserve all other observation fields. This avoids duplicate IDs from independent delta responses without pretending to deduplicate semantic findings.

### Plan-editor deepening revises the plan but does not make the outer round READY

If a plan-editor's initial response is `REVISED`, run deepening on the same planning subagent. A deepening response may return `REVISED` and further update the plan, or `READY` to say no additional critical plan issues were found. Even if the final deepening response is `READY`, the outer plan-editor round still counts as `REVISED` because the plan changed during that round. Close the same planning subagent after deepening completes and start the next existing fresh plan-editor round.

## File Structure

- Modify: `SKILL.md`
  - Add plan-editor deepening after `REVISED` reports only.
  - Add post-implementation review deepening after `blocking_issue_count > 0` only.
  - Make native mode and fallback-runner mode capture every completed deepening response before the next prompt.
  - Add 10-pass halt behavior for deepening loops.
  - Update monitor windows for plan-editor and post-implementation review/deepening to 180 minutes.
- Create: `subagents/prompt-planning-edit-deepen.md`
  - Same-agent follow-up prompt for additional critical plan issues after a `REVISED` plan-editor report.
- Create: `subagents/prompt-post-impl-review-deepen.md`
  - Same-agent follow-up prompt for additional post-implementation observations after a blocking review report.
- Modify: `orchestrator/review_observations.py`
  - Add a `combine` subcommand for normalized observation JSON artifacts.
- Create: `tests/test_review_observations.py`
  - Cover extraction and combined observation behavior with repeated original IDs and no-issue deltas.
- Modify: `orchestrator/subagent_runner.py`
  - Add explicit 180-minute timeout defaults for `planning-edit`, `planning-edit-deepen`, `post-implementation-review`, and `post-implementation-review-deepen`.
- Modify: `tests/test_subagent_runner.py`
  - Add direct timeout-default coverage for review/deepening phases and unchanged 60-minute defaults for unrelated phases.

---

### Task 1: Add Review Observation Combination

**Files:**
- Modify: `orchestrator/review_observations.py`
- Create: `tests/test_review_observations.py`

- [ ] **Step 1: Write failing tests for combined review observations**

Create `tests/test_review_observations.py` with a `ReviewObservationsTests` class. Use `tempfile.TemporaryDirectory`, `subprocess.run`, and `json` to exercise the CLI through the real script path:

```python
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
REVIEW_OBSERVATIONS = REPO_ROOT / "orchestrator" / "review_observations.py"


def _run_review_observations(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(REVIEW_OBSERVATIONS), *args],
        text=True,
        capture_output=True,
        check=False,
    )


def _reply(observations: list[dict], *, status: str = "issues_found") -> str:
    payload = {
        "status": status,
        "summary": "summary",
        "observations": observations,
    }
    return (
        "<review_observations_json>"
        + json.dumps(payload)
        + "</review_observations_json>\n"
    )
```

Add `test_combine_renumbers_accumulated_observations_and_counts_blockers`:

```python
def test_combine_renumbers_accumulated_observations_and_counts_blockers(self) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        reply1 = tmp_path / "reply1.txt"
        reply2 = tmp_path / "reply2.txt"
        obs1 = tmp_path / "obs1.json"
        obs2 = tmp_path / "obs2.json"
        combined = tmp_path / "combined.json"

        base_observation = {
            "id": "R1",
            "severity": "critical",
            "category": "correctness",
            "expected": "first expected",
            "observed": "first observed",
            "where": {"file": "src/a.py", "line": 10},
            "evidence": {"commands": ["pytest"], "notes": "first evidence"},
        }
        second_observation = {
            "id": "R1",
            "severity": "major",
            "category": "missing_test",
            "expected": "second expected",
            "observed": "second observed",
            "where": {"file": "tests/test_a.py", "line": 20},
            "evidence": {"commands": ["pytest tests/test_a.py"], "notes": "second evidence"},
        }
        reply1.write_text(_reply([base_observation]), encoding="utf-8")
        reply2.write_text(_reply([second_observation]), encoding="utf-8")

        self.assertEqual(
            _run_review_observations("extract", "--reply", str(reply1), "--output", str(obs1)).returncode,
            0,
        )
        self.assertEqual(
            _run_review_observations("extract", "--reply", str(reply2), "--output", str(obs2)).returncode,
            0,
        )

        result = _run_review_observations(
            "combine",
            "--output",
            str(combined),
            str(obs1),
            str(obs2),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(combined.read_text(encoding="utf-8"))
        self.assertEqual(payload["status"], "issues_found")
        self.assertEqual(payload["issue_count"], 2)
        self.assertEqual(payload["blocking_issue_count"], 2)
        self.assertEqual([item["id"] for item in payload["observations"]], ["R1", "R2"])
        self.assertEqual(payload["observations"][0]["expected"], "first expected")
        self.assertEqual(payload["observations"][1]["expected"], "second expected")

        stdout_payload = json.loads(result.stdout)
        self.assertEqual(stdout_payload["status"], "ok")
        self.assertEqual(stdout_payload["observations_path"], str(combined.resolve()))
        self.assertTrue(stdout_payload["has_blocking_issues"])
```

Add `test_combine_all_no_issue_artifacts_returns_no_issues`:

```python
def test_combine_all_no_issue_artifacts_returns_no_issues(self) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        reply_path = tmp_path / "reply.txt"
        obs_path = tmp_path / "obs.json"
        combined = tmp_path / "combined.json"
        reply_path.write_text(_reply([], status="no_issues"), encoding="utf-8")

        extract = _run_review_observations(
            "extract", "--reply", str(reply_path), "--output", str(obs_path)
        )
        self.assertEqual(extract.returncode, 0, extract.stderr)

        result = _run_review_observations("combine", "--output", str(combined), str(obs_path))

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(combined.read_text(encoding="utf-8"))
        self.assertEqual(payload["status"], "no_issues")
        self.assertEqual(payload["observations"], [])
        self.assertEqual(payload["issue_count"], 0)
        self.assertEqual(payload["blocking_issue_count"], 0)
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run:

```bash
python3 -m unittest tests.test_review_observations -v
```

Expected: FAIL with an argparse error because `combine` is not a valid subcommand.

- [ ] **Step 3: Implement the `combine` subcommand**

In `orchestrator/review_observations.py`, add:

```python
def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExtractionError(f"could not read observations JSON file: {path}") from exc
    if not isinstance(payload, dict):
        raise ExtractionError(f"observations JSON root must be an object: {path}")
    return payload
```

Add a helper:

```python
def combine_payloads(payloads: list[dict[str, Any]]) -> dict[str, Any]:
    observations: list[dict[str, Any]] = []
    summaries: list[str] = []
    for payload in payloads:
        normalized = normalize_payload(payload)
        if normalized["summary"]:
            summaries.append(normalized["summary"])
        for observation in normalized["observations"]:
            copied = dict(observation)
            copied["id"] = f"R{len(observations) + 1}"
            observations.append(copied)

    combined = {
        "status": "issues_found" if observations else "no_issues",
        "summary": " | ".join(summaries),
        "observations": observations,
    }
    return normalize_payload(combined)
```

Add:

```python
def combine_command(args: argparse.Namespace) -> int:
    input_paths = [Path(raw).resolve() for raw in args.inputs]
    output_path = Path(args.output).resolve()
    payloads = [_read_json(path) for path in input_paths]
    combined = combine_payloads(payloads)
    _write_json(output_path, combined)
    result = {
        "status": "ok",
        "observations_path": str(output_path),
        "issue_count": combined["issue_count"],
        "blocking_issue_count": combined["blocking_issue_count"],
        "has_blocking_issues": combined["blocking_issue_count"] > 0,
        "review_status": combined["status"],
    }
    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0
```

Register the subcommand in `build_parser()`:

```python
combine = subparsers.add_parser(
    "combine",
    help="Combine normalized review observation JSON files into one normalized artifact.",
)
combine.add_argument("--output", required=True, help="Path to write combined observations JSON.")
combine.add_argument("inputs", nargs="+", help="Normalized observation JSON files from extract.")
combine.set_defaults(func=combine_command)
```

Do not deduplicate semantic findings. The follow-up prompt makes each response a delta; the helper should only renumber IDs and recalculate counts.

- [ ] **Step 4: Run the review observation tests to verify they pass**

Run:

```bash
python3 -m unittest tests.test_review_observations -v
```

Expected: PASS.

- [ ] **Step 5: Commit the observation-combine change**

Run:

```bash
git add orchestrator/review_observations.py tests/test_review_observations.py
git commit -m "test: combine review observation passes"
```

Expected: commit succeeds.

---

### Task 2: Add Deepening Prompt Templates

**Files:**
- Create: `subagents/prompt-post-impl-review-deepen.md`
- Create: `subagents/prompt-planning-edit-deepen.md`

- [ ] **Step 1: Create the post-implementation review deepening prompt**

Create `subagents/prompt-post-impl-review-deepen.md`:

```markdown
Good finds. Search for additional issues, as there may be more.

Use the same review target, severity standard, evidence requirements, and JSON schema from your current instructions. Return exactly one `<review_observations_json>...</review_observations_json>` block and no prose. Report only additional observations not already reported in this thread. If you find additional issues, set `status` to `"issues_found"` and include them in `observations`. If you find no additional issues, set `status` to `"no_issues"` with an empty `observations` array.
```

- [ ] **Step 2: Create the plan-editor deepening prompt**

Create `subagents/prompt-planning-edit-deepen.md`:

```markdown
Good finds. Search for additional plan issues, as there may be more.

Use the same task input, current plan, critical-issue standard, workspace, and report contract from your current instructions. Report only additional critical issues not already reported in this thread.

If you find additional critical issues, revise the plan to fix them, commit, and return the same markdown sections in the same order, listing only the additional issues from this pass in `## Critical issues`.

If you find no additional critical issues, do not modify files and return the same markdown sections in the same order with `## Plan verdict` set to `READY` and `## Critical issues` set to `None`.
```

- [ ] **Step 3: Validate both templates render through the phase wrapper**

Run:

```bash
python3 orchestrator/run_phase.py prepare \
  --phase post-implementation-review-deepen \
  --template subagents/prompt-post-impl-review-deepen.md \
  --workdir "$(pwd)"

python3 orchestrator/run_phase.py prepare \
  --phase planning-edit-deepen \
  --template subagents/prompt-planning-edit-deepen.md \
  --workdir "$(pwd)"
```

Expected: both commands return JSON with `status: "prepared"` and a `prompt_path`. Inspect each rendered `prompt_path`; there should be no unresolved Trycycle placeholders such as `{WORKTREE_PATH}`.

- [ ] **Step 4: Commit the deepening prompt templates**

Run:

```bash
git add subagents/prompt-post-impl-review-deepen.md subagents/prompt-planning-edit-deepen.md
git commit -m "docs: add same-reviewer deepening prompts"
```

Expected: commit succeeds.

---

### Task 3: Raise Review-Agent Timeout Defaults

**Files:**
- Modify: `orchestrator/subagent_runner.py`
- Modify: `tests/test_subagent_runner.py`

- [ ] **Step 1: Add failing unit coverage for review phase timeout defaults**

Append a new `SubagentRunnerTimeoutDefaultsTests` class near the existing pure unit tests in `tests/test_subagent_runner.py`:

```python
class SubagentRunnerTimeoutDefaultsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(ORCHESTRATOR_ROOT))
        import subagent_runner  # type: ignore

        cls._default_timeout_seconds_for_phase = staticmethod(
            subagent_runner._default_timeout_seconds_for_phase
        )

    def test_review_and_deepening_phases_use_execution_timeout(self) -> None:
        for phase in (
            "executing",
            "planning-edit",
            "planning-edit-deepen",
            "post-implementation-review",
            "post-implementation-review-deepen",
        ):
            with self.subTest(phase=phase):
                self.assertEqual(self._default_timeout_seconds_for_phase(phase), 3 * 60 * 60)

    def test_unrelated_phases_keep_default_timeout(self) -> None:
        for phase in (
            "planning-initial",
            "test-plan",
            "planning-reconsider",
            "nonconvergence-review",
            "smoke",
        ):
            with self.subTest(phase=phase):
                self.assertEqual(self._default_timeout_seconds_for_phase(phase), 60 * 60)
```

- [ ] **Step 2: Run the timeout tests and verify they fail**

Run:

```bash
python3 -m unittest tests.test_subagent_runner.SubagentRunnerTimeoutDefaultsTests -v
```

Expected: FAIL because the review phases still return `60 * 60`.

- [ ] **Step 3: Implement review timeout phase defaults**

In `orchestrator/subagent_runner.py`, replace:

```python
DEFAULT_TIMEOUT_SECONDS = 60 * 60
EXECUTING_TIMEOUT_SECONDS = 3 * 60 * 60
```

with:

```python
DEFAULT_TIMEOUT_SECONDS = 60 * 60
LONG_RUNNING_AGENT_TIMEOUT_SECONDS = 3 * 60 * 60
LONG_RUNNING_AGENT_PHASES = {
    "executing",
    "planning-edit",
    "planning-edit-deepen",
    "post-implementation-review",
    "post-implementation-review-deepen",
}
```

Then update `_default_timeout_seconds_for_phase`:

```python
def _default_timeout_seconds_for_phase(phase: str) -> int:
    if phase in LONG_RUNNING_AGENT_PHASES:
        return LONG_RUNNING_AGENT_TIMEOUT_SECONDS
    return DEFAULT_TIMEOUT_SECONDS
```

Search for `EXECUTING_TIMEOUT_SECONDS` and replace any remaining references with `LONG_RUNNING_AGENT_TIMEOUT_SECONDS` or remove them if unused.

- [ ] **Step 4: Run the timeout tests to verify they pass**

Run:

```bash
python3 -m unittest tests.test_subagent_runner.SubagentRunnerTimeoutDefaultsTests -v
```

Expected: PASS.

- [ ] **Step 5: Commit the timeout default change**

Run:

```bash
git add orchestrator/subagent_runner.py tests/test_subagent_runner.py
git commit -m "test: extend review agent timeouts"
```

Expected: commit succeeds.

---

### Task 4: Add Plan-Editor Deepening to the Orchestrator Instructions

**Files:**
- Modify: `SKILL.md`

- [ ] **Step 1: Update the plan-editor timeout text**

In `SKILL.md` Step 7, change the plan-editor monitor text at the current `Monitor by checking every 5 minutes until 60 minutes have passed` line to 180 minutes:

```markdown
Monitor by checking every 5 minutes until 180 minutes have passed. Then, and only then, kill it and retry.
```

Leave planning-initial, test-plan, planning-reconsider, and nonconvergence-review timeout text at 60 minutes.

- [ ] **Step 2: Replace the current plan-editor post-round steps with deepening-aware steps**

In `SKILL.md` Step 7, replace the current "After each edit round" list with instructions equivalent to:

```markdown
After each edit round:
1. Wait for the planning subagent to return either an updated planning report containing `## Plan verdict`, `## Critical issues`, `## Plan path`, `## Commit`, and `## Changed files`, or a report beginning with `USER DECISION REQUIRED:`.
2. If the planning subagent returns `USER DECISION REQUIRED:`, present that question to the user, send the user's answer back to that active planning subagent, and wait again for either an updated planning report or another `USER DECISION REQUIRED:` report. Monitor by checking every 5 minutes until 180 minutes have passed. Then, and only then, kill it and retry.
3. Update `{IMPLEMENTATION_PLAN_PATH}` from `## Plan path` in the latest planning report.
4. Run the workspace hygiene gate checks and verify the latest commit hash plus changed-file list match the planning subagent's report.
5. Start a loop outputs temp file if needed, save the returned planning report to a temp file, and append that path.
6. If `## Plan verdict` is `READY`, close that planning subagent for the completed round, clear any saved handle or `session_id`, and continue to step 8 with the current `{IMPLEMENTATION_PLAN_PATH}`. Do not run deepening after a `READY` verdict.
7. If `## Plan verdict` is `REVISED`, run the same-agent plan-editor deepening loop below before closing the planning subagent. After deepening completes without hitting the cap, close that planning subagent for the completed round, clear any saved handle or `session_id`, and repeat Step 7 with a fresh planning subagent. The outer plan-editor round still counts as `REVISED` even if the final deepening response is `READY`, because the plan changed during this round.
8. Repeat up to 5 fresh plan-editor rounds.
```

- [ ] **Step 3: Add the same-agent plan-editor deepening loop**

Immediately after the "After each edit round" list, add:

```markdown
Same-agent plan-editor deepening loop:
1. Set the plan-editor deepening count to 0 for this planning subagent.
2. Prepare the `planning-edit-deepen` phase via the phase wrapper using template `<skill-directory>/subagents/prompt-planning-edit-deepen.md`, `--set WORKTREE_PATH={WORKTREE_PATH}`, and `--set IMPLEMENTATION_PLAN_PATH={IMPLEMENTATION_PLAN_PATH}`. Append the returned `prompt_path` to the phase prompt paths temp file.
3. In native mode, send the exact returned `prompt_path` contents verbatim to the same active planning subagent. In fallback-runner mode, resume the same planning session through `python3 <skill-directory>/orchestrator/subagent_runner.py resume` using that planning dispatch's saved `session_id`, its resolved backend, the wrapper-prepared `prompt_path`, and phase `planning-edit-deepen`.
4. Monitor by checking every 5 minutes until 180 minutes have passed. Then, and only then, kill it and halt this Trycycle run as an unexpected deepening timeout. Surface all completed planning report paths, the timed-out attempt artifacts if available, and the active planning session id if available. Await user instructions before taking any further action.
5. Wait for either a report containing `## Plan verdict`, `## Critical issues`, `## Plan path`, `## Commit`, and `## Changed files`, or a report beginning with `USER DECISION REQUIRED:`.
6. If the planning subagent returns `USER DECISION REQUIRED:`, present that question to the user, send the user's answer back to that same active planning subagent, and wait again for either an updated planning report or another `USER DECISION REQUIRED:` report. Monitor by checking every 5 minutes until 180 minutes have passed. Then, and only then, kill it and halt with the completed planning report paths and timed-out attempt artifacts.
7. Save the completed deepening report to a temp file immediately and append that path to the loop outputs temp file before sending any further prompt.
8. Update `{IMPLEMENTATION_PLAN_PATH}` from `## Plan path`, then run the workspace hygiene gate checks and verify the latest commit hash plus changed-file list match the planning subagent's report.
9. If `## Plan verdict` is `READY`, the same reviewer has found no additional critical plan issues. End this same-agent deepening loop.
10. If `## Plan verdict` is `REVISED`, increment the plan-editor deepening count.
11. If the plan-editor deepening count is 10, halt this Trycycle run as an unexpected deepening cap. Do not proceed to test-plan building and do not start another fresh plan-editor round. Surface the latest planning report plus all completed planning report paths and await user instructions.
12. If the plan-editor deepening count is less than 10, repeat this same-agent plan-editor deepening loop.
```

Make sure the step says "halt" at the cap, not "hand to execution."

- [ ] **Step 4: Verify no READY challenge path was introduced**

Run:

```bash
rg -n "READY.*deepen|deepening after a `READY`|Do not run deepening after a `READY`" SKILL.md
```

Expected: the only READY-related deepening text should say not to run deepening after a normal `READY` verdict, and that a deepening `READY` only ends the same-agent deepening loop.

- [ ] **Step 5: Commit the plan-editor orchestration change**

Run:

```bash
git add SKILL.md
git commit -m "docs: deepen revised plan reviews"
```

Expected: commit succeeds.

---

### Task 5: Add Post-Implementation Review Deepening to the Orchestrator Instructions

**Files:**
- Modify: `SKILL.md`

- [ ] **Step 1: Update post-implementation review timeout text**

In `SKILL.md` Step 10, change the normal post-implementation review monitor line from 60 minutes to 180 minutes:

```markdown
Monitor by checking every 5 minutes until 180 minutes have passed. Then, and only then, kill it and retry.
```

Do not change the implementation fix-round timeout; it already uses 180 minutes.

- [ ] **Step 2: Replace the single-response review extraction flow with a per-pass accumulation flow**

In Step 10, replace the current text beginning with "Use the review subagent's output as the fix-loop input" through the review-history append instructions with deepening-aware instructions equivalent to:

```markdown
Use the review subagent's completed output as the first review-pass input. Keep that same review subagent open until either:
- the normal first response has no blocking issues,
- same-agent deepening completes without additional blocking issues,
- the 10-pass deepening cap is hit,
- a timeout or extraction failure requires halting,
- or the reviewer asks for `USER DECISION REQUIRED:`.

After every completed review pass, including the normal first response and every deepening response:
1. Save the reviewer's raw stdout to a temp file immediately.
2. Extract a structured review-observations artifact from that saved reply.
3. Append the review reply path and extracted review-observations path to the loop outputs temp file.
4. Append the completed review pass number, raw stdout, and normalized review-observations JSON to `{REVIEW_LOOP_HISTORY}` under the current post-implementation review round before sending any further prompt.
```

Keep the existing `review_observations.py extract` command block and extraction-failure behavior, but update the surrounding text so it applies to each pass rather than only one round output.

- [ ] **Step 3: Add the post-implementation same-agent deepening loop**

After the per-pass extraction instructions, add:

```markdown
If the normal first review response has `blocking_issue_count: 0`, do not run deepening. Close the completed review subagent and clear any saved handle or `session_id`.

If any completed review pass has `blocking_issue_count > 0`, run same-agent post-implementation review deepening before deciding the fix-loop input:
1. Set the post-implementation review deepening count to 0 for this review subagent.
2. Prepare the `post-implementation-review-deepen` phase via the phase wrapper using template `<skill-directory>/subagents/prompt-post-impl-review-deepen.md`. Append the returned `prompt_path` to the phase prompt paths temp file.
3. In native mode, send the exact returned `prompt_path` contents verbatim to the same active review subagent. In fallback-runner mode, resume the same review session through `python3 <skill-directory>/orchestrator/subagent_runner.py resume` using that review dispatch's saved `session_id`, its resolved backend, the wrapper-prepared `prompt_path`, and phase `post-implementation-review-deepen`.
4. Monitor by checking every 5 minutes until 180 minutes have passed. Then, and only then, kill it and halt this Trycycle run as an unexpected deepening timeout. Surface all completed review reply paths, extracted observation paths, the timed-out attempt artifacts if available, and the active review session id if available. Await user instructions before taking any further action.
5. Save and extract the completed deepening response immediately, append its reply path and observation path to the loop outputs temp file, and append the pass to `{REVIEW_LOOP_HISTORY}` before sending any further prompt.
6. If extraction fails, stop and surface the review reply plus the extractor failure to the user rather than guessing.
7. If the deepening response has `blocking_issue_count: 0`, the same reviewer has found no additional critical or major issues. End this same-agent deepening loop.
8. If the deepening response has `blocking_issue_count > 0`, increment the post-implementation review deepening count.
9. If the post-implementation review deepening count is 10, halt this Trycycle run as an unexpected deepening cap. Do not dispatch an implementation fix round, do not run plan reconsideration, and do not start another fresh review round. Surface the latest review output plus all completed review reply paths and extracted observation paths, and await user instructions.
10. If the post-implementation review deepening count is less than 10, repeat this same-agent post-implementation review deepening loop.
```

The counter intentionally counts completed deepening responses that contain `critical` or `major` observations. A final `no_issues` response stops the loop and is not counted toward the cap.

- [ ] **Step 4: Combine extracted observations before downstream decisions**

After the deepening loop text, add:

````markdown
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

Use this combined review-round observation artifact anywhere Step 10 previously used the latest extracted review-observations artifact, including:
- stop condition checks
- plan reconsideration `{POST_IMPLEMENTATION_REVIEW_OBSERVATIONS_JSON}`
- implementation fix-round `{POST_IMPLEMENTATION_REVIEW_OBSERVATIONS_JSON}`
- nonconvergence evidence
````

Because this is nested inside Markdown, escape or adjust the inner fenced command block correctly when editing `SKILL.md`.

- [ ] **Step 5: Preserve existing post-review cadence and semantics**

Verify the edited Step 10 still says:

- plan reconsideration cadence is based on completed fresh post-implementation review rounds, not deepening passes
- stop point is still 8 completed fresh review rounds by default
- implementation fixes still receive only `critical` and `major` observations as required targets
- minor and nit observations remain non-required fix targets

Run:

```bash
rg -n "completed review round|deepening|blocking_issue_count|critical.*major|minor.*nit|combine" SKILL.md
```

Expected: the output confirms the above concepts are present.

- [ ] **Step 6: Commit the post-implementation orchestration change**

Run:

```bash
git add SKILL.md
git commit -m "docs: deepen blocking implementation reviews"
```

Expected: commit succeeds.

---

### Task 6: Run Full Verification and Review the Final Diff

**Files:**
- Verify all changed files from prior tasks

- [ ] **Step 1: Run focused Python tests**

Run:

```bash
python3 -m unittest tests.test_review_observations -v
python3 -m unittest tests.test_subagent_runner.SubagentRunnerTimeoutDefaultsTests -v
```

Expected: both commands PASS.

- [ ] **Step 2: Run the full repository test suite**

Run:

```bash
python3 -m unittest discover tests -v
```

Expected: PASS. If live tests are skipped because their opt-in environment variables are unset, that is acceptable for the repository's existing live-test convention. Do not skip or weaken deterministic tests.

- [ ] **Step 3: Validate both new prompt templates still render**

Run:

```bash
python3 orchestrator/run_phase.py prepare \
  --phase post-implementation-review-deepen \
  --template subagents/prompt-post-impl-review-deepen.md \
  --workdir "$(pwd)"

python3 orchestrator/run_phase.py prepare \
  --phase planning-edit-deepen \
  --template subagents/prompt-planning-edit-deepen.md \
  --workdir "$(pwd)"
```

Expected: both commands return JSON with `status: "prepared"` and no unresolved placeholders in the rendered prompt files.

- [ ] **Step 4: Review the final diff for policy regressions**

Run:

```bash
git diff --stat main...HEAD
git diff main...HEAD -- SKILL.md subagents/prompt-post-impl-review-deepen.md subagents/prompt-planning-edit-deepen.md orchestrator/review_observations.py orchestrator/subagent_runner.py tests/test_review_observations.py tests/test_subagent_runner.py
```

Check the diff manually for:

- no deepening after normal `READY` / no-blocker responses
- deepening only resumes the same reviewer/planning subagent
- 10-pass cap halts and awaits user instructions
- no "hand to execution at cap" behavior
- completed deepening outputs are saved and extracted before further prompts
- combined post-implementation observations drive downstream fix and reconsideration steps
- no new fallbacks that hide errors

- [ ] **Step 5: Commit any final corrections**

If Step 4 finds wording or implementation mistakes, fix them and commit:

```bash
git add <changed-files>
git commit -m "fix: tighten review deepening flow"
```

If there are no corrections, do not create an empty commit.

- [ ] **Step 6: Report completion facts**

Run:

```bash
git status --short
git rev-parse --short HEAD
git diff --name-only main...HEAD
```

Expected:

- `git status --short` is clean
- changed files are limited to:
  - `SKILL.md`
  - `orchestrator/review_observations.py`
  - `orchestrator/subagent_runner.py`
  - `subagents/prompt-planning-edit-deepen.md`
  - `subagents/prompt-post-impl-review-deepen.md`
  - `tests/test_review_observations.py`
  - `tests/test_subagent_runner.py`

Report the final `HEAD`, changed files, and test results to the user.
