# OpenCode Support Test Plan

The accepted testing strategy still holds after reconciliation against the finalized implementation plan. The plan confirms the same integration seams (probe, command build, run, resume, reply extraction, host detection, transcript extraction, CLI detection) and the same extension pattern used for Kimi. The fake-binary harness, SQLite fixture harness, and live integration test are all well-matched to the planned interfaces. No new external dependencies, paid APIs, or scope changes have appeared that the strategy did not anticipate.

One minor adjustment: the plan reveals that `build.py` needs a single-match short-circuit to avoid calling `choose_most_recent_match` (which calls `path.stat()`) on synthetic OpenCode paths. This is a small code change in `build.py` that the strategy implicitly covered under "transcript extraction tests with SQLite fixtures," so it does not change cost or scope.

## Harness requirements

### Fake OpenCode CLI harness

- **What it does:** Creates a temporary fake `opencode` executable that responds to `run --help` with probe-satisfying help text, logs all invocations to a JSONL file, reads prompts from stdin, and emits either JSON event streams (with configurable session ID, reply text, and event structure) or default-format text output depending on `--format`.
- **What it exposes:** Deterministic probe validation, run command construction verification, resume command verification (checking `--session` flag), JSON reply extraction, model/effort flag propagation, and session ID capture -- all through the real `subagent_runner.py` CLI surface.
- **Estimated complexity:** Medium. Requires a scriptable Python fake binary with env-var-driven behavior modes (success, failure), configurable session ID, reply text, and output format. The implementation plan provides the complete fake binary code.
- **Tests that depend on it:** T1, T2, T3, T4, T5, T6, T7, T13, T14.

### SQLite fixture harness

- **What it does:** Creates a temporary OpenCode SQLite database with the correct schema (`session`, `message`, `part` tables) and populates it with configurable session, message, and part records including canary strings in user message text parts.
- **What it exposes:** Deterministic canary-based transcript lookup and transcript extraction inputs for `orchestrator/user-request-transcript/build.py` with the `--cli opencode` adapter.
- **Estimated complexity:** Low. A helper function that creates a temp SQLite DB with `CREATE TABLE` + `INSERT` statements. The implementation plan provides the complete fixture code.
- **Tests that depend on it:** T8, T9, T10, T11, T12.

### Live OpenCode harness

- **What it does:** Runs the real installed `opencode` binary against temp prompts and workdirs, then asserts against the runner's JSON output, reply artifacts, and session ID capture. Gated on `TRYCYCLE_RUN_LIVE_OPENCODE_TESTS=1`.
- **What it exposes:** Acceptance evidence that trycycle works against the real OpenCode CLI surface, including JSON event parsing, session ID capture from live output, and session resume continuity.
- **Estimated complexity:** Low to write, but requires API credits and a working local OpenCode installation with configured provider credentials.
- **Tests that depend on it:** T14.

## Test plan

### Subagent runner integration tests (fake binary)

1. **T1 -- OpenCode probe reports available and resumable when it is the only backend on PATH**
   - **Type:** scenario
   - **Disposition:** new
   - **Harness:** Fake OpenCode CLI harness
   - **Preconditions:** `PATH` contains only the fake `opencode` binary. `HOME` points at a temp directory so home-based Codex/Claude/Kimi fallback paths cannot be discovered.
   - **Actions:** Run `python3 orchestrator/subagent_runner.py probe`.
   - **Expected outcome:** JSON output includes `backends.opencode` with `available: true` and `supports_resume: true`; `selected_backend` is `"opencode"`; `backend_order` contains `"opencode"`. Source of truth: the implementation plan's probe function design, which checks `opencode run --help` for `--session`, `--model`, `--dir`, `--format` tokens.
   - **Interactions:** Binary resolution, help text parsing, backend preference ordering.

2. **T2 -- OpenCode host detection sets host_backend and preference ordering when OPENCODE=1**
   - **Type:** scenario
   - **Disposition:** new
   - **Harness:** Fake OpenCode CLI harness
   - **Preconditions:** `OPENCODE=1` is set in the environment. The fake `opencode` binary is on PATH.
   - **Actions:** Run `python3 orchestrator/subagent_runner.py probe`.
   - **Expected outcome:** `host_backend` is `"opencode"`; `selected_backend` is `"opencode"`; `backend_order` starts with `"opencode"`. Source of truth: the implementation plan's host detection design, which checks `os.environ.get("OPENCODE")` and returns `"opencode"` preference order `["opencode", "codex", "claude", "kimi"]`.
   - **Interactions:** `_detect_host_backend`, `_detect_backend_preferences`, probe ordering.

