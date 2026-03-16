# Thin Phase Wrapper Implementation Plan

> **For agentic workers:** REQUIRED: Use trycycle-executing to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Trycycle's phase-by-phase shell choreography with a thin wrapper command that owns transcript capture, prompt rendering, artifact persistence, and fallback dispatch/resume, while adding `--output` support to the existing helper CLIs and validating the new flow with heavy automated coverage plus live Claude/Codex smoke runs.

**Architecture:** Keep Trycycle's native-vs-fallback transport split, but move all phase preparation into one stdlib Python entrypoint: `orchestrator/run_phase.py`. That wrapper will call the existing transcript builder, prompt builder, and fallback runner as subprocesses, so we centralize operational logic without turning the repo into a larger state-machine framework or import-heavy package refactor. Each invocation is self-contained and writes one artifacts directory with a structured `result.json`; persistent mutable session state stays out of scope except for the existing fallback `session_id`.

**Tech Stack:** Python 3 stdlib scripts, `unittest`, existing prompt templates in `subagents/`, Trycycle `SKILL.md`, Codex CLI, Claude Code.

---

## User-visible behavior and invariants

- The skill text must stop telling the agent to manually run `mark_with_canary.py`, redirect stdout into temp files, or invoke `prompt_builder/build.py` directly during normal phase execution.
- `python3 orchestrator/run_phase.py prepare ...` is the native-mode contract. It prepares exactly one phase, writes artifacts, prints one JSON payload, and never dispatches a subagent.
- `python3 orchestrator/run_phase.py run ...` is the fallback fresh-dispatch contract. It performs the same preparation work, then invokes `subagent_runner.py run`, nesting those dispatch artifacts under the phase artifacts directory.
- `python3 orchestrator/run_phase.py resume ...` is the fallback resume contract for the persistent implementation agent. It re-renders the phase prompt, then invokes `subagent_runner.py resume` with the supplied `session_id`.
- Transcript lookup rules move into code:
  - Codex: direct current-session lookup first, canary fallback second.
  - Claude: canary flow only.
  - The wrapper records whether the transcript came from direct lookup or canary fallback.
- The wrapper owns the phase-to-template registry. Skill prose names the phase and required paths; code decides which template, transcript placeholder, and prompt-builder validation flags to use.
- No persistent session state file is introduced. Git state, changed files, and plan/test-plan freshness remain live checks in `SKILL.md`.
- Failures must be explicit:
  - a failed preparation exits non-zero and writes an error `result.json`
  - no success payload may point at a non-existent prompt or reply path
  - prompt validation failures must not silently leave a stale prompt advertised as valid
- Heavy testing is required here even though this repo usually avoids adding tests. The user explicitly requested it, and this change is orchestration plumbing where regressions are otherwise easy to miss.

## File structure

- Modify: `orchestrator/prompt_builder/build.py`
  - Add `--output` support so rendered prompts can be written by path instead of shell redirection.
- Modify: `orchestrator/user-request-transcript/build.py`
  - Add `--output` support so transcript JSON can be written by path instead of shell redirection.
- Create: `orchestrator/run_phase.py`
  - New thin wrapper entrypoint with `prepare`, `run`, and `resume` subcommands.
  - Owns the declarative phase registry, transcript lookup fallback, artifact layout, prompt rendering, and fallback-runner dispatch.
- Modify: `SKILL.md`
  - Rewrite phase instructions around `run_phase.py` so the orchestrator speaks in helper commands, not shell choreography.
- Modify: `docs/trycycle-information-flow.dot`
  - Update the architecture diagram so maintainers can see `run_phase.py` as the new preparation hub.
- Create: `tests/test_prompt_builder_build.py`
  - CLI-level tests for prompt-builder `--output` behavior.
- Create: `tests/test_user_request_transcript_build.py`
  - CLI-level tests for transcript-builder `--output` behavior on direct lookup and canary lookup.
- Create: `tests/test_run_phase.py`
  - High-value wrapper tests covering phase preparation, Codex direct lookup, Claude canary lookup, fallback dispatch, resume, artifact contracts, and error propagation.
- Create: `docs/evals/2026-03-15-phase-wrapper-live-smoke.md`
  - Record the live Claude Code and Codex CLI smoke runs the user requested, including commands used, artifact paths, and observed outcomes.

## Strategy gate

