# Add Kimi CLI Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use trycycle-executing to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add first-class Kimi CLI support to trycycle's existing transcript-adapter and fallback-runner paths so Trycycle can run under Kimi without introducing a second orchestration architecture.

**Architecture:** Extend the three existing seams that already carry Codex and Claude support: `user-request-transcript/build.py` gets a Kimi adapter, `run_phase.py` accepts explicit Kimi transcript/backend choices and launches transcript lookup from the phase `--workdir`, and `subagent_runner.py` gets a Kimi print-mode backend with robust success validation. Update `SKILL.md` to use explicit `--transcript-cli kimi-cli` and `--backend kimi` when the host agent is Kimi, because Kimi does not expose a reliable host marker for `auto` detection. Keep the implementation small and local; do not add a separate Kimi-native subagent orchestration path.

**Tech Stack:** Python 3 stdlib, `unittest`, Markdown docs, real `kimi` CLI smoke commands

---

## Design decisions

### Reuse the existing adapter and fallback-runner seams

Kimi support belongs in the same extension points Codex and Claude already use:

- transcript extraction in `orchestrator/user-request-transcript/`
- phase preparation and CLI surface in `orchestrator/run_phase.py`
- fallback probe/run/resume in `orchestrator/subagent_runner.py`

Do **not** add a Kimi-specific orchestration mode, `Task`-tool integration, or another dispatch pipeline. The user asked for minimal changes and reuse, and these seams are already the repo's steady-state contract.

### Support explicit Kimi flags; do not promise reliable `auto` host detection

Keep `auto` detection behavior conservative:

- `run_phase.py --transcript-cli auto` stays Codex/Claude-only
- `subagent_runner.py --backend auto` adds Kimi only as a fallback candidate after Codex/Claude

Do **not** add a "detect Kimi host" branch. In local inspection, Kimi does not expose a stable environment marker analogous to `CODEX_THREAD_ID` or `CLAUDECODE`, and this machine already has unrelated `KIMI_*` variables in a non-Kimi session. The correct fix is to update `SKILL.md` so that when the host is Kimi it passes explicit `--transcript-cli kimi-cli` and `--backend kimi`.

This gives correct behavior in real Trycycle usage without inventing brittle heuristics.

### Kimi transcript lookup uses `kimi.json` plus top-level session context files, not `kimi export`

Direct lookup should read:

- `KIMI_SHARE_DIR` when set, otherwise `~/.kimi`
- `<share-root>/kimi.json` for `work_dirs[].last_session_id`
- `<share-root>/sessions/<md5(workdir)>/<session-id>/context.jsonl`
- if needed, the most recent top-level `context*.jsonl` file in that same session directory, excluding `context_sub_*.jsonl`

Fallback canary lookup must search only top-level transcript files under `<share-root>/sessions`, not every `*.jsonl`. In real Kimi session directories, `wire.jsonl` and `context_sub_*.jsonl` are present and can contain the same canary text, but they are not the top-level user transcript Trycycle needs.

Do **not** use `kimi export` in the implementation. Trycycle only needs the current session transcript, and the on-disk files are the direct source of truth with fewer moving parts.

### Kimi transcript lookup must be anchored to the phase `--workdir`, not the caller's cwd

Direct Kimi lookup keys off the current worktree path recorded in `kimi.json`. `run_phase.py` currently launches the transcript builder in the caller's cwd, which is not guaranteed to equal `--workdir` during normal Trycycle execution.

The wrapper must therefore invoke transcript lookup with `cwd=Path(args.workdir).resolve()` so Kimi direct lookup tracks the implementation workspace, not wherever the orchestrator happened to be launched from.

### Kimi runner success is validated against session context, not exit code alone

Observed Kimi behavior can exit `0` while printing a config/auth error such as `LLM not set`. The runner must not classify that as success.

For Kimi, success should require all of the following:

- exit code `0`
- non-empty printed reply
- the Kimi session context for the dispatched `session_id` contains a visible final assistant turn whose text matches the printed reply after normalizing line endings and trimming the single trailing newline added by print mode

This is stronger than string-matching error messages and more precise than checking `kimi.json` alone:

- it catches the known zero-exit false-success case
- it works for both fresh runs and resumes
- it validates the persisted session content Trycycle will rely on later

When validation fails, the runner should return `status: "escalate_to_user"` and surface the actual printed text (for example `LLM not set`) instead of the misleading generic message `kimi exited with code 0.`

