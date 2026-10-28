#!/usr/bin/env python3
"""
Deterministic repair for OpenCode task tool empty results.

When OpenCode's native task tool returns empty <task_result> because the
subagent's final assistant message has no text parts, this script reads
the session database and extracts tool outputs + reasoning as text.

Database schema (from opencode.db):
  session(id, parent_id, ...)
  message(id, session_id, data)
  part(id, message_id, session_id, time_created, data)
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

#: Maximum characters per individual tool output before truncation.
MAX_TOOL_OUTPUT_CHARS = 15000

#: Maximum total extracted text characters before truncating the full result.
MAX_TOTAL_OUTPUT_CHARS = 80000

#: Maximum steps (back from the last step) to include tool outputs from.
MAX_TOOL_STEPS = 3

#: Known OpenCode wrapper close-tag prefixes that should be filtered from text.
_CLOSE_TAG_PREFIXES = ("</task_result", "</task", "</tool_result", "</tool_call")


class RepairError(Exception):
    """Repair script failure that should be surfaced to the orchestrator."""


_DB_NOT_FOUND = "Cannot find opencode.db. Set OPENCODE_DB_PATH or OPENCODE_DATA_DIR."


def resolve_db_path() -> Path:
    """Find the OpenCode database path.

    Checks in order: OPENCODE_DB_PATH, OPENCODE_DATA_DIR, XDG_DATA_HOME,
    ~/.local/share, Windows AppData via WSL.
    """
    # Explicit env var override (recommended by error messages)
    env_path = os.environ.get("OPENCODE_DB_PATH")
    if env_path:
        db_path = Path(env_path)
        if db_path.exists():
            return db_path
        raise FileNotFoundError(
            f"OPENCODE_DB_PATH is set but file not found: {db_path}"
        )

    # OPENCODE_DATA_DIR (custom data root)
    data_dir = os.environ.get("OPENCODE_DATA_DIR")
    if data_dir:
        db_path = Path(data_dir) / "opencode.db"
        if db_path.exists():
            return db_path

    # XDG data directory
    data_home = os.environ.get(
        "XDG_DATA_HOME", os.path.expanduser("~/.local/share")
    )
    db_path = Path(data_home) / "opencode" / "opencode.db"
    if db_path.exists():
        return db_path

    # macOS
    macos_path = (
        Path.home() / "Library" / "Application Support" / "opencode" / "opencode.db"
    )
    if macos_path.exists():
        return macos_path

    # Native Windows (honored even under WSL when LOCALAPPDATA is set)
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        p = Path(local_appdata) / "opencode" / "opencode.db"
        if p.exists():
            return p

    # Windows AppData via WSL mount (native Windows OpenCode, not WSL-internal)
    for base in ["/mnt/c/Users"]:
        try:
            for user_dir in Path(base).iterdir():
                if user_dir.is_dir():
                    p = user_dir / "AppData" / "Local" / "opencode" / "opencode.db"
                    if p.exists():
                        return p
        except (FileNotFoundError, PermissionError):
            continue

    raise RepairError(_DB_NOT_FOUND)


def get_parts(db_path: Path, session_id: str) -> list[dict[str, Any]]:
    """Return all parts for a session, ordered by time_created then id."""
    with sqlite3.connect(str(db_path), timeout=5) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT data FROM part WHERE session_id = ? ORDER BY time_created, id",
            (session_id,),
        ).fetchall()
    parts: list[dict[str, Any]] = []
    for row in rows:
        try:
            parsed = json.loads(row["data"])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            parts.append(parsed)
    return parts


def skip_preamble(parts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop parts before the first step-start (user message text preamble)."""
    for i, part in enumerate(parts):
        if part.get("type") == "step-start":
            return parts[i:]
    return parts


def _safe_text(part: dict[str, Any], key: str = "text") -> str:
    """Extract a text field safely, returning '' for missing or None values."""
    value = part.get(key)
    return str(value) if value is not None else ""


def _is_relevant_text(text: str) -> bool:
    """Return True if the text looks like real content, not XML wrapper noise."""
    stripped = text.strip()
    if not stripped:
        return False
    for prefix in _CLOSE_TAG_PREFIXES:
        if stripped.startswith(prefix):
            return False
    return True


