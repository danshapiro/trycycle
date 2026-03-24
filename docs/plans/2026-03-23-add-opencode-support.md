# Add OpenCode Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use trycycle-executing to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add first-class OpenCode support to trycycle's fallback-runner, transcript-adapter, host-detection, and user-facing docs so Trycycle can run under OpenCode and dispatch OpenCode subagents, using the same extension seams that Codex, Claude, and Kimi already use.

**Architecture:** Extend every existing integration seam: `subagent_runner.py` gets an OpenCode probe/run/resume backend with JSON-format output parsing for reply extraction and session ID capture; `user-request-transcript/` gets an OpenCode adapter that reads the SQLite database at `~/.local/share/opencode/opencode.db`; `run_phase.py` and `build.py` gain OpenCode as a transcript-CLI choice with auto-detection via the `OPENCODE` environment variable; `SKILL.md` gets updated transcript-helper instructions; and `README.md` gets installation and badge lines. The implementation follows the exact patterns established by the Kimi CLI integration (the most recent backend addition) and does not introduce any new orchestration architecture.

**Tech Stack:** Python 3 stdlib (`sqlite3`, `json`, `subprocess`, `uuid`, `unittest`), real `opencode` CLI for live integration tests

---

## Design decisions

### Use `--format json` for all runner invocations, not default format

Empirical testing on OpenCode 1.3.0 confirms that the **default format does produce clean stdout when piped** (non-TTY) — it outputs only the final assistant text, similar to Claude's `-p --output-format text` and Kimi's `--print --final-message-only`. However, default format does **not** include the session ID in its output. Since OpenCode auto-assigns session IDs (they cannot be pre-assigned), and the runner needs the session ID for resume support, we must use `--format json`.

Each JSON line has a `type` field (`step_start`, `text`, `tool_use`, `step_finish`, `reasoning`) plus a `sessionID` field and a `part` object. The runner parses the JSON event stream to:
1. Extract the `sessionID` from the first event line (the primary reason we need JSON format)
2. Collect all `type: "text"` events from the final assistant turn to assemble the reply text

The JSON parsing is straightforward and the events are well-structured.

**Important caveat:** OpenCode may not flush all JSON events to stdout before the process exits. The runner must handle partial output gracefully. If the JSON stream is incomplete (no text events), the runner should fall back to querying the SQLite database for the final assistant text. This provides a reliable two-tier reply extraction strategy.

### Session IDs are auto-assigned; first run captures, resume uses `--session`

OpenCode does not allow pre-assigning session IDs. Passing a nonexistent `--session` ID errors with `NotFoundError: Session not found`. Therefore:

- **First run:** Omit `--session`, use `--format json`, capture `sessionID` from the first JSON event line
- **Resume:** Pass `--session <captured_id>` to continue the existing session

This differs from Claude and Kimi (which accept pre-generated UUIDs). The `_run_backend` function for OpenCode must return `session_id=None` initially and populate it post-run from the JSON output. The `_opencode_command` function returns `(command, None)` instead of `(command, session_id)`.

### Host detection uses `OPENCODE=1` environment variable

OpenCode sets `OPENCODE=1` and `OPENCODE_PID=<pid>` in child process environments. It does **not** set `OPENCODE_SESSION_ID`. The `OPENCODE=1` flag is a reliable host detection marker, analogous to Codex's `CODEX_THREAD_ID`/`CODEX_HOME` and Claude's `CLAUDECODE`.

`_detect_host_backend()` should check `os.environ.get("OPENCODE")` and return `"opencode"` when it is set and non-empty.

### Transcript extraction reads SQLite directly, not `opencode export`

OpenCode stores all session data in SQLite at `~/.local/share/opencode/opencode.db`. The schema has:
- `session` table: `id`, `project_id`, `directory`, `title`, `time_created`, `time_updated`
- `message` table: `id`, `session_id`, `data` (JSON blob with `role`, `time`, `agent`, etc.), `time_created`
- `part` table: `id`, `message_id`, `session_id`, `data` (JSON blob with `type`, `text`, etc.), `time_created`