3. **T3 -- Runner `run --backend opencode` succeeds with JSON reply extraction and session ID capture**
   - **Type:** scenario
   - **Disposition:** new
   - **Harness:** Fake OpenCode CLI harness
   - **Preconditions:** Fake `opencode` binary is on PATH, configured to emit JSON events with `sessionID: "ses_test_abc123"` and reply text `"opencode test reply"` in a `type: "text"` event. Temp prompt, workdir, and artifacts dir exist.
   - **Actions:** Run `python3 orchestrator/subagent_runner.py run --phase smoke --prompt-file <prompt> --workdir <workdir> --artifacts-dir <artifacts> --backend opencode --model anthropic/claude-sonnet-4-20250514 --effort high`.
   - **Expected outcome:** Exit code 0; JSON output has `status: "ok"`, `backend: "opencode"`, `session_id: "ses_test_abc123"`; `reply_path` file contains `"opencode test reply"`; the logged argv includes `run`, `--format json`, `--dir <workdir>`, `--model anthropic/claude-sonnet-4-20250514`, `--variant high`. Source of truth: the implementation plan's command builder and JSON reply extraction design.
   - **Interactions:** `_opencode_command`, `_extract_opencode_reply_from_json`, `_extract_opencode_session_id_from_json`, `_normalize_status`, artifact writing.

4. **T4 -- Runner `resume --backend opencode` passes session ID via --session flag**
   - **Type:** scenario
   - **Disposition:** new
   - **Harness:** Fake OpenCode CLI harness
   - **Preconditions:** Fake `opencode` binary is on PATH, configured for success mode with session ID `"ses_existing_session"`. Temp prompt, workdir, and artifacts dir exist.
   - **Actions:** Run `python3 orchestrator/subagent_runner.py resume --phase execute --session-id ses_existing_session --prompt-file <prompt> --workdir <workdir> --artifacts-dir <artifacts> --backend opencode`.
   - **Expected outcome:** Exit code 0; JSON output has `status: "ok"`, `session_id: "ses_existing_session"`; `reply_path` file contains the configured reply text; the logged argv includes `--session ses_existing_session`. Source of truth: the implementation plan's resume command builder, which passes `--session <captured_id>`.
   - **Interactions:** `_opencode_resume_command`, resume backend dispatch, session continuity.

5. **T5 -- Runner `run --backend host --dry-run` selects opencode when OPENCODE=1 is set**
   - **Type:** scenario
   - **Disposition:** new
   - **Harness:** Fake OpenCode CLI harness
   - **Preconditions:** `OPENCODE=1` is set. Fake `opencode` binary is on PATH.
   - **Actions:** Run `python3 orchestrator/subagent_runner.py run --phase smoke --prompt-file <prompt> --workdir <workdir> --artifacts-dir <artifacts> --backend host --dry-run`.
   - **Expected outcome:** Exit code 0; JSON output has `status: "ok"`, `backend: "opencode"`; the recorded command starts with the fake opencode binary path. Source of truth: the implementation plan's host-backend detection, which resolves `"host"` to `"opencode"` when `OPENCODE=1` is set.
   - **Interactions:** `_detect_host_backend`, `_resolve_backend_selection`, dry-run command generation.

6. **T6 -- Runner escalates when opencode run exits non-zero**
   - **Type:** boundary
   - **Disposition:** new
   - **Harness:** Fake OpenCode CLI harness
   - **Preconditions:** Fake `opencode` binary is configured with `FAKE_OPENCODE_MODE=failure`, which causes it to write to stderr and exit with code 1.
   - **Actions:** Run `python3 orchestrator/subagent_runner.py run --phase smoke --prompt-file <prompt> --workdir <workdir> --artifacts-dir <artifacts> --backend opencode`.
   - **Expected outcome:** Exit code 1; JSON output has `status: "escalate_to_user"`; `stdout_path` and `reply_path` contain the error output. Source of truth: the implementation plan's `_normalize_status` function and the existing pattern established by Kimi/Claude/Codex escalation behavior.
   - **Interactions:** Non-zero exit handling, `_normalize_status`, artifact capture for failed runs.