def _find_step_boundaries(parts: list[dict[str, Any]]) -> list[tuple[int, int]]:
    """Return (start_index, end_index) pairs for each step in the parts list.

    A step runs from a step-start to its matching step-finish (inclusive).
    """
    boundaries: list[tuple[int, int]] = []
    stack: list[int] = []
    for i, part in enumerate(parts):
        ptype = part.get("type")
        if ptype == "step-start":
            stack.append(i)
        elif ptype == "step-finish":
            if stack:
                boundaries.append((stack.pop(), i))
            else:
                boundaries.append((0, i))
    for start_idx in stack:
        boundaries.append((start_idx, len(parts) - 1))
    boundaries.sort(key=lambda b: b[0])
    return boundaries


def format_parts(parts: list[dict[str, Any]]) -> str:
    """Format message parts into readable text.

    Extracts tool outputs from the most recent steps (last MAX_TOOL_STEPS),
    and reasoning/text from the final step only. Total output is capped.
    """
    lines: list[str] = []
    total_len = 0

    def append(content: str) -> None:
        nonlocal total_len
        remaining = MAX_TOTAL_OUTPUT_CHARS - total_len
        if remaining <= 0:
            return
        if len(content) > remaining:
            content = content[:remaining] + "\n... (output truncated at max)"
        lines.append(content)
        total_len += len(content)

    # Find the last step-finish and its preceding step-start
    last_step_start = 0
    last_finish = len(parts)
    for i in range(len(parts) - 1, -1, -1):
        if parts[i].get("type") == "step-finish":
            last_finish = i
            break
    for i in range(last_finish - 1, -1, -1):
        if parts[i].get("type") == "step-start":
            last_step_start = i
            break

    # Find tool parts from the last N steps
    boundaries = _find_step_boundaries(parts)
    if boundaries:
        # Take at most MAX_TOOL_STEPS from the end
        recent_boundaries = boundaries[-MAX_TOOL_STEPS:]
    else:
        recent_boundaries = [(0, len(parts))]

    for start, end in recent_boundaries:
        for part in parts[start : end + 1]:
            if part.get("type") != "tool":
                continue
            tool_name = part.get("tool", "unknown")
            state = part.get("state")
            if not isinstance(state, dict):
                continue
            tool_input = state.get("input", {})
            tool_output = str(state.get("output", "") or "")
            status = state.get("status", "unknown")

            append(f"Tool: {tool_name} (status: {status})")
            if tool_input:
                input_str = json.dumps(tool_input)
                if len(input_str) > MAX_TOOL_OUTPUT_CHARS:
                    input_str = input_str[:MAX_TOOL_OUTPUT_CHARS] + "... (truncated)"
                append(f"  Input: {input_str}")
            if tool_output:
                if len(tool_output) > MAX_TOOL_OUTPUT_CHARS:
                    tool_output = (
                        tool_output[:MAX_TOOL_OUTPUT_CHARS] + "\n... (truncated)"
                    )
                append(f"  Output:\n{tool_output}")
            append("")

    # Reasoning from the last step only (most relevant)
    for part in parts[last_step_start : last_finish + 1]:
        if part.get("type") == "reasoning":
            reasoning_text = _safe_text(part)
            if reasoning_text.strip():
                append("Reasoning:")
                append(reasoning_text)
                append("")

    # Text from the last step that isn't XML noise
    text_parts: list[str] = []
    for part in parts[last_step_start : last_finish + 1]:
        if part.get("type") == "text":
            text = _safe_text(part)
            if _is_relevant_text(text):
                text_parts.append(text)
    if text_parts:
        append("Text:")
        append(" ".join(text_parts))
        append("")

    result = "\n".join(lines).strip()
    if not result:
        result = "(no extractable content found in subagent session parts)"

    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract subagent output from OpenCode session database"
    )
    parser.add_argument(
        "--session-id",
        required=True,
        help="Subagent session ID from the task tool output (starts with ses_)",
    )
    parser.add_argument(
        "--db-path",
        default=None,
        help="Path to opencode.db (default: auto-detect)",
    )
    args = parser.parse_args()

    try:
        db_path = Path(args.db_path) if args.db_path else resolve_db_path()
    except (FileNotFoundError, RepairError) as e:
        print(str(e), file=sys.stderr)
        return 1

    try:
        parts = get_parts(db_path, args.session_id)
    except sqlite3.Error as e:
        print(
            f"Database error reading session {args.session_id}: {e}", file=sys.stderr
        )
        return 1

    if not parts:
        print(
            f"No parts found for session {args.session_id}. "
            "Check that the session ID is correct and the database is the right one.",
            file=sys.stderr,
        )
        return 1

    message_parts = skip_preamble(parts)
    output = format_parts(message_parts)
    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