Direct SQLite lookup (Python's built-in `sqlite3` module, no dependencies) is faster and more reliable than shelling out to `opencode export`. It also avoids starting a full Node.js/Bun process for a simple DB read.

The transcript adapter should:
1. **Direct lookup** (`find_current_transcript`): Not available for OpenCode because there is no `OPENCODE_SESSION_ID` env var. Return `None` to force canary-based lookup.
2. **Canary lookup** (`find_matching_transcripts`): Query the `part` table for rows where `data` contains the canary string, join with `message` to get `session_id`, then identify the correct session. Search scope: parts with `type: "text"` where the text is a user-submitted message.
3. **Transcript extraction** (`extract_transcript`): Given a session ID (resolved from the canary match), query messages and parts ordered by `time_created`, extracting user text parts and assistant text parts into `TranscriptTurn` objects.

The adapter's `find_matching_transcripts` returns the session's virtual path (using the session ID as the path stem) so it can be passed to `extract_transcript`. Since OpenCode uses SQLite rather than JSONL files, the adapter needs a slightly different interface: `find_matching_transcripts` returns `list[Path]` where each "path" is a synthetic marker that `extract_transcript` interprets as a session ID to query. This follows the existing adapter contract shape but uses the path's stem as the session identifier.

**Important: two integration issues with synthetic paths.** Because these paths don't exist on disk:

1. **`choose_most_recent_match` in `build.py` calls `path.stat()`**, which would raise `FileNotFoundError`. Fix: in `build.py`, skip `choose_most_recent_match` when exactly one match is returned (nothing to sort). This is safe for all adapters. The SQL query already orders by `time_created DESC`, so the adapter should `LIMIT 1` in the query to guarantee a single result.

2. **DB path is lost between `find_matching_transcripts` and `extract_transcript`.** The `build.py` dispatcher passes `search_root` to `find_matching_transcripts` but only passes the chosen path to `extract_transcript`. For tests that redirect `--search-root` to a temp directory, `extract_transcript` would fail to find the DB at the default location. Fix: use a module-level `_last_resolved_db_path` variable in `opencode_cli.py`. `find_matching_transcripts` sets it after resolving the DB; `extract_transcript` reads it (falling back to `_resolve_db_path(None)` if unset).

**Alternative considered and rejected:** Using `opencode export <sessionID>` as a subprocess. This is simpler but slower (spawns a full process), and the session ID is not known from an env var so it would require the same DB query to find it anyway. Cutting out the middleman is cleaner.

### OpenCode auto-detection in `run_phase.py` transcript CLI

Add `"opencode"` to the `_detect_transcript_cli` function in `run_phase.py`: when `OPENCODE=1` is set, return `"opencode"`. This must be checked before the existing Codex and Claude checks because OpenCode can co-exist with those env vars if running within a compound agent setup. However, in practice, `OPENCODE=1` only appears when OpenCode is the host, so ordering it after Codex/Claude is fine. Place it after the existing checks but before the final error, consistent with the existing approach.

### Backend preference ordering

When OpenCode is the host backend, prefer `["opencode", "codex", "claude", "kimi"]`. When OpenCode is not the host, add it at the end of the fallback list: `["codex", "claude", "kimi", "opencode"]` (or `["claude", "codex", "kimi", "opencode"]` when Claude is the host).

### Model override via `TRYCYCLE_OPENCODE_MODEL`

Follow the existing pattern: add `"opencode": "TRYCYCLE_OPENCODE_MODEL"` to `MODEL_OVERRIDE_ENV_BY_BACKEND`. The format for OpenCode models is `provider/model` (e.g., `anthropic/claude-sonnet-4-20250514`).

### Effort mapping uses `--variant`

OpenCode uses `--variant` for reasoning effort (e.g., `high`, `max`, `minimal`). Map directly from trycycle's `--effort` to `--variant` since they use compatible value semantics.

### Permissions do not need special pre-configuration

OpenCode's `run` mode auto-denies `question`, `plan_enter`, and `plan_exit`. For other tools (bash, edit, write, read), the normal permission flow applies and the user gets prompted. No special pre-configuration is needed in `opencode.json`.

### Reply extraction from JSON events: two-tier approach

**Tier 1 (preferred): Parse stdout JSON events.** Collect all events with `type: "text"` from the final assistant message (the last group of events before the final `step_finish` with `reason: "stop"`). Concatenate their `.part.text` values.

**Tier 2 (deferred to live testing): Query SQLite.** If stdout parsing yields no text (e.g., due to incomplete event flushing), a fallback could query the `part` table for the session, filtering for `type: "text"` parts in the last assistant message, ordered by `time_created`. This is not implemented in the initial pass. The live integration test (Task 10) will reveal whether the JSON stream is reliably complete; if not, add the DB fallback as a follow-up.

### SKILL.md transcript-helper section: OpenCode uses canary-based lookup

Since OpenCode does not expose `OPENCODE_SESSION_ID` in child processes, transcript lookup requires a canary. The SKILL.md instructions should tell the orchestrator:
- For OpenCode, always run `mark_with_canary.py` first, capture the canary, then invoke the wrapper with `--transcript-cli opencode --canary "{CANARY}"`.

This is the same pattern as Claude Code's canary requirement.

### OpenCode skill discovery already works

OpenCode searches `~/.claude/skills/<name>/SKILL.md` among its skill paths, so a trycycle installed for Claude Code at `~/.claude/skills/trycycle/` is already discoverable by OpenCode. The README should note this. A dedicated install path at `~/.config/opencode/skills/trycycle` is also an option.

### `build.py` ADAPTERS: OpenCode uses SQLite, not JSONL

The existing adapter contract in `build.py` expects each adapter to have:
- `find_current_transcript(search_root=...) -> Path | None` (optional)
- `find_matching_transcripts(canary=..., timeout_ms=..., poll_ms=..., search_root=...) -> list[Path]`
- `extract_transcript(path: Path) -> list[TranscriptTurn]`

For OpenCode, `find_matching_transcripts` will search the SQLite DB for the canary in user message text parts and return synthetic `Path` objects (e.g., `Path(f"/opencode-session/{session_id}")`) that `extract_transcript` can parse back into a session ID for querying. This preserves the existing adapter contract without restructuring `build.py`. See the "Important: two integration issues with synthetic paths" note above for the `stat()` and DB-path-continuity fixes required.

---

## File structure

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `orchestrator/user-request-transcript/opencode_cli.py` | OpenCode transcript adapter: SQLite-based canary search and transcript extraction |
| Modify | `orchestrator/user-request-transcript/build.py` | Add `"opencode"` to ADAPTERS dict; skip `choose_most_recent_match` for single-match results |
| Modify | `orchestrator/subagent_runner.py` | Add `_probe_opencode`, `_opencode_command`, `_opencode_resume_command`, `_extract_opencode_reply_from_json`, `_extract_opencode_session_id_from_json`, integrate into `_run_backend`, `_resume_backend`, `_detect_host_backend`, `_detect_backend_preferences`, `_probe_backends`, `build_parser` |
| Modify | `orchestrator/run_phase.py` | Add `"opencode"` to `_detect_transcript_cli` and `--transcript-cli` choices |
| Modify | `SKILL.md` | Add OpenCode to transcript-helper section and backend-detection notes |
| Modify | `README.md` | Add OpenCode install line, badge, and compatibility mention |
| Modify | `tests/test_subagent_runner.py` | Add fake opencode binary, probe test, run test, resume test, host-detection test, reply-extraction tests |
| Modify | `tests/test_user_request_transcript_build.py` | Add OpenCode transcript adapter tests with SQLite fixtures |

---

### Task 1: OpenCode transcript adapter (`opencode_cli.py`)

**Files:**
- Create: `orchestrator/user-request-transcript/opencode_cli.py`
- Test: `tests/test_user_request_transcript_build.py`

- [ ] **Step 1: Write the failing test for OpenCode transcript extraction**

```python
# In tests/test_user_request_transcript_build.py, add:

import sqlite3

def _create_opencode_db(db_path: Path, sessions: list[dict]) -> None:
    """Create a minimal OpenCode SQLite DB with the given session/message/part data."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE session (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            directory TEXT NOT NULL,
            title TEXT NOT NULL,
            version TEXT NOT NULL,
            time_created INTEGER NOT NULL,
            time_updated INTEGER NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE message (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            time_created INTEGER NOT NULL,
            time_updated INTEGER NOT NULL,
            data TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE part (
            id TEXT PRIMARY KEY,
            message_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            time_created INTEGER NOT NULL,
            time_updated INTEGER NOT NULL,
            data TEXT NOT NULL
        )
    """)
    for session in sessions:
        conn.execute(
            "INSERT INTO session VALUES (?, ?, ?, ?, ?, ?, ?)",
            (session["id"], "proj1", session.get("directory", "/tmp"),
             session.get("title", "test"), "1.3.0",
             session.get("time_created", 1000), session.get("time_updated", 2000)),
        )
        for msg in session.get("messages", []):
            conn.execute(
                "INSERT INTO message VALUES (?, ?, ?, ?, ?)",
                (msg["id"], session["id"], msg.get("time_created", 1000),
                 msg.get("time_updated", 2000), json.dumps(msg["data"])),
            )
            for part in msg.get("parts", []):
                conn.execute(
                    "INSERT INTO part VALUES (?, ?, ?, ?, ?, ?)",
                    (part["id"], msg["id"], session["id"],
                     part.get("time_created", 1000), part.get("time_updated", 2000),
                     json.dumps(part["data"])),
                )
    conn.commit()
    conn.close()


class OpenCodeTranscriptTests(UserRequestTranscriptBuildTests):
    def test_opencode_canary_finds_correct_session(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            db_path = tmp_path / "opencode.db"
            canary = "trycycle-canary-12345678901234567890"
            _create_opencode_db(db_path, [
                {
                    "id": "ses_abc123",
                    "directory": "/tmp",
                    "time_created": 1000,
                    "time_updated": 2000,
                    "messages": [
                        {
                            "id": "msg_001",
                            "data": {"role": "user"},
                            "time_created": 1001,
                            "time_updated": 1001,
                            "parts": [
                                {
                                    "id": "prt_001",
                                    "data": {"type": "text", "text": f"Build something {canary}"},
                                    "time_created": 1001,
                                    "time_updated": 1001,
                                },
                            ],
                        },
                        {
                            "id": "msg_002",
                            "data": {"role": "assistant"},
                            "time_created": 1002,
                            "time_updated": 1002,
                            "parts": [
                                {
                                    "id": "prt_002",
                                    "data": {"type": "text", "text": "I'll help you build that."},
                                    "time_created": 1002,
                                    "time_updated": 1002,
                                },
                            ],
                        },
                    ],
                },
            ])
            result = self.run_builder(
                "--cli", "opencode",
                "--canary", canary,
                "--search-root", str(tmp_path),
                env={"HOME": str(tmp_path)},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            turns = json.loads(result.stdout)
            self.assertEqual(len(turns), 2)
            self.assertEqual(turns[0]["role"], "user")
            self.assertIn(canary, turns[0]["text"])
            self.assertEqual(turns[1]["role"], "assistant")
            self.assertEqual(turns[1]["text"], "I'll help you build that.")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /home/user/code/trycycle/.worktrees/add-opencode-support && python3 -m pytest tests/test_user_request_transcript_build.py::OpenCodeTranscriptTests::test_opencode_canary_finds_correct_session -v`
Expected: FAIL — `opencode` not recognized as a valid CLI name

- [ ] **Step 3: Write the OpenCode transcript adapter**

Create `orchestrator/user-request-transcript/opencode_cli.py`:

```python
from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path

from common import TranscriptError, TranscriptTurn


DEFAULT_DB_PATH = Path.home() / ".local" / "share" / "opencode" / "opencode.db"
OPENCODE_DATA_DIR_ENV = "OPENCODE_DATA_DIR"

# Module-level cache: set by find_matching_transcripts so extract_transcript
# can locate the DB without receiving search_root through the adapter contract.
_last_resolved_db_path: Path | None = None


def _resolve_db_path(search_root: Path | None) -> Path:
    if search_root is not None:
        db_path = search_root / "opencode.db"
        if db_path.exists():
            return db_path
        raise TranscriptError(f"OpenCode database not found at {db_path}")

    data_dir = os.environ.get(OPENCODE_DATA_DIR_ENV)
    if data_dir:
        db_path = Path(data_dir) / "opencode.db"
        if db_path.exists():
            return db_path

    if DEFAULT_DB_PATH.exists():
        return DEFAULT_DB_PATH

    raise TranscriptError(
        f"OpenCode database not found at {DEFAULT_DB_PATH}. "
        f"Set {OPENCODE_DATA_DIR_ENV} or pass --search-root."
    )


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def find_matching_transcripts(
    *,
    canary: str,
    timeout_ms: int,
    poll_ms: int,
    search_root: Path | None = None,
) -> list[Path]:
    global _last_resolved_db_path
    db_path = _resolve_db_path(search_root)
    _last_resolved_db_path = db_path
    deadline = time.monotonic() + (timeout_ms / 1000)

    while True:
        conn = _connect(db_path)
        try:
            rows = conn.execute(
                """
                SELECT DISTINCT p.session_id
                FROM part p
                JOIN message m ON p.message_id = m.id
                WHERE json_extract(m.data, '$.role') = 'user'
                  AND json_extract(p.data, '$.type') = 'text'
                  AND json_extract(p.data, '$.text') LIKE ?
                ORDER BY p.time_created DESC
                LIMIT 1
                """,
                (f"%{canary}%",),
            ).fetchall()
        finally:
            conn.close()

        if rows:
            return [Path(f"/opencode-session/{row['session_id']}") for row in rows]

        if time.monotonic() >= deadline:
            break
        time.sleep(poll_ms / 1000)

    raise TranscriptError(
        f"No OpenCode session contained canary {canary!r} within {timeout_ms}ms."
    )


def extract_transcript(path: Path) -> list[TranscriptTurn]:
    session_id = path.name
    db_path = _last_resolved_db_path if _last_resolved_db_path is not None else _resolve_db_path(None)
    conn = _connect(db_path)
    try:
        return _extract_session_transcript(conn, session_id)
    finally:
        conn.close()


def _extract_transcript_from_db(db_path: Path, session_id: str) -> list[TranscriptTurn]:
    conn = _connect(db_path)
    try:
        return _extract_session_transcript(conn, session_id)
    finally:
        conn.close()


def _extract_session_transcript(conn: sqlite3.Connection, session_id: str) -> list[TranscriptTurn]:
    rows = conn.execute(
        """
        SELECT m.id AS message_id, m.data AS message_data, m.time_created AS msg_time
        FROM message m
        WHERE m.session_id = ?
        ORDER BY m.time_created, m.id
        """,
        (session_id,),
    ).fetchall()

    selected_turns: list[TranscriptTurn] = []
    pending_assistant: TranscriptTurn | None = None
    saw_user = False

    for row_index, row in enumerate(rows):
        msg_data = json.loads(row["message_data"])
        role = msg_data.get("role")

        parts = conn.execute(
            """
            SELECT data, time_created
            FROM part
            WHERE message_id = ?
            ORDER BY time_created, id
            """,
            (row["message_id"],),
        ).fetchall()

        visible_text_parts = []
        for part_row in parts:
            part_data = json.loads(part_row["data"])
            if part_data.get("type") == "text":
                text = part_data.get("text", "")
                if text.strip():
                    visible_text_parts.append(text)

        visible_text = "".join(visible_text_parts).strip()
        if not visible_text:
            continue

        if role == "user":
            if saw_user and pending_assistant is not None:
                selected_turns.append(pending_assistant)
                pending_assistant = None
            selected_turns.append(
                TranscriptTurn(order=row_index, role="user", text=visible_text)
            )
            saw_user = True
        elif role == "assistant":
            pending_assistant = TranscriptTurn(
                order=row_index, role="assistant", text=visible_text,
            )

    if pending_assistant is not None:
        selected_turns.append(pending_assistant)

    return selected_turns
```

- [ ] **Step 4: Register the adapter in `build.py` and fix single-match handling**

In `orchestrator/user-request-transcript/build.py`:

1. Add the import and ADAPTERS entry:
```python
import opencode_cli

ADAPTERS = {
    "claude-code": claude_code,
    "codex-cli": codex_cli,
    "kimi-cli": kimi_cli,
    "opencode": opencode_cli,
}
```

2. In `main()`, fix the canary branch to skip `choose_most_recent_match` when exactly one match is returned (avoids `stat()` on synthetic paths that don't exist on disk):
```python
        matches = adapter.find_matching_transcripts(
            canary=args.canary,
            timeout_ms=args.timeout_ms,
            poll_ms=args.poll_ms,
            search_root=args.search_root,
        )
        if len(matches) == 1:
            chosen_path = matches[0]
        else:
            chosen_path = choose_most_recent_match(matches)
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd /home/user/code/trycycle/.worktrees/add-opencode-support && python3 -m pytest tests/test_user_request_transcript_build.py::OpenCodeTranscriptTests -v`
Expected: PASS

- [ ] **Step 6: Refactor and verify**

Verify the adapter handles edge cases:
- Multiple sessions with the canary (the SQL `LIMIT 1` returns only the most recent, so `choose_most_recent_match` is never called on synthetic paths)
- Sessions with no assistant reply (should still return user turns)
- The `_last_resolved_db_path` cache is set correctly by `find_matching_transcripts` and used by `extract_transcript`
- Empty text parts (should be excluded)

Run: `cd /home/user/code/trycycle/.worktrees/add-opencode-support && python3 -m pytest tests/test_user_request_transcript_build.py -v`
Expected: all PASS (including existing tests)

- [ ] **Step 7: Commit**

```bash
git -C /home/user/code/trycycle/.worktrees/add-opencode-support add orchestrator/user-request-transcript/opencode_cli.py orchestrator/user-request-transcript/build.py tests/test_user_request_transcript_build.py
git -C /home/user/code/trycycle/.worktrees/add-opencode-support commit -m "feat: add OpenCode transcript adapter with SQLite-based lookup"
```

---

### Task 2: OpenCode host detection and backend preference ordering

**Files:**
- Modify: `orchestrator/subagent_runner.py:213-227`
- Test: `tests/test_subagent_runner.py`

- [ ] **Step 1: Write the failing test for OpenCode host detection**

```python
# In tests/test_subagent_runner.py, add:

def _write_fake_opencode_binary(bin_dir: Path) -> Path:
    opencode_path = bin_dir / "opencode"
    opencode_path.write_text(
        textwrap.dedent(
            f"""\
            #!{sys.executable}
            import json
            import os
            import sys

            def read_flag_value(flag):
                if flag not in sys.argv:
                    return None
                index = sys.argv.index(flag)
                if index + 1 >= len(sys.argv):
                    return None
                return sys.argv[index + 1]

            def append_log():
                log_path = os.environ.get("FAKE_OPENCODE_LOG")
                if not log_path:
                    return
                with open(log_path, "a", encoding="utf-8") as handle:
                    handle.write(json.dumps({{"argv": sys.argv[1:]}}) + "\\n")

            append_log()

            if sys.argv[1:] == ["run", "--help"]:
                sys.stdout.write(
                    "opencode run [message..]\\n"
                    "run opencode with a message\\n"
                    "-s, --session\\n"
                    "-m, --model\\n"
                    "--dir\\n"
                    "--format\\n"
                    "--variant\\n"
                )
                raise SystemExit(0)

            if "--help" in sys.argv or "-h" in sys.argv:
                sys.stdout.write("opencode\\n--version\\n")
                raise SystemExit(0)

            # Simulate run mode
            session_id = read_flag_value("--session") or os.environ.get("FAKE_OPENCODE_SESSION_ID", "ses_fake_test_123")
            prompt_text = sys.stdin.read()
            mode = os.environ.get("FAKE_OPENCODE_MODE", "success")
            reply_text = os.environ.get("FAKE_OPENCODE_REPLY", "fake opencode reply")
            output_format = read_flag_value("--format") or "default"

            if mode == "failure":
                sys.stderr.write("Error: something went wrong\\n")
                raise SystemExit(1)

            if output_format == "json":
                msg_id = "msg_fake_001"
                # Emit JSON events
                events = [
                    {{"type": "step_start", "timestamp": 1000, "sessionID": session_id, "part": {{"id": "prt_001", "sessionID": session_id, "messageID": msg_id, "type": "step-start"}}}},
                    {{"type": "text", "timestamp": 1001, "sessionID": session_id, "part": {{"id": "prt_002", "sessionID": session_id, "messageID": msg_id, "type": "text", "text": reply_text, "time": {{"start": 1001, "end": 1001}}}}}},
                    {{"type": "step_finish", "timestamp": 1002, "sessionID": session_id, "part": {{"id": "prt_003", "sessionID": session_id, "messageID": msg_id, "type": "step-finish", "reason": "stop"}}}},
                ]
                for event in events:
                    sys.stdout.write(json.dumps(event) + "\\n")
            else:
                sys.stdout.write(reply_text)

            raise SystemExit(0)
            """
        ),
        encoding="utf-8",
    )
    opencode_path.chmod(0o755)
    return opencode_path


class OpenCodeTests(SubagentRunnerTests):
    def test_probe_detects_opencode_host_backend(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            bin_dir = tmp_path / "bin"
            home_dir = tmp_path / "home"
            bin_dir.mkdir()
            home_dir.mkdir()
            _write_fake_opencode_binary(bin_dir)

            result = self.run_runner(
                "probe",
                env={
                    "PATH": str(bin_dir),
                    "HOME": str(home_dir),
                    "OPENCODE": "1",
                },
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["host_backend"], "opencode")
            self.assertEqual(payload["selected_backend"], "opencode")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /home/user/code/trycycle/.worktrees/add-opencode-support && python3 -m pytest tests/test_subagent_runner.py::OpenCodeTests::test_probe_detects_opencode_host_backend -v`
Expected: FAIL — `opencode` not in backends

- [ ] **Step 3: Implement host detection and backend ordering**

In `orchestrator/subagent_runner.py`, modify:

```python
# Add to MODEL_OVERRIDE_ENV_BY_BACKEND:
MODEL_OVERRIDE_ENV_BY_BACKEND = {
    "codex": "TRYCYCLE_CODEX_MODEL",
    "claude": "TRYCYCLE_CLAUDE_MODEL",
    "kimi": "TRYCYCLE_KIMI_MODEL",
    "opencode": "TRYCYCLE_OPENCODE_MODEL",
}

# Modify _detect_host_backend:
def _detect_host_backend() -> str | None:
    if os.environ.get("CODEX_THREAD_ID") or os.environ.get("CODEX_HOME"):
        return "codex"
    if os.environ.get("CLAUDECODE"):
        return "claude"
    if os.environ.get("OPENCODE"):
        return "opencode"
    return None

# Modify _detect_backend_preferences:
def _detect_backend_preferences() -> list[str]:
    host_backend = _detect_host_backend()
    if host_backend == "codex":
        return ["codex", "claude", "kimi", "opencode"]
    if host_backend == "claude":
        return ["claude", "codex", "kimi", "opencode"]
    if host_backend == "opencode":
        return ["opencode", "codex", "claude", "kimi"]
    return ["codex", "claude", "kimi", "opencode"]
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd /home/user/code/trycycle/.worktrees/add-opencode-support && python3 -m pytest tests/test_subagent_runner.py::OpenCodeTests::test_probe_detects_opencode_host_backend -v`
Expected: PASS

- [ ] **Step 5: Refactor and verify**

Run: `cd /home/user/code/trycycle/.worktrees/add-opencode-support && python3 -m pytest tests/test_subagent_runner.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git -C /home/user/code/trycycle/.worktrees/add-opencode-support add orchestrator/subagent_runner.py tests/test_subagent_runner.py
git -C /home/user/code/trycycle/.worktrees/add-opencode-support commit -m "feat: add OpenCode host detection and backend preference ordering"
```

---

### Task 3: OpenCode probe function

**Files:**
- Modify: `orchestrator/subagent_runner.py` (add `_probe_opencode`, update `_probe_backends`)
- Test: `tests/test_subagent_runner.py`

- [ ] **Step 1: Write the failing test for OpenCode probe**

```python
def test_probe_selects_opencode_when_it_is_the_only_available_backend(self):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        bin_dir = tmp_path / "bin"
        home_dir = tmp_path / "home"
        bin_dir.mkdir()
        home_dir.mkdir()
        _write_fake_opencode_binary(bin_dir)

        result = self.run_runner(
            "probe",
            env={
                "PATH": str(bin_dir),
                "HOME": str(home_dir),
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["selected_backend"], "opencode")
        self.assertTrue(payload["backends"]["opencode"]["available"])
        self.assertTrue(payload["backends"]["opencode"]["supports_resume"])
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /home/user/code/trycycle/.worktrees/add-opencode-support && python3 -m pytest tests/test_subagent_runner.py::OpenCodeTests::test_probe_selects_opencode_when_it_is_the_only_available_backend -v`
Expected: FAIL — `_probe_opencode` not defined

- [ ] **Step 3: Implement the probe function**

```python
def _probe_opencode(binary: str) -> dict[str, Any]:
    path = _resolve_binary(binary)
    if path is None:
        return {
            "available": False,
            "binary": binary,
            "reason": "binary not found on PATH",
        }

    ok, output = _run_probe([path, "run", "--help"])
    if not ok:
        return {
            "available": False,
            "binary": path,
            "reason": output,
        }

    required_tokens = ["--session", "--model", "--dir", "--format"]
    missing = [token for token in required_tokens if token not in output]
    if missing:
        return {
            "available": False,
            "binary": path,
            "reason": f"missing required help tokens: {', '.join(missing)}",
        }

    return {
        "available": True,
        "binary": path,
        "supports_resume": True,
    }
```

Update `_probe_backends`:
```python
def _probe_backends() -> dict[str, Any]:
    backends = {
        "codex": _probe_codex("codex"),
        "claude": _probe_claude("claude"),
        "kimi": _probe_kimi("kimi"),
        "opencode": _probe_opencode("opencode"),
    }
    # ... rest unchanged
```

Update `build_parser` backend choices to include `"opencode"`:
```python
choices=["auto", "host", "codex", "claude", "kimi", "opencode"],
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd /home/user/code/trycycle/.worktrees/add-opencode-support && python3 -m pytest tests/test_subagent_runner.py::OpenCodeTests::test_probe_selects_opencode_when_it_is_the_only_available_backend -v`
Expected: PASS

- [ ] **Step 5: Refactor and verify**

Run: `cd /home/user/code/trycycle/.worktrees/add-opencode-support && python3 -m pytest tests/test_subagent_runner.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git -C /home/user/code/trycycle/.worktrees/add-opencode-support add orchestrator/subagent_runner.py tests/test_subagent_runner.py
git -C /home/user/code/trycycle/.worktrees/add-opencode-support commit -m "feat: add OpenCode probe function and backend registration"
```

---

### Task 4: OpenCode command builders and JSON reply extraction

**Files:**
- Modify: `orchestrator/subagent_runner.py` (add `_opencode_command`, `_opencode_resume_command`, `_extract_opencode_reply_from_json`, `_extract_opencode_session_id_from_json`)
- Test: `tests/test_subagent_runner.py`

- [ ] **Step 1: Write the failing test for OpenCode run**

```python
def test_run_with_opencode_backend_returns_ok_with_json_reply(self):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        bin_dir = tmp_path / "bin"
        home_dir = tmp_path / "home"
        workdir = tmp_path / "work"
        artifacts_dir = tmp_path / "artifacts"
        prompt_path = tmp_path / "prompt.txt"
        log_path = tmp_path / "opencode-log.jsonl"
        bin_dir.mkdir()
        home_dir.mkdir()
        workdir.mkdir()
        prompt_path.write_text("Test prompt for opencode\n", encoding="utf-8")
        _write_fake_opencode_binary(bin_dir)

        result = self.run_runner(
            "run",
            "--phase", "smoke",
            "--prompt-file", str(prompt_path),
            "--workdir", str(workdir),
            "--artifacts-dir", str(artifacts_dir),
            "--backend", "opencode",
            "--model", "anthropic/claude-sonnet-4-20250514",
            "--effort", "high",
            env={
                "PATH": str(bin_dir),
                "HOME": str(home_dir),
                "FAKE_OPENCODE_LOG": str(log_path),
                "FAKE_OPENCODE_MODE": "success",
                "FAKE_OPENCODE_REPLY": "opencode test reply",
                "FAKE_OPENCODE_SESSION_ID": "ses_test_abc123",
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["backend"], "opencode")
        self.assertEqual(payload["session_id"], "ses_test_abc123")
        reply_path = Path(payload["reply_path"])
        self.assertEqual(reply_path.read_text(encoding="utf-8"), "opencode test reply")
        log_records = _read_jsonl(log_path)
        argv = log_records[-1]["argv"]
        self.assertIn("run", argv)
        self.assertIn("--format", argv)
        self.assertIn("json", argv)
        self.assertIn("--dir", argv)
        self.assertIn(str(workdir), argv)
        self.assertIn("--model", argv)
        self.assertIn("anthropic/claude-sonnet-4-20250514", argv)
        self.assertIn("--variant", argv)
        self.assertIn("high", argv)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /home/user/code/trycycle/.worktrees/add-opencode-support && python3 -m pytest tests/test_subagent_runner.py::OpenCodeTests::test_run_with_opencode_backend_returns_ok_with_json_reply -v`
Expected: FAIL — `opencode` not a supported backend in `_run_backend`

- [ ] **Step 3: Implement command builders and reply extraction**

```python
def _extract_opencode_session_id_from_json(stdout: str) -> str | None:
    """Extract the sessionID from the first JSON event line."""
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        session_id = event.get("sessionID")
        if session_id:
            return session_id
    return None


def _extract_opencode_reply_from_json(stdout: str) -> str:
    """Extract reply text from JSON event stream.

    Collects all 'text' type events from the final assistant step
    (between the last step_start and the final step_finish with reason 'stop').
    """
    text_parts: list[str] = []
    in_current_step = False

    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        event_type = event.get("type")
        if event_type == "step_start":
            # New step: reset collected text
            text_parts = []
            in_current_step = True
        elif event_type == "text" and in_current_step:
            part = event.get("part", {})
            text = part.get("text", "")
            if text:
                text_parts.append(text)
        elif event_type == "step_finish":
            part = event.get("part", {})
            if part.get("reason") == "stop":
                # This is the final stop; text_parts has the reply
                break
            # Tool-call step finish; text will be reset on next step_start

    return "".join(text_parts)


def _opencode_command(
    *,
    binary: str,
    workdir: Path,
    effort: str | None,
    model: str | None,
) -> tuple[list[str], None]:
    command = [
        binary,
        "run",
        "--dir",
        str(workdir),
        "--format",
        "json",
    ]
    if model:
        command.extend(["--model", model])
    if effort:
        command.extend(["--variant", effort])
    return command, None


def _opencode_resume_command(
    *,
    binary: str,
    session_id: str,
    workdir: Path,
    effort: str | None,
    model: str | None,
) -> list[str]:
    command = [
        binary,
        "run",
        "--session",
        session_id,
        "--dir",
        str(workdir),
        "--format",
        "json",
    ]
    if model:
        command.extend(["--model", model])
    if effort:
        command.extend(["--variant", effort])
    return command
```

Then integrate into `_run_backend`:
```python
elif backend == "opencode":
    command, session_id = _opencode_command(
        binary=binary,
        workdir=workdir,
        effort=effort,
        model=model,
    )
    cwd = workdir
```

And in the reply-extraction section of `_run_backend`, after `subprocess.run`:
```python
if backend == "opencode":
    reply_text = _extract_opencode_reply_from_json(result.stdout or "")
    reply_path.write_text(reply_text, encoding="utf-8")
    if session_id is None:
        session_id = _extract_opencode_session_id_from_json(result.stdout or "")
```

Similarly integrate into `_resume_backend` and `_classify_run_result`.

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd /home/user/code/trycycle/.worktrees/add-opencode-support && python3 -m pytest tests/test_subagent_runner.py::OpenCodeTests::test_run_with_opencode_backend_returns_ok_with_json_reply -v`
Expected: PASS

- [ ] **Step 5: Refactor and verify**

Run: `cd /home/user/code/trycycle/.worktrees/add-opencode-support && python3 -m pytest tests/test_subagent_runner.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git -C /home/user/code/trycycle/.worktrees/add-opencode-support add orchestrator/subagent_runner.py tests/test_subagent_runner.py
git -C /home/user/code/trycycle/.worktrees/add-opencode-support commit -m "feat: add OpenCode command builders and JSON reply extraction"
```

---

### Task 5: OpenCode resume support

**Files:**
- Modify: `orchestrator/subagent_runner.py` (integrate `_opencode_resume_command` into `_resume_backend`)
- Test: `tests/test_subagent_runner.py`

- [ ] **Step 1: Write the failing test for OpenCode resume**

```python
def test_resume_with_opencode_backend_returns_ok(self):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        bin_dir = tmp_path / "bin"
        home_dir = tmp_path / "home"
        workdir = tmp_path / "work"
        artifacts_dir = tmp_path / "artifacts"
        prompt_path = tmp_path / "prompt.txt"
        log_path = tmp_path / "opencode-log.jsonl"
        bin_dir.mkdir()
        home_dir.mkdir()
        workdir.mkdir()
        prompt_path.write_text("Resume prompt\n", encoding="utf-8")
        _write_fake_opencode_binary(bin_dir)

        result = self.run_runner(
            "resume",
            "--phase", "execute",
            "--session-id", "ses_existing_session",
            "--prompt-file", str(prompt_path),
            "--workdir", str(workdir),
            "--artifacts-dir", str(artifacts_dir),
            "--backend", "opencode",
            env={
                "PATH": str(bin_dir),
                "HOME": str(home_dir),
                "FAKE_OPENCODE_LOG": str(log_path),
                "FAKE_OPENCODE_MODE": "success",
                "FAKE_OPENCODE_REPLY": "resumed reply text",
                "FAKE_OPENCODE_SESSION_ID": "ses_existing_session",
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["backend"], "opencode")
        self.assertEqual(payload["session_id"], "ses_existing_session")
        reply_path = Path(payload["reply_path"])
        self.assertEqual(reply_path.read_text(encoding="utf-8"), "resumed reply text")
        log_records = _read_jsonl(log_path)
        argv = log_records[-1]["argv"]
        self.assertIn("--session", argv)
        self.assertIn("ses_existing_session", argv)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /home/user/code/trycycle/.worktrees/add-opencode-support && python3 -m pytest tests/test_subagent_runner.py::OpenCodeTests::test_resume_with_opencode_backend_returns_ok -v`
Expected: FAIL

- [ ] **Step 3: Integrate resume into `_resume_backend`**

Add the `opencode` branch:
```python
elif backend == "opencode":
    command = _opencode_resume_command(
        binary=binary,
        session_id=session_id,
        workdir=workdir,
        effort=effort,
        model=model,
    )
    cwd = workdir
```

And the reply extraction for resume:
```python
if backend == "opencode":
    reply_text = _extract_opencode_reply_from_json(result.stdout or "")
    reply_path.write_text(reply_text, encoding="utf-8")
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd /home/user/code/trycycle/.worktrees/add-opencode-support && python3 -m pytest tests/test_subagent_runner.py::OpenCodeTests::test_resume_with_opencode_backend_returns_ok -v`
Expected: PASS

- [ ] **Step 5: Refactor and verify**

Run: `cd /home/user/code/trycycle/.worktrees/add-opencode-support && python3 -m pytest tests/test_subagent_runner.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git -C /home/user/code/trycycle/.worktrees/add-opencode-support add orchestrator/subagent_runner.py tests/test_subagent_runner.py
git -C /home/user/code/trycycle/.worktrees/add-opencode-support commit -m "feat: add OpenCode session resume support"
```

---

### Task 6: OpenCode dry-run and host-backend integration

**Files:**
- Modify: `orchestrator/subagent_runner.py`
- Test: `tests/test_subagent_runner.py`

- [ ] **Step 1: Write the failing test for host-backend dry run**

```python
def test_run_with_host_backend_uses_opencode_when_opencode_is_host(self):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        bin_dir = tmp_path / "bin"
        home_dir = tmp_path / "home"
        workdir = tmp_path / "work"
        artifacts_dir = tmp_path / "artifacts"
        prompt_path = tmp_path / "prompt.txt"
        bin_dir.mkdir()
        home_dir.mkdir()
        workdir.mkdir()
        prompt_path.write_text("host backend dry run\n", encoding="utf-8")
        fake_opencode = _write_fake_opencode_binary(bin_dir)

        result = self.run_runner(
            "run",
            "--phase", "smoke",
            "--prompt-file", str(prompt_path),
            "--workdir", str(workdir),
            "--artifacts-dir", str(artifacts_dir),
            "--backend", "host",
            "--dry-run",
            env={
                "PATH": str(bin_dir),
                "HOME": str(home_dir),
                "OPENCODE": "1",
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["backend"], "opencode")
        self.assertEqual(payload["process"]["command"][0], str(fake_opencode))
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /home/user/code/trycycle/.worktrees/add-opencode-support && python3 -m pytest tests/test_subagent_runner.py::OpenCodeTests::test_run_with_host_backend_uses_opencode_when_opencode_is_host -v`
Expected: FAIL or PASS (may already pass from Task 2/3 integration)

- [ ] **Step 3: Fix any remaining integration issues**

If the test already passes, add a test for the `--backend opencode` choice in the parser being accepted.

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd /home/user/code/trycycle/.worktrees/add-opencode-support && python3 -m pytest tests/test_subagent_runner.py::OpenCodeTests -v`
Expected: all PASS

- [ ] **Step 5: Refactor and verify**

Run: `cd /home/user/code/trycycle/.worktrees/add-opencode-support && python3 -m pytest tests/test_subagent_runner.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git -C /home/user/code/trycycle/.worktrees/add-opencode-support add orchestrator/subagent_runner.py tests/test_subagent_runner.py
git -C /home/user/code/trycycle/.worktrees/add-opencode-support commit -m "feat: add OpenCode host-backend and dry-run integration"
```

---

### Task 7: OpenCode transcript CLI detection in `run_phase.py`

**Files:**
- Modify: `orchestrator/run_phase.py:48-55` (`_detect_transcript_cli`), line ~287 (`--transcript-cli` choices)
- Test: `tests/test_run_phase.py`

- [ ] **Step 1: Write the failing test for OpenCode transcript CLI auto-detection**

```python
# In tests/test_run_phase.py, verify that when OPENCODE=1 is set,
# the auto-detection resolves to "opencode"
def test_detect_transcript_cli_auto_resolves_opencode_when_opencode_is_host(self):
    # ... test that --transcript-cli auto with OPENCODE=1 env resolves to opencode
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /home/user/code/trycycle/.worktrees/add-opencode-support && python3 -m pytest tests/test_run_phase.py -k opencode -v`
Expected: FAIL

- [ ] **Step 3: Implement the changes**

In `orchestrator/run_phase.py`:

Update `_detect_transcript_cli`:
```python
def _detect_transcript_cli(selected: str) -> str:
    if selected != "auto":
        return selected
    if os.environ.get("CODEX_THREAD_ID") or os.environ.get("CODEX_HOME"):
        return "codex-cli"
    if os.environ.get("CLAUDECODE"):
        return "claude-code"
    if os.environ.get("OPENCODE"):
        return "opencode"
    raise PhaseError("Could not detect transcript CLI. Pass --transcript-cli explicitly.")
```

Update `--transcript-cli` choices:
```python
choices=["auto", "codex-cli", "claude-code", "kimi-cli", "opencode"],
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd /home/user/code/trycycle/.worktrees/add-opencode-support && python3 -m pytest tests/test_run_phase.py -v`
Expected: all PASS

- [ ] **Step 5: Refactor and verify**

Run: `cd /home/user/code/trycycle/.worktrees/add-opencode-support && python3 -m pytest tests/ -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git -C /home/user/code/trycycle/.worktrees/add-opencode-support add orchestrator/run_phase.py tests/test_run_phase.py
git -C /home/user/code/trycycle/.worktrees/add-opencode-support commit -m "feat: add OpenCode to transcript CLI auto-detection and choices"
```

---

### Task 8: Update SKILL.md with OpenCode transcript-helper instructions

**Files:**
- Modify: `SKILL.md:44-51` (transcript placeholder helper section)

- [ ] **Step 1: Write the failing test (manual review)**

This is a documentation change, not code. Verify the current SKILL.md does not mention OpenCode.

- [ ] **Step 2: Update the SKILL.md transcript-helper section**

In `SKILL.md`, update the "Transcript placeholder helper" section to add an OpenCode entry. After the existing item 4 (Claude Code), add:

```markdown
5. For OpenCode, always run `python3 <skill-directory>/orchestrator/user-request-transcript/mark_with_canary.py` as a separate top-level command first, capture stdout exactly as `{CANARY}`, then invoke the wrapper with `--transcript-cli opencode --canary "{CANARY}"`.
```

Also add OpenCode to the "Subagent Defaults" section's fallback-runner note:
```markdown
  - In fallback-runner mode, use `--backend host` by default so fresh subagents stay on the parent backend. When the host agent is Kimi, use `--backend kimi` explicitly. When the host agent is OpenCode, `--backend host` works correctly because `OPENCODE=1` is detectable.
```

- [ ] **Step 3: Verify no existing behavior is broken**

Read the updated SKILL.md and confirm the changes are coherent and consistent with the existing structure.

- [ ] **Step 4: Commit**

```bash
git -C /home/user/code/trycycle/.worktrees/add-opencode-support add SKILL.md
git -C /home/user/code/trycycle/.worktrees/add-opencode-support commit -m "docs: add OpenCode to SKILL.md transcript-helper and subagent defaults"
```

---

### Task 9: Update README.md with OpenCode installation and badges

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add OpenCode install line**

In the "If you've been sent here by your human" section, after the Kimi CLI line, add:

```markdown
- **OpenCode:** `git clone https://github.com/danshapiro/trycycle.git ~/.config/opencode/skills/trycycle`
```

Also note that OpenCode discovers skills at `~/.claude/skills/` too, so existing Claude Code installs are automatically available:

```markdown
> **Note:** OpenCode also discovers skills installed at `~/.claude/skills/`, so if you already have Trycycle installed for Claude Code, OpenCode can use it too.
```

- [ ] **Step 2: Update the tagline and badges**

Update the tagline to include OpenCode:
```html
<em>A skill for Claude Code, Codex CLI, Kimi CLI, and OpenCode that plans, strengthens, and reviews your code -- automatically.</em>
```

Add an OpenCode badge:
```html
<a href="https://github.com/anomalyco/opencode"><img src="https://img.shields.io/badge/works%20with-OpenCode-FF6B35" alt="Works with OpenCode" /></a>
```

Update the Topics comment to include `opencode`.

- [ ] **Step 3: Update the "Getting Started" human instructions**

Add OpenCode to the list: "Tell your favorite coding agent (Claude Code, Codex CLI, Kimi CLI, OpenCode, etc.):"

- [ ] **Step 4: Commit**

```bash
git -C /home/user/code/trycycle/.worktrees/add-opencode-support add README.md
git -C /home/user/code/trycycle/.worktrees/add-opencode-support commit -m "docs: add OpenCode installation, badges, and compatibility to README"
```

---

### Task 10: Live integration test with real OpenCode

**Files:**
- Modify: `tests/test_subagent_runner.py`

- [ ] **Step 1: Write a live integration test gated on `TRYCYCLE_RUN_LIVE_OPENCODE_TESTS`**

```python
@unittest.skipUnless(
    os.environ.get("TRYCYCLE_RUN_LIVE_OPENCODE_TESTS") == "1",
    "Live OpenCode tests require TRYCYCLE_RUN_LIVE_OPENCODE_TESTS=1",
)
class LiveOpenCodeTests(SubagentRunnerTests):
    def test_live_opencode_run_and_resume(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            workdir = tmp_path / "work"
            artifacts_dir_run = tmp_path / "artifacts_run"
            artifacts_dir_resume = tmp_path / "artifacts_resume"
            prompt_path = tmp_path / "prompt.txt"
            resume_prompt_path = tmp_path / "resume_prompt.txt"
            workdir.mkdir()
            prompt_path.write_text("Say exactly: TRYCYCLE_OPENCODE_LIVE_TEST\n", encoding="utf-8")

            # Run
            result = self.run_runner(
                "run",
                "--phase", "live-smoke",
                "--prompt-file", str(prompt_path),
                "--workdir", str(workdir),
                "--artifacts-dir", str(artifacts_dir_run),
                "--backend", "opencode",
                "--timeout-seconds", "120",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["backend"], "opencode")
            self.assertTrue(payload["session_id"])
            self.assertIn("TRYCYCLE_OPENCODE_LIVE_TEST", Path(payload["reply_path"]).read_text(encoding="utf-8"))

            # Resume
            session_id = payload["session_id"]
            resume_prompt_path.write_text("What was my previous message?\n", encoding="utf-8")
            resume_result = self.run_runner(
                "resume",
                "--phase", "live-smoke",
                "--session-id", session_id,
                "--prompt-file", str(resume_prompt_path),
                "--workdir", str(workdir),
                "--artifacts-dir", str(artifacts_dir_resume),
                "--backend", "opencode",
                "--timeout-seconds", "120",
            )
            self.assertEqual(resume_result.returncode, 0, resume_result.stderr)
            resume_payload = json.loads(resume_result.stdout)
            self.assertEqual(resume_payload["status"], "ok")
            self.assertEqual(resume_payload["session_id"], session_id)
```

- [ ] **Step 2: Run the live test**

Run: `cd /home/user/code/trycycle/.worktrees/add-opencode-support && TRYCYCLE_RUN_LIVE_OPENCODE_TESTS=1 python3 -m pytest tests/test_subagent_runner.py::LiveOpenCodeTests -v --timeout=300`
Expected: PASS (or investigate failures)

- [ ] **Step 3: Refactor based on live test results**

Fix any issues discovered during live testing (e.g., reply extraction edge cases, session ID capture timing).

- [ ] **Step 4: Run the full test suite**

Run: `cd /home/user/code/trycycle/.worktrees/add-opencode-support && python3 -m pytest tests/ -v`
Expected: all PASS (live tests skipped without env var)

- [ ] **Step 5: Commit**

```bash
git -C /home/user/code/trycycle/.worktrees/add-opencode-support add tests/test_subagent_runner.py
git -C /home/user/code/trycycle/.worktrees/add-opencode-support commit -m "test: add live OpenCode integration test (gated on env var)"
```

---

### Task 11: Full regression and cleanup

**Files:**
- All modified files

- [ ] **Step 1: Run the complete test suite**

Run: `cd /home/user/code/trycycle/.worktrees/add-opencode-support && python3 -m pytest tests/ -v`
Expected: all PASS

- [ ] **Step 2: Run the live OpenCode tests**

Run: `cd /home/user/code/trycycle/.worktrees/add-opencode-support && TRYCYCLE_RUN_LIVE_OPENCODE_TESTS=1 python3 -m pytest tests/test_subagent_runner.py::LiveOpenCodeTests -v --timeout=300`
Expected: PASS

- [ ] **Step 3: Verify the parser description and help text**

Run: `cd /home/user/code/trycycle/.worktrees/add-opencode-support && python3 orchestrator/subagent_runner.py --help`
Verify: description mentions OpenCode alongside Codex, Claude, and Kimi.

Run: `cd /home/user/code/trycycle/.worktrees/add-opencode-support && python3 orchestrator/subagent_runner.py run --help`
Verify: `--backend` choices include `opencode`.

- [ ] **Step 4: Verify probe detects the real opencode binary**

Run: `cd /home/user/code/trycycle/.worktrees/add-opencode-support && python3 orchestrator/subagent_runner.py probe | python3 -m json.tool`
Verify: `backends.opencode.available` is `true`.

- [ ] **Step 5: Clean up any debug or scratch artifacts**

Remove any temporary test files or debug output left during development.

- [ ] **Step 6: Final commit if needed**

```bash
git -C /home/user/code/trycycle/.worktrees/add-opencode-support add -A
git -C /home/user/code/trycycle/.worktrees/add-opencode-support commit -m "chore: final cleanup for OpenCode support"
```