7. **T7 -- OpenCode model override via TRYCYCLE_OPENCODE_MODEL environment variable**
   - **Type:** scenario
   - **Disposition:** new
   - **Harness:** Fake OpenCode CLI harness
   - **Preconditions:** `TRYCYCLE_OPENCODE_MODEL=anthropic/claude-opus-4-20250514` is set. Fake `opencode` binary is on PATH.
   - **Actions:** Run `python3 orchestrator/subagent_runner.py run --phase smoke --prompt-file <prompt> --workdir <workdir> --artifacts-dir <artifacts> --backend opencode --dry-run`.
   - **Expected outcome:** The recorded command includes `--model anthropic/claude-opus-4-20250514`. Source of truth: the implementation plan's `MODEL_OVERRIDE_ENV_BY_BACKEND` mapping, which adds `"opencode": "TRYCYCLE_OPENCODE_MODEL"`.
   - **Interactions:** Environment variable model override, command builder, dry-run artifact inspection.

### Transcript adapter integration tests (SQLite fixture)

8. **T8 -- OpenCode canary lookup finds the correct session and extracts visible conversation turns**
   - **Type:** scenario
   - **Disposition:** new
   - **Harness:** SQLite fixture harness
   - **Preconditions:** A temp SQLite DB contains one session (`ses_abc123`) with a user message part containing the canary string and a subsequent assistant message part with visible text. The DB is at `<tmpdir>/opencode.db`.
   - **Actions:** Run `python3 orchestrator/user-request-transcript/build.py --cli opencode --canary <canary> --search-root <tmpdir>`.
   - **Expected outcome:** Exit code 0; stdout is a JSON array with 2 turns; the first turn has `role: "user"` and text containing the canary; the second has `role: "assistant"` with the expected reply text. Source of truth: the implementation plan's `opencode_cli.py` adapter design, which queries the `part` table for canary matches and extracts user/assistant text parts.
   - **Interactions:** `build.py` adapter dispatch, `opencode_cli.find_matching_transcripts` (SQLite canary query), `opencode_cli.extract_transcript` (SQLite message/part query), `build.py` single-match short-circuit (skips `choose_most_recent_match`), transcript rendering.

9. **T9 -- OpenCode transcript extraction handles multiple user and assistant turns**
   - **Type:** scenario
   - **Disposition:** new
   - **Harness:** SQLite fixture harness
   - **Preconditions:** A temp SQLite DB contains one session with a multi-turn conversation: user1, assistant1, user2, assistant2. The canary appears in user1's text.
   - **Actions:** Run `python3 orchestrator/user-request-transcript/build.py --cli opencode --canary <canary> --search-root <tmpdir>`.
   - **Expected outcome:** Exit code 0; stdout contains 4 turns in the correct order, alternating user/assistant. Source of truth: the implementation plan's `_extract_session_transcript` function, which iterates messages ordered by `time_created` and collects visible text parts.
   - **Interactions:** Multi-message extraction ordering, `_extract_session_transcript` accumulation logic.

10. **T10 -- OpenCode transcript skips empty text parts and messages with no visible text**
    - **Type:** boundary
    - **Disposition:** new
    - **Harness:** SQLite fixture harness
    - **Preconditions:** A temp SQLite DB contains a session where some message parts have `type: "tool_use"` (not `"text"`), some text parts have empty or whitespace-only text, and one assistant message has only non-text parts.
    - **Actions:** Run `python3 orchestrator/user-request-transcript/build.py --cli opencode --canary <canary> --search-root <tmpdir>`.
    - **Expected outcome:** Exit code 0; the output contains only turns with visible text content; empty/whitespace-only text parts and non-text parts are excluded. Source of truth: the implementation plan's `_extract_session_transcript`, which filters on `part_data.get("type") == "text"` and `text.strip()`.
    - **Interactions:** Part type filtering, whitespace handling, empty-message suppression.