### Resume uses explicit `--session`, not `--continue`

Trycycle already persists the session id returned by the runner. Resume should therefore use:

```bash
kimi --print --final-message-only --session <saved-session-id> ...
```

Do **not** use `--continue` inside the runner. `--continue` depends on global workdir metadata; explicit `--session` is deterministic and aligns with the existing Codex/Claude runner contract.

### Map Trycycle effort hints onto Kimi's boolean thinking mode

Kimi does not expose multi-level reasoning effort. Keep the existing `--effort` CLI surface and map it as follows:

- `low` -> `--no-thinking`
- `medium`, `high`, `max` -> `--thinking`

This keeps the public runner interface unchanged and makes Trycycle's existing `--effort max` usage do the right thing under Kimi.

### Kimi probe must tolerate rich-help formatting

`kimi --help` on the installed `1.24.0` binary exposes the needed functionality, but its rich table formatting truncates long option names such as `--final-message-only`. Do **not** probe Kimi by requiring that exact full token to appear verbatim in help output.

Probe for stable evidence instead:

- exact tokens that are rendered in full, such as `--print`, `--session`, `--continue`, and `--work-dir`
- plus either the phrase `final assistant` from the help description or another stable indicator for final-message-only support

### Update docs narrowly

Documentation changes should be limited to what becomes untrue without them:

- `SKILL.md` must tell Kimi-hosted Trycycle to pass explicit Kimi wrapper flags
- `README.md` must list Kimi as a supported host and include the Kimi skills install path

Do **not** add skill-content tests. The user explicitly allowed code-behavior tests, but skill contents remain out of bounds for committed tests in this task.

## File structure

- Create: `orchestrator/user-request-transcript/kimi_cli.py`
  - Kimi transcript adapter: share-root resolution, direct current-session lookup, canary lookup, and transcript extraction.
- Modify: `orchestrator/user-request-transcript/build.py`
  - Register `kimi-cli` in the adapter map and CLI choices.
- Modify: `orchestrator/run_phase.py`
  - Accept explicit `--transcript-cli kimi-cli` and `--backend kimi`; keep `auto` conservative.
- Modify: `orchestrator/subagent_runner.py`
  - Add Kimi probe, command building, run/resume handling, effort mapping, reply capture, and Kimi-specific success validation.
- Modify: `tests/test_user_request_transcript_build.py`
  - Add deterministic Kimi transcript builder coverage.
- Modify: `tests/test_run_phase.py`
  - Add Kimi phase-preparation coverage and Kimi dry-run dispatch coverage using a fake `kimi` binary.
- Create: `tests/test_subagent_runner.py`
  - Add deterministic runner tests for Kimi probe/run/resume/failure normalization.
- Modify: `SKILL.md`
  - Add Kimi transcript-helper and fallback-runner guidance.
- Modify: `README.md`
  - Add Kimi to the support/install docs and repo topics comment.

## Strategy gate

- **Is this the right problem?** Yes. The missing support is in the shared orchestration seams, not in any one prompt or subskill. Fixing those seams lands real Kimi support across planning, execution, and review phases.
- **Is this the right architecture?** Yes. It keeps Trycycle's single architecture intact and adds Kimi as another backend/adapter pair, which is exactly how Codex and Claude are already modeled.
- **Could we do less?** We could add parser choices only, but that would still leave transcript extraction, false-success normalization, and user-facing skill instructions broken. That would not be real support.
- **Could we do more?** We could add Kimi-native subagents/agents orchestration or attempt universal `auto` detection. Both add complexity and rely on undocumented host signals. That is the wrong steady-state answer for this request.

---

### Task 1: Add a Kimi transcript adapter and prove direct lookup plus canary fallback

**Files:**
- Create: `orchestrator/user-request-transcript/kimi_cli.py`
- Modify: `orchestrator/user-request-transcript/build.py`
- Modify: `tests/test_user_request_transcript_build.py`

- [ ] **Step 1: Extend the transcript builder tests with red Kimi cases**

Add two new tests to `tests/test_user_request_transcript_build.py` and any local helper functions they need:

```python
def test_kimi_direct_lookup_writes_output_file(self):
    ...

def test_kimi_canary_lookup_works_when_last_session_id_is_missing(self):
    ...
```

The fixtures should synthesize a temporary Kimi share root containing:

- `kimi.json`
- `sessions/<md5(workdir)>/<session-id>/context.jsonl`