- Do not build a persistent `session.py` state machine. That would add cross-phase mutable state before the thin wrapper architecture has proven insufficient, and it would blur the native/fallback boundary that still matters in Trycycle.
- Do not refactor the repo into importable Python packages just to avoid subprocess calls. Existing helper scripts are already the stable units here; a wrapper that shells into those helpers is the cleanest steady-state change for this codebase.
- Keep `subagent_runner.py` authoritative for backend probing, artifact capture, and normalized JSON. `run_phase.py` should orchestrate it, not reimplement it.
- Put the duplication where it belongs:
  - phase templates and transcript placeholder names live in a registry in `run_phase.py`
  - shell-specific temp-file choreography disappears from `SKILL.md`
- Treat the live Claude/Codex smoke runs as acceptance gates, not optional follow-up. Automated tests will cover most behavior, but only live runs prove the wrapper-driven flow still works against the real CLIs.

### Task 1: Add prompt-builder path output and protect against partial writes

**Files:**
- Modify: `orchestrator/prompt_builder/build.py`
- Create: `tests/test_prompt_builder_build.py`

- [ ] **Step 1: Identify or write the failing test**

Write CLI-level tests that cover the two behaviors this change must guarantee:

```python
def test_output_writes_rendered_prompt_to_requested_file(self):
    ...

def test_output_file_is_not_created_when_render_fails(self):
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_prompt_builder_build -v`

Expected: FAIL because `build.py` does not accept `--output` yet and cannot satisfy the new file-writing assertions.

- [ ] **Step 3: Write minimal implementation**

Extend `build.py` with an optional `--output PATH` argument and a helper that writes the rendered prompt atomically only after template parsing and validation succeed.

```python
def emit_output(text: str, output_path: Path | None) -> None:
    if output_path is None:
        sys.stdout.write(text)
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(output_path)
```

Keep stdout behavior unchanged when `--output` is omitted.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_prompt_builder_build -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add orchestrator/prompt_builder/build.py tests/test_prompt_builder_build.py
git commit -m "feat: add prompt builder output path support"
```

### Task 2: Add transcript-builder path output without changing transcript semantics

**Files:**
- Modify: `orchestrator/user-request-transcript/build.py`
- Create: `tests/test_user_request_transcript_build.py`

- [ ] **Step 1: Identify or write the failing test**

Write tests that prove the transcript builder can write to a file for both lookup styles it already supports:

```python
def test_codex_direct_lookup_can_write_transcript_to_output_file(self):
    ...

def test_claude_canary_lookup_can_write_transcript_to_output_file(self):
    ...
```

Use `--search-root` with temporary transcript fixtures so the tests stay hermetic.

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_user_request_transcript_build -v`

Expected: FAIL because `build.py` does not accept `--output` yet.

- [ ] **Step 3: Write minimal implementation**

Mirror the prompt-builder pattern in `user-request-transcript/build.py`: accept `--output`, compute the transcript exactly as before, and write the rendered JSON transcript to that path only after lookup succeeds.

```python
if args.output is None:
    sys.stdout.write(transcript)
else:
    write_output_file(args.output, transcript)
```

Do not move the direct-vs-canary fallback logic here; that belongs in `run_phase.py`, where the skill-level orchestration is being collapsed.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_user_request_transcript_build -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add orchestrator/user-request-transcript/build.py tests/test_user_request_transcript_build.py
git commit -m "feat: add transcript builder output path support"
```

### Task 3: Build `run_phase.py` for native-mode preparation with a declarative phase registry

**Files:**
- Create: `orchestrator/run_phase.py`
- Create: `tests/test_run_phase.py`

- [ ] **Step 1: Identify or write the failing test**

Start with preparation-only tests, because the wrapper contract must be solid before adding dispatch:

```python
def test_prepare_testing_strategy_writes_prompt_and_transcript_artifacts(self):
    ...

def test_prepare_planning_edit_binds_worktree_and_plan_path(self):
    ...

def test_prepare_uses_codex_direct_lookup_before_canary(self):
    ...

def test_prepare_uses_claude_canary_flow(self):
    ...
```

The tests should assert the contents of `result.json`, `prompt.txt`, `transcript.json`, and `canary.txt` where applicable.

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_run_phase.RunPhasePrepareTests -v`

Expected: FAIL because `orchestrator/run_phase.py` does not exist.

- [ ] **Step 3: Write minimal implementation**

Create `run_phase.py` with these core pieces:

