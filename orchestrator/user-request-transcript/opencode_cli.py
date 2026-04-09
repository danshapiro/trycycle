from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path

from common import TranscriptError, TranscriptTurn


DEFAULT_DB_PATH = Path.home() / ".local" / "share" / "opencode" / "opencode.db"
OPENCODE_DATA_DIR_ENV = "OPENCODE_DATA_DIR"
OPENCODE_PID_ENV = "OPENCODE_PID"

# Module-level cache: set by find_matching_transcripts or find_current_transcript
# so extract_transcript can locate the DB without receiving search_root through
# the adapter contract.
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


def _session_id_from_proc() -> str | None:
    pid_str = os.environ.get(OPENCODE_PID_ENV)
    if not pid_str:
        return None
    try:
        pid = int(pid_str)
    except ValueError:
        return None
    try:
        cmdline_bytes = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return None
    parts = cmdline_bytes.decode("utf-8", errors="replace").split("\x00")
    for i, part in enumerate(parts):
        if part == "--session" and i + 1 < len(parts):
            return parts[i + 1]
        if part.startswith("--session="):
            return part.split("=", 1)[1]
    return None


def find_current_transcript(search_root: Path | None = None) -> Path | None:
    global _last_resolved_db_path
    session_id = _session_id_from_proc()
    if not session_id:
        return None
    try:
        db_path = _resolve_db_path(search_root)
    except TranscriptError:
        return None
    _last_resolved_db_path = db_path
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT id FROM session WHERE id = ?",
            (session_id,),
        ).fetchone()
    finally:
        conn.close()
    if row:
        return Path(f"/opencode-session/{session_id}")
    return None


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
                WHERE (
                    (json_extract(p.data, '$.type') = 'text'
                     AND json_extract(p.data, '$.text') LIKE ?)
                    OR
                    (json_extract(p.data, '$.type') = 'tool'
                     AND json_extract(p.data, '$.state') LIKE ?)
                )
                ORDER BY p.time_created DESC
                LIMIT 1
                """,
                (f"%{canary}%", f"%{canary}%"),
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