The direct-lookup case should:

- run the builder from `cwd=workdir`
- set `--cli kimi-cli`
- pass `--search-root <fake-share-root>`
- assert the rendered JSON includes user and assistant turns
- assert assistant extraction ignores `{"type": "think"}` blocks and keeps only visible `{"type": "text"}` blocks

The canary case should set `last_session_id` to `null`, include the canary in the top-level `context.jsonl`, and also place the same canary in decoy files such as `wire.jsonl` and `context_sub_1.jsonl`. Assert the builder still falls back to the top-level transcript successfully so the test goes red if the implementation searches every `*.jsonl`.

- [ ] **Step 2: Run the transcript builder tests to verify they fail**

Run:

```bash
python3 -m unittest tests.test_user_request_transcript_build -v
```

Expected: FAIL because `build.py` does not accept `kimi-cli` and no Kimi adapter exists.

- [ ] **Step 3: Implement the Kimi transcript adapter**

Create `orchestrator/user-request-transcript/kimi_cli.py` with these responsibilities:

- resolve the share root from `search_root`, else `KIMI_SHARE_DIR`, else `Path.home() / ".kimi"`
- read `kimi.json` and find the current workdir entry by exact resolved cwd string
- locate the current session transcript at:
  - prefer `sessions/<md5(workdir)>/<session-id>/context.jsonl`
  - else fall back to the most recent top-level `context*.jsonl` in that session directory, excluding `context_sub_*.jsonl`
  - or legacy fallback `sessions/<md5(workdir)>/<session-id>.jsonl`
- implement canary lookup by searching only top-level transcript files under `<share-root>/sessions`:
  - include `context.jsonl`, `context_*.jsonl`, and any legacy `<session-id>.jsonl`
  - exclude `wire.jsonl`, `metadata.json`, and `context_sub_*.jsonl`
- extract transcript turns from `context.jsonl` with the same interval behavior as the existing adapters:
  - append each visible user turn
  - keep only the last non-empty visible assistant reply between user turns
  - ignore `_system_prompt`, `_checkpoint`, `_usage`, and assistant `think` blocks

Then register the adapter in `orchestrator/user-request-transcript/build.py`:

```python
import kimi_cli

ADAPTERS = {
    "claude-code": claude_code,
    "codex-cli": codex_cli,
    "kimi-cli": kimi_cli,
}
```

Do **not** change the builder's control flow. Reuse the existing `find_current_transcript` / `find_matching_transcripts` / `extract_transcript` protocol exactly.

- [ ] **Step 4: Run the transcript builder tests to verify they pass**

Run:

```bash
python3 -m unittest tests.test_user_request_transcript_build -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add orchestrator/user-request-transcript/kimi_cli.py orchestrator/user-request-transcript/build.py tests/test_user_request_transcript_build.py
git commit -m "feat: add kimi transcript adapter"
```

### Task 2: Accept explicit Kimi options in the phase wrapper

**Files:**
- Modify: `orchestrator/run_phase.py`
- Modify: `tests/test_run_phase.py`

- [ ] **Step 1: Extend the phase wrapper tests with red Kimi cases**

Add two tests to `tests/test_run_phase.py`:

```python
def test_prepare_supports_kimi_direct_lookup(self):
    ...

def test_run_dispatches_with_kimi_backend_dry_run(self):
    ...
```

`test_prepare_supports_kimi_direct_lookup` should synthesize a temporary Kimi share root and run:

- `run_phase.py prepare`
- `--transcript-placeholder USER_REQUEST_TRANSCRIPT`
- `--transcript-cli kimi-cli`
- `--transcript-search-root <fake-share-root>`
- subprocess from a cwd that is **not** `workdir`

The fixture should only register `workdir` inside `kimi.json`. The test should assert Kimi direct lookup succeeds anyway, which proves `run_phase.py` launches transcript lookup from `--workdir` instead of inheriting the caller's cwd.

`test_run_dispatches_with_kimi_backend_dry_run` should prepend a temporary fake `kimi` executable to `PATH` that only needs to satisfy the help-token probe. Then run:

- `run_phase.py run`
- `--backend kimi`
- `--dry-run`

and assert the nested `dispatch` payload is `ok` and the selected backend is `kimi`.

- [ ] **Step 2: Run the phase wrapper tests to verify they fail**

Run:

```bash
python3 -m unittest tests.test_run_phase -v
```