```python
@dataclass(frozen=True)
class PhaseSpec:
    template_path: Path
    transcript_placeholder: str | None
    required_tags: tuple[str, ...]
    scalar_bindings: tuple[str, ...]
    file_bindings: tuple[str, ...]

PHASES = {
    "testing-strategy": ...,
    "planning-initial": ...,
    "planning-edit": ...,
    "test-plan": ...,
    "executing": ...,
    "post-impl-review": ...,
}
```

Implement `prepare` so it:

1. validates phase-specific required inputs
2. creates an artifacts directory layout such as:
   - `result.json`
   - `prompt.txt`
   - `transcript.json` when a transcript placeholder is required
   - `canary.txt` when canary fallback is used
3. runs the transcript builder with direct lookup first for Codex and canary-only for Claude
4. runs the prompt builder with `--output`
5. emits structured JSON like:

```json
{
  "status": "prepared",
  "command": "prepare",
  "phase": "planning-initial",
  "artifacts_dir": "/tmp/trycycle-phase-123",
  "result_path": "/tmp/trycycle-phase-123/result.json",
  "prompt_path": "/tmp/trycycle-phase-123/prompt.txt",
  "transcript_path": "/tmp/trycycle-phase-123/transcript.json",
  "transcript_lookup_mode": "direct",
  "canary_path": null
}
```

Use `--workdir` as the execution directory for helper subprocesses, and keep `--worktree-path` as an explicit binding only for phases whose prompt template requires `{WORKTREE_PATH}`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_run_phase.RunPhasePrepareTests -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add orchestrator/run_phase.py tests/test_run_phase.py
git commit -m "feat: add phase preparation wrapper"
```

### Task 4: Add fallback `run` and `resume` to the wrapper and prove real dispatch integration with fake backends

**Files:**
- Modify: `orchestrator/run_phase.py`
- Modify: `tests/test_run_phase.py`

- [ ] **Step 1: Identify or write the failing test**

Extend `tests/test_run_phase.py` with integration-style tests that run the real `subagent_runner.py` against temporary fake `codex` and `claude` executables placed on `PATH`:

```python
def test_run_invokes_subagent_runner_and_nests_dispatch_artifacts(self):
    ...

def test_resume_passes_session_id_through_to_subagent_runner(self):
    ...

def test_run_surfaces_user_decision_required_from_dispatch(self):
    ...
```

The fake binaries must satisfy the help-token probes and return deterministic replies so the wrapper sees the same JSON shape real dispatch would produce.

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_run_phase.RunPhaseDispatchTests -v`

Expected: FAIL because `run_phase.py` only supports preparation at this point.

- [ ] **Step 3: Write minimal implementation**

Add `run` and `resume` subcommands that reuse the exact same preparation code, then invoke `subagent_runner.py` with `--artifacts-dir <phase-artifacts>/dispatch`.

```python
def dispatch_phase(prepared: PreparedPhase, *, resume_session_id: str | None) -> dict[str, Any]:
    command = [
        "python3",
        str(skill_root / "orchestrator" / "subagent_runner.py"),
        "resume" if resume_session_id else "run",
        "--phase", prepared.phase,
        "--prompt-file", str(prepared.prompt_path),
        "--workdir", str(prepared.workdir),
        "--artifacts-dir", str(prepared.artifacts_dir / "dispatch"),
        ...
    ]
```

Merge the runner payload into the phase result JSON under a `dispatch` key instead of flattening it, so phase-owned artifacts and dispatch-owned artifacts stay distinct.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_run_phase.RunPhaseDispatchTests -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add orchestrator/run_phase.py tests/test_run_phase.py
git commit -m "feat: add fallback dispatch to phase wrapper"
```

### Task 5: Rewrite `SKILL.md` around wrapper commands and update maintainer-facing architecture docs

**Files:**
- Modify: `SKILL.md`
- Modify: `docs/trycycle-information-flow.dot`

- [ ] **Step 1: Identify or write the failing test**

Add assertions to `tests/test_run_phase.py` or a small new `SkillRewriteTests` case that treat the skill text itself as a contract:

```python
def test_skill_uses_run_phase_wrapper_instead_of_manual_prompt_redirection(self):
    ...
```

The test should fail if phase sections still instruct agents to call `mark_with_canary.py`, `prompt_builder/build.py`, or shell redirection directly for routine phase execution.

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_run_phase.SkillRewriteTests -v`

Expected: FAIL because `SKILL.md` still contains the old choreography.

- [ ] **Step 3: Write minimal implementation**

Rewrite the relevant `SKILL.md` sections so they describe wrapper usage, not procedures:

