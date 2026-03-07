from __future__ import annotations

from collections import deque
import json
import os
from pathlib import Path

from common import TranscriptError, TranscriptTurn, iter_jsonl_records, wait_for_matches


DEFAULT_ROOT = Path.home() / ".claude" / "projects"
HISTORY_PATH = Path.home() / ".claude" / "history.jsonl"
RECENT_SESSION_WINDOW_MS = 6 * 60 * 60 * 1000
MAX_PROJECT_HISTORY_ENTRIES = 256


def current_project_candidates() -> set[str]:
    candidates: set[str] = set()
    for raw_path in (os.environ.get("PWD"), os.getcwd(), str(Path.cwd()), str(Path.cwd().resolve())):
        if raw_path:
            candidates.add(raw_path)
    return candidates


def load_recent_project_history_session_ids(history_path: Path = HISTORY_PATH) -> list[tuple[int, str]]:
    if not history_path.exists():
        return []

    project_candidates = current_project_candidates()
    matching_entries: deque[tuple[int, str]] = deque(maxlen=MAX_PROJECT_HISTORY_ENTRIES)

    try:
        with history_path.open(encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                payload = json.loads(stripped)
                if payload.get("project") not in project_candidates:
                    continue

                session_id = payload.get("sessionId")
                timestamp_ms = payload.get("timestamp")
                if not isinstance(session_id, str):
                    raise TranscriptError(
                        f"Expected string sessionId in Claude Code history file {history_path}."
                    )
                if not isinstance(timestamp_ms, int):
                    raise TranscriptError(
                        f"Expected integer timestamp in Claude Code history file {history_path}."
                    )
                matching_entries.append((timestamp_ms, session_id))
    except OSError as exc:
        raise TranscriptError(f"Failed to read Claude Code history file {history_path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise TranscriptError(
            f"Failed to parse JSON in Claude Code history file {history_path}: {exc}"
        ) from exc

    return list(matching_entries)


def load_latest_history_session_id(history_path: Path = HISTORY_PATH) -> str | None:
    matching_entries = load_recent_project_history_session_ids(history_path=history_path)
    if not matching_entries:
        return None

    latest_timestamp_ms, latest_session_id = matching_entries[-1]
    recent_session_ids = {
        session_id
        for timestamp_ms, session_id in matching_entries
        if timestamp_ms >= latest_timestamp_ms - RECENT_SESSION_WINDOW_MS
    }

    # Claude's history file is global, so direct lookup is only safe when a
    # single same-project session has recent activity. Otherwise fall back to
    # the explicit canary flow instead of silently picking the wrong session.
    if len(recent_session_ids) != 1:
        return None
    return latest_session_id


def find_current_transcript(search_root: Path | None = None) -> Path | None:
    root = search_root or DEFAULT_ROOT
    if not root.exists():
        raise TranscriptError(f"Claude Code transcript root does not exist: {root}")

    session_id = load_latest_history_session_id()
    if not session_id:
        return None

    # Claude's global history file records the session id for each submitted
    # user message, so we can resolve the live top-level transcript directly.
    matches = sorted(
        path for path in root.rglob(f"{session_id}.jsonl") if "subagents" not in path.parts
    )
    if not matches:
        return None
    if len(matches) > 1:
        raise TranscriptError(
            f"Expected one Claude Code transcript for sessionId={session_id}, found {len(matches)}."
        )
    return matches[0]


def find_matching_transcripts(
    *,
    canary: str,
    timeout_ms: int,
    poll_ms: int,
    search_root: Path | None = None,
) -> list[Path]:
    root = search_root or DEFAULT_ROOT
    if not root.exists():
        raise TranscriptError(f"Claude Code transcript root does not exist: {root}")

    return wait_for_matches(
        root=root,
        canary=canary,
        timeout_ms=timeout_ms,
        poll_ms=poll_ms,
        exclude_globs=["**/subagents/**"],
        exclude_paths=lambda path: "subagents" in path.parts,
    )


def extract_transcript(path: Path) -> list[TranscriptTurn]:
    selected_turns: list[TranscriptTurn] = []
    pending_assistant: TranscriptTurn | None = None
    saw_user = False

    for line_number, record in iter_jsonl_records(path):
        record_type = record.get("type")

        if record_type == "user":
            message = record.get("message", {})
            content = message.get("content")
            if isinstance(content, str):
                if saw_user and pending_assistant is not None:
                    selected_turns.append(pending_assistant)
                    pending_assistant = None
                selected_turns.append(
                    TranscriptTurn(order=line_number, role="user", text=content)
                )
                saw_user = True
            continue

        if record_type != "assistant":
            continue

        message = record.get("message", {})
        content_blocks = message.get("content", [])
        if not isinstance(content_blocks, list):
            continue

        visible_reply = "".join(
            block.get("text", "")
            for block in content_blocks
            if block.get("type") == "text"
        )
        if visible_reply:
            pending_assistant = TranscriptTurn(
                order=line_number,
                role="assistant",
                text=visible_reply,
            )

    return selected_turns