11. **T11 -- OpenCode transcript lookup fails gracefully when DB does not exist**
    - **Type:** boundary
    - **Disposition:** new
    - **Harness:** SQLite fixture harness (empty tmpdir, no DB created)
    - **Preconditions:** `--search-root` points to a temp directory with no `opencode.db` file.
    - **Actions:** Run `python3 orchestrator/user-request-transcript/build.py --cli opencode --canary <canary> --search-root <tmpdir>`.
    - **Expected outcome:** Exit code 1; stderr contains an error message indicating the OpenCode database was not found. Source of truth: the implementation plan's `_resolve_db_path` function, which raises `TranscriptError` when the DB is missing.
    - **Interactions:** `_resolve_db_path` error path, `build.py` error handling.

12. **T12 -- OpenCode canary timeout when canary is not in any session**
    - **Type:** boundary
    - **Disposition:** new
    - **Harness:** SQLite fixture harness
    - **Preconditions:** A temp SQLite DB exists with sessions, but none contain the specified canary string. `--timeout-ms` is set to a short value (e.g., 500ms).
    - **Actions:** Run `python3 orchestrator/user-request-transcript/build.py --cli opencode --canary <nonexistent-canary> --search-root <tmpdir> --timeout-ms 500`.
    - **Expected outcome:** Exit code 1; stderr contains an error message indicating no session contained the canary within the timeout. Source of truth: the implementation plan's `find_matching_transcripts` polling loop, which raises `TranscriptError` on deadline expiry.
    - **Interactions:** Canary polling loop, timeout enforcement, error propagation.

### Transcript CLI auto-detection in run_phase.py

13. **T13 -- `run_phase.py` auto-detects opencode as transcript CLI when OPENCODE=1 is set**
    - **Type:** scenario
    - **Disposition:** new
    - **Harness:** Fake OpenCode CLI harness + SQLite fixture harness
    - **Preconditions:** `OPENCODE=1` is set. A template requires a transcript placeholder. A temp OpenCode SQLite DB is populated with the canary in a user message.
    - **Actions:** Run `python3 orchestrator/run_phase.py prepare --phase planning-initial --template <template> --workdir <workdir> --transcript-placeholder USER_REQUEST_TRANSCRIPT --canary <canary> --transcript-search-root <tmpdir> --require-nonempty-tag task_input_json` with `OPENCODE=1` in environment.
    - **Expected outcome:** Exit code 0; `result.json` reports `status: "prepared"`; the rendered prompt contains the transcript extracted from the OpenCode SQLite DB. Source of truth: the implementation plan's `_detect_transcript_cli` update, which adds `os.environ.get("OPENCODE")` returning `"opencode"`.
    - **Interactions:** `_detect_transcript_cli` auto-detection, transcript builder subprocess with `--cli opencode`, prompt builder validation, `run_phase.py` artifact generation.

### Live integration test

14. **T14 -- Live OpenCode run and resume with real binary**
    - **Type:** integration
    - **Disposition:** new
    - **Harness:** Live OpenCode harness (gated on `TRYCYCLE_RUN_LIVE_OPENCODE_TESTS=1`)
    - **Preconditions:** Real `opencode` binary is installed and configured with valid provider credentials. No fake binary or fixture overrides.
    - **Actions:** (1) Run `python3 orchestrator/subagent_runner.py run --phase live-smoke --prompt-file <prompt> --workdir <workdir> --artifacts-dir <artifacts_run> --backend opencode --timeout-seconds 120` with a prompt asking the model to say a known marker string. (2) Capture the `session_id` from the run output. (3) Run `python3 orchestrator/subagent_runner.py resume --phase live-smoke --session-id <captured_session_id> --prompt-file <resume_prompt> --workdir <workdir> --artifacts-dir <artifacts_resume> --backend opencode --timeout-seconds 120` asking the model to recall the previous message.
    - **Expected outcome:** Both commands exit 0; run output has `status: "ok"`, `backend: "opencode"`, a non-empty `session_id` starting with `ses_`, and the reply contains the marker string. Resume output has `status: "ok"` and the same `session_id`. Source of truth: empirical validation from the research phase, which confirmed JSON event stream format, session ID capture from first event line, and `--session` resume behavior.
    - **Interactions:** Real OpenCode CLI invocation, real API call, JSON event stream parsing, session persistence, session resume via `--session`.

### Regression tests