- Replace the prompt-builder helper and transcript-placeholder helper sections with a `run_phase.py` helper section.
- For each wrapped phase, use one command shape:

```bash
python3 <skill-directory>/orchestrator/run_phase.py prepare \
  --phase planning-initial \
  --workdir {WORKTREE_PATH} \
  --worktree-path {WORKTREE_PATH} \
  --artifacts-dir <phase-artifacts-dir>
```

or, in fallback mode:

```bash
python3 <skill-directory>/orchestrator/run_phase.py run ...
python3 <skill-directory>/orchestrator/run_phase.py resume ...
```

- Keep the native/fallback policy text and worktree hygiene gates intact.
- Update `docs/trycycle-information-flow.dot` so the orchestration path now flows through `run_phase.py` before prompt building, transcript lookup, and fallback dispatch.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_run_phase.SkillRewriteTests -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add SKILL.md docs/trycycle-information-flow.dot tests/test_run_phase.py
git commit -m "docs: route trycycle phases through wrapper"
```

### Task 6: Run the heavy verification stack and record the live Claude/Codex smoke runs

**Files:**
- Create: `docs/evals/2026-03-15-phase-wrapper-live-smoke.md`

- [ ] **Step 1: Identify or write the verification checklist**

Create the eval document first with explicit acceptance criteria:

- automated unittest suite passes
- Codex live smoke run completes a simple wrapper-driven trycycle flow
- Claude live smoke run completes the same flow
- both live runs record artifact paths and whether transcript lookup was direct or canary
- no phase in the observed flow requires raw shell redirection or manual prompt-file plumbing

- [ ] **Step 2: Run automated tests to verify the current stack is green before live smoke**

Run: `python3 -m unittest discover -s tests -v`

Expected: PASS

- [ ] **Step 3: Execute the live smoke runs and record the results**

Perform two end-to-end smoke validations on a tiny scratch repo with a trivial change request, one against Codex and one against Claude, using the wrapper-driven Trycycle flow the user asked for.

Minimum evidence to record in `docs/evals/2026-03-15-phase-wrapper-live-smoke.md` for each backend:

- backend name and CLI version
- scratch repo path and request text
- whether the run used native dispatch, fallback `run`, or fallback `resume`
- wrapper artifact directory for at least one planning-style phase and one execution-style phase
- observed `session_id` when fallback resume was exercised
- final changed files and commit hash in the scratch repo
- any divergence between Codex direct lookup and Claude canary lookup

If one backend cannot be exercised live in this environment, record the exact blocker and treat that as a failed acceptance gate rather than silently skipping it.

- [ ] **Step 4: Re-run automated tests to verify the recorded eval did not break the repo**

Run: `python3 -m unittest discover -s tests -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add docs/evals/2026-03-15-phase-wrapper-live-smoke.md
git commit -m "test: record phase wrapper live smoke validation"
```

## Final verification checklist

- `python3 -m unittest discover -s tests -v`
- Live Codex smoke run recorded in `docs/evals/2026-03-15-phase-wrapper-live-smoke.md`
- Live Claude smoke run recorded in `docs/evals/2026-03-15-phase-wrapper-live-smoke.md`
- `rg -n "mark_with_canary.py|prompt_builder/build.py|> \\\"\\$prompt_file\\\"|set-file .*temp-file" SKILL.md` shows no routine phase choreography left behind
- `python3 orchestrator/run_phase.py --help`
- `python3 orchestrator/run_phase.py prepare --help`
- `python3 orchestrator/run_phase.py run --help`
- `python3 orchestrator/run_phase.py resume --help`

## Notes for the implementation subagent

- Keep the wrapper thin. Do not add a persistent session file, a daemon, or a generalized orchestration framework.
- Favor predictable artifact paths and structured JSON over clever abstractions.
- Preserve the current prompt templates. The new behavior should come from phase preparation code and `SKILL.md`, not from changing the templates' intent.
- When a live smoke run exposes a gap, fix the wrapper or skill text, rerun the relevant automated tests, then rerun the live smoke before closing the task.

## Remember

- Exact file paths always
- Keep the native-vs-fallback split explicit
- Centralize transcript fallback and prompt rendering in code, not prose
- Reuse the real `subagent_runner.py`; do not fork its behavior
- If a helper command fails, surface that error in `run_phase.py` result JSON rather than swallowing it
- The live Claude and Codex smoke runs are required deliverables for this change