Expected: FAIL because `run_phase.py` does not accept `kimi-cli` or `kimi`.

- [ ] **Step 3: Add Kimi to the explicit phase wrapper surfaces**

Modify `orchestrator/run_phase.py` so that:

- `--transcript-cli` accepts `kimi-cli`
- `run --backend` accepts `kimi`
- `_prepare_transcripts()` treats Kimi like Codex for canary requirements: direct lookup is allowed with no canary, and canary is only required if direct lookup returns `None`
- `_run_command()` accepts an optional `cwd`
- `_prepare_transcripts()` invokes `user-request-transcript/build.py` with `cwd=workdir` so direct-lookup adapters use the phase worktree rather than the orchestrator's current directory

Keep `_detect_transcript_cli("auto")` unchanged except for any message text needed to stay accurate. Do **not** add a Kimi auto-detection heuristic here.

- [ ] **Step 4: Run the phase wrapper tests to verify they pass**

Run:

```bash
python3 -m unittest tests.test_run_phase -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add orchestrator/run_phase.py tests/test_run_phase.py
git commit -m "feat: add kimi options to run phase wrapper"
```

### Task 3: Add Kimi to the fallback runner with deterministic success validation

**Files:**
- Modify: `orchestrator/subagent_runner.py`
- Create: `tests/test_subagent_runner.py`

- [ ] **Step 1: Add deterministic red tests for Kimi probe, run, resume, and failure normalization**

Create `tests/test_subagent_runner.py` with a temp fake `kimi` binary and these tests:

```python
def test_probe_selects_kimi_when_it_is_the_only_available_backend(self):
    ...

def test_run_with_kimi_backend_returns_ok_when_context_matches_stdout(self):
    ...

def test_resume_with_kimi_backend_uses_explicit_session_id(self):
    ...

def test_run_with_kimi_backend_escalates_when_stdout_is_not_backed_by_visible_assistant_output(self):
    ...
```

The fake `kimi` binary should:

- print Kimi-compatible help text when called with `--help`
- on `run`, parse `--work-dir`, `--session`, `--thinking` / `--no-thinking`, and `--print --final-message-only`
- write a fake Kimi session context under `KIMI_SHARE_DIR/sessions/<md5(workdir)>/<session-id>/context.jsonl`
- in the success case, write a visible assistant `text` block matching stdout
- in the failure case, print `LLM not set` to stdout but write no visible assistant reply to the context file

The probe test should run with:

- a `PATH` that only contains the fake `kimi` binary
- a temporary `HOME` so `_search_paths()` cannot discover the real `~/bin/claude` or `~/.local/bin/kimi`

This isolation is required because `subagent_runner.py` appends home-based search paths even when `PATH` is overridden.

The resume test should assert the recorded argv contains `--session <id>` and **not** `--continue`.

- [ ] **Step 2: Run the runner tests to verify they fail**

Run:

```bash
python3 -m unittest tests.test_subagent_runner -v
```

Expected: FAIL because the runner does not yet know about Kimi.

- [ ] **Step 3: Implement Kimi probe/run/resume and centralized result classification**

Modify `orchestrator/subagent_runner.py` to add:

1. `probe`
   - add `_probe_kimi("kimi")`
   - require help tokens proving the binary supports:
     - `--print`
     - `--session`
     - `--continue`
     - `--work-dir`
     - plus a stable indicator for final-message-only support such as the phrase `final assistant`
   - include `kimi` in the probe payload
   - append `kimi` to the default backend order after Codex/Claude
   - update parser descriptions and help text so they say `Codex, Claude, or Kimi` instead of only `Codex and Claude`

2. command construction
   - add `_kimi_command()` returning `(argv, session_id)`
   - add `_kimi_resume_command()` returning `argv`
   - use:

```python
[
    binary,
    "--print",
    "--final-message-only",
    "--work-dir",
    str(workdir),
    "--session",
    session_id,
]
```

   - append `--model <model>` when present
   - map effort to thinking mode:
     - `low` => `--no-thinking`
     - otherwise => `--thinking`

3. reply capture
   - treat Kimi like Claude for reply capture: the printed final message comes from stdout and must be written to `reply.txt`