15. **T15 -- Full existing test suite passes with OpenCode additions**
    - **Type:** regression
    - **Disposition:** existing
    - **Harness:** All existing test harnesses
    - **Preconditions:** All code changes for OpenCode support have been applied.
    - **Actions:** Run `python3 -m pytest tests/ -v`.
    - **Expected outcome:** All previously passing tests continue to pass. The one pre-existing failure (if any) remains unchanged. New OpenCode tests pass. Live OpenCode tests are skipped without the gate env var. Source of truth: the existing test suite baseline (47 passing, 1 pre-existing failure, 2 skipped live Kimi tests).
    - **Interactions:** All backends, all adapters, all harnesses.

### Unit tests (support material)

16. **T16 -- `_extract_opencode_session_id_from_json` parses session ID from JSON events**
    - **Type:** unit
    - **Disposition:** new
    - **Harness:** Direct function import
    - **Preconditions:** None.
    - **Actions:** Call `_extract_opencode_session_id_from_json` with (a) a well-formed JSON event stream containing `sessionID`, (b) an empty string, (c) malformed JSON lines, (d) JSON events without `sessionID`.
    - **Expected outcome:** (a) returns the correct session ID; (b) returns `None`; (c) returns `None` (skips malformed lines gracefully); (d) returns `None`. Source of truth: the implementation plan's function specification.
    - **Interactions:** JSON parsing only; no subprocess or filesystem.

17. **T17 -- `_extract_opencode_reply_from_json` extracts reply text from multi-step JSON events**
    - **Type:** unit
    - **Disposition:** new
    - **Harness:** Direct function import
    - **Preconditions:** None.
    - **Actions:** Call `_extract_opencode_reply_from_json` with (a) a JSON event stream containing `step_start`, `text` events, `step_finish` with `reason: "stop"`; (b) a multi-step stream where a tool-call step precedes the final assistant step; (c) an empty string; (d) a stream with no `text` events.
    - **Expected outcome:** (a) returns the concatenated text from text events in the final step; (b) returns only the text from the last step (tool-call step text is reset on next `step_start`); (c) returns empty string; (d) returns empty string. Source of truth: the implementation plan's `_extract_opencode_reply_from_json` function specification, which collects text between the last `step_start` and the final `step_finish` with `reason: "stop"`.
    - **Interactions:** JSON parsing only; no subprocess or filesystem.

## Coverage summary

### Covered areas

- **Probe function:** T1 validates probe detection when opencode is the only available backend. T2 validates host detection and preference ordering.
- **Command construction (run):** T3 validates all flags (`--format json`, `--dir`, `--model`, `--variant`) and reply/session extraction.
- **Command construction (resume):** T4 validates `--session` flag propagation and reply extraction on resume.
- **Host-backend integration:** T5 validates `--backend host` resolves to opencode when `OPENCODE=1` is set.
- **Error handling:** T6 validates escalation on non-zero exit.
- **Model override:** T7 validates `TRYCYCLE_OPENCODE_MODEL` environment variable.
- **Transcript canary lookup:** T8 validates end-to-end canary-based transcript extraction from SQLite.
- **Transcript multi-turn:** T9 validates correct ordering of multi-turn conversations.
- **Transcript filtering:** T10 validates exclusion of non-text parts and empty text.
- **Transcript error paths:** T11 (missing DB), T12 (canary timeout).
- **CLI auto-detection:** T13 validates `_detect_transcript_cli` returns `"opencode"` when `OPENCODE=1` is set.
- **Live integration:** T14 validates real opencode binary run and resume.
- **Regression:** T15 validates all existing tests continue to pass.
- **JSON parsing helpers:** T16, T17 validate the pure-function extraction logic.

### Explicitly excluded per strategy

- **SKILL.md and README.md documentation changes (Tasks 8, 9):** These are prose/documentation changes, not code. The project's AGENTS.md explicitly states "Don't create tests for skill changes, only code changes." No automated tests for these files.
- **Native mode OpenCode subagent orchestration:** The implementation plan notes this is speculative and deferred. No tests written for native mode.
- **SQLite Tier 2 reply fallback:** The plan defers the DB-based reply fallback to live testing results (Task 10 in the plan). If the live test reveals JSON stream incompleteness, the fallback will be added as a follow-up with its own tests.

### Risks from exclusions

- Documentation changes could contain incorrect paths or stale instructions. This is low risk since the changes are small and the review loop will catch obvious errors.
- The SQLite Tier 2 fallback is not tested because it is not yet implemented. If OpenCode's JSON event stream is unreliable in some edge cases, reply extraction could fail. The live test (T14) provides the signal to decide whether this fallback is needed.