4. Kimi session validation
   - add small helpers in `subagent_runner.py` to:
     - resolve the Kimi share root from `KIMI_SHARE_DIR` or `~/.kimi`
     - locate the session context path from `workdir` + `session_id`
     - extract the final visible assistant text from that context file
   - replace the duplicated status/message logic in `_command_run()` and `_command_resume()` with one helper that classifies the result
   - for Kimi, only return `ok` / `user_decision_required` when the persisted final assistant text matches the printed reply after normalizing line endings and trimming only the print-mode trailing newline
   - when Kimi validation fails, return `escalate_to_user` with a message derived from the actual printed output, for example:

```python
message = f"Kimi did not produce a valid persisted reply: {first_line_of_reply}"
```

Do **not** change Codex or Claude command construction beyond what is necessary to route through the new shared result-classification helper.

- [ ] **Step 4: Run the runner tests to verify they pass**

Run:

```bash
python3 -m unittest tests.test_subagent_runner -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add orchestrator/subagent_runner.py tests/test_subagent_runner.py
git commit -m "feat: add kimi fallback runner backend"
```

### Task 4: Update Trycycle's skill and README for Kimi-hosted usage

**Files:**
- Modify: `SKILL.md`
- Modify: `README.md`

- [ ] **Step 1: Review the Kimi-sensitive user-facing instructions**

Read the relevant sections in `SKILL.md` and `README.md` and identify every place that is now incomplete or inaccurate for Kimi:

- transcript placeholder helper
- fallback-runner guidance
- supported-host description
- install instructions
- repo topics comment

Do **not** add tests for these files.

- [ ] **Step 2: Update `SKILL.md` for explicit Kimi wrapper usage**

Edit `SKILL.md` so that:

- the transcript helper includes a Kimi branch:
  - pass `--transcript-cli kimi-cli` on transcript-bearing phase wrapper calls
  - use direct lookup first
  - if the wrapper says a canary is required, emit a canary and rerun with `--canary`
- the fallback-runner guidance says that when Trycycle is running under Kimi, wrapper calls that dispatch through the bundled runner must pass `--backend kimi`
- the text explains why: Kimi support is explicit because `auto` cannot reliably detect a Kimi host
- the existing Codex/Claude instructions stay intact

- [ ] **Step 3: Update `README.md` to include Kimi support**

Edit `README.md` so that it:

- describes Trycycle as supporting Claude Code, Codex CLI, and Kimi CLI
- adds the Kimi user install path:

```bash
git clone https://github.com/danshapiro/trycycle.git ~/.kimi/skills/trycycle
```

- updates the maintainer topics comment to include `kimi-cli`

Keep the documentation diff narrow. Do not redesign badges, layout, or unrelated prose.

- [ ] **Step 4: Verify the doc updates textually**

Run:

```bash
rg -n "kimi-cli|~/.kimi/skills/trycycle|--backend kimi|--transcript-cli kimi-cli" SKILL.md README.md
```

Expected: the output shows the new Kimi support text in both files.

- [ ] **Step 5: Commit**

```bash
git add SKILL.md README.md
git commit -m "docs: document kimi trycycle usage"
```

## Final verification checklist

- [ ] Run the full automated suite:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

Expected: PASS

- [ ] Verify probe output includes Kimi:

```bash
python3 orchestrator/subagent_runner.py probe
```

Expected: JSON includes a `kimi` backend entry and `supports_resume: true` when `kimi` is installed.

- [ ] Run a real Kimi runner success smoke:

```bash
tmpdir=$(mktemp -d)
workdir="$tmpdir/work"
mkdir -p "$workdir"
printf 'Reply exactly with TRYCYCLE-KIMI-RUN-1\n' > "$tmpdir/prompt1.txt"
python3 orchestrator/subagent_runner.py run --phase smoke --prompt-file "$tmpdir/prompt1.txt" --workdir "$workdir" --artifacts-dir "$tmpdir/run1" --backend kimi --timeout-seconds 180
session_id=$(RUN1_RESULT="$tmpdir/run1/result.json" python3 - <<'PY'
import json, os
with open(os.environ["RUN1_RESULT"], encoding="utf-8") as handle:
    payload = json.load(handle)
assert payload["status"] == "ok", payload
print(payload["session_id"])
PY
)
printf 'Reply exactly with TRYCYCLE-KIMI-RUN-2\n' > "$tmpdir/prompt2.txt"
python3 orchestrator/subagent_runner.py resume --phase smoke --session-id "$session_id" --prompt-file "$tmpdir/prompt2.txt" --workdir "$workdir" --artifacts-dir "$tmpdir/run2" --backend kimi --timeout-seconds 180
RUN1_RESULT="$tmpdir/run1/result.json" RUN2_RESULT="$tmpdir/run2/result.json" python3 - <<'PY'
import json, os, pathlib
run1 = json.loads(pathlib.Path(os.environ["RUN1_RESULT"]).read_text())
run2 = json.loads(pathlib.Path(os.environ["RUN2_RESULT"]).read_text())
assert run1["status"] == "ok", run1
assert run2["status"] == "ok", run2
assert run2["session_id"] == run1["session_id"], (run1, run2)
print("runner smoke ok")
PY
```

Expected: both runner invocations return `status: "ok"` and the same `session_id`.

- [ ] Verify `run_phase.py prepare` can read the live Kimi session from outside the workdir:

```bash
template="$tmpdir/template.md"
printf '<task_input_json>{USER_REQUEST_TRANSCRIPT}</task_input_json>\n' > "$template"
python3 orchestrator/run_phase.py prepare --phase smoke --template "$template" --workdir "$workdir" --artifacts-dir "$tmpdir/phase" --transcript-placeholder USER_REQUEST_TRANSCRIPT --transcript-cli kimi-cli --require-nonempty-tag task_input_json
PHASE_RESULT="$tmpdir/phase/result.json" python3 - <<'PY'
import json, os, pathlib
payload = json.loads(pathlib.Path(os.environ["PHASE_RESULT"]).read_text())
prompt = pathlib.Path(payload["prompt_path"]).read_text()
assert "TRYCYCLE-KIMI-RUN-2" in prompt, prompt
print("run_phase kimi lookup ok")
PY
```

Expected: transcript lookup succeeds even though the command is launched from the repo root instead of `"$workdir"`.

- [ ] Verify the transcript builder can read the live Kimi session:

```bash
(cd "$workdir" && python3 /home/user/code/trycycle/.worktrees/add-kimi-cli-support/orchestrator/user-request-transcript/build.py --cli kimi-cli --output "$tmpdir/transcript.json")
TRANSCRIPT_PATH="$tmpdir/transcript.json" python3 - <<'PY'
import json, os, pathlib
payload = json.loads(pathlib.Path(os.environ["TRANSCRIPT_PATH"]).read_text())
assert any(turn["text"] == "TRYCYCLE-KIMI-RUN-2" for turn in payload if turn["role"] == "assistant"), payload
print("transcript smoke ok")
PY
```

Expected: the rendered transcript includes the visible assistant reply from the live Kimi session.

- [ ] Verify the zero-exit failure case escalates through Trycycle's runner:

```bash
faildir=$(mktemp -d)
mkdir -p "$faildir/work"
printf 'Reply exactly with SHOULD-NOT-SUCCEED\n' > "$faildir/prompt.txt"
KIMI_SHARE_DIR="$faildir/share" python3 orchestrator/subagent_runner.py run --phase smoke --prompt-file "$faildir/prompt.txt" --workdir "$faildir/work" --artifacts-dir "$faildir/run" --backend kimi --timeout-seconds 60
```

Expected: exit code `1`, `status: "escalate_to_user"`, and the resulting payload/message surfaces the real problem text instead of claiming a successful run.

- [ ] Re-run the existing non-Kimi regression smokes after the Kimi changes:

```bash
regdir=$(mktemp -d)
printf 'Reply exactly with OK\n' > "$regdir/prompt.txt"
python3 orchestrator/subagent_runner.py run --phase smoke --prompt-file "$regdir/prompt.txt" --workdir /tmp --backend codex --dry-run
python3 orchestrator/subagent_runner.py run --phase smoke --prompt-file "$regdir/prompt.txt" --workdir /tmp --backend claude --dry-run
```

Expected: both dry runs return `status: "ok"`.

## Notes for the implementation subagent

- Keep the Kimi implementation local. Do not convert `orchestrator/user-request-transcript` into a package just to share tiny helpers with `subagent_runner.py`; that would be more invasive than the feature warrants.
- In transcript code, `search_root` for Kimi should mean the Kimi share root (the directory that contains both `kimi.json` and `sessions/`), not the nested `sessions/` directory alone.
- In transcript lookup, never treat `wire.jsonl` or `context_sub_*.jsonl` as top-level user transcripts.
- Keep Codex and Claude behavior unchanged except where the new shared result-classification helper removes duplication.
- If a real Kimi smoke fails because the local Kimi installation is not authenticated or configured, record that explicitly in the implementation report; do not hide it.
