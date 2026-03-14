from __future__ import annotations

import os
from pathlib import Path
import shutil
import time

from common import (
    TranscriptError,
    TranscriptTurn,
    choose_most_recent_match,
    iter_jsonl_records,
    python_search,
    rg_search,
)


DEFAULT_ROOT = Path.home() / ".codex" / "sessions"
CODEX_HOME_ENV = "CODEX_HOME"
THREAD_ID_ENV = "CODEX_THREAD_ID"


def _candidate_roots(search_root: Path | None) -> list[Path]:
    if search_root is not None:
        return [search_root]

    candidates: list[Path] = []

    codex_home = os.environ.get(CODEX_HOME_ENV)
    if codex_home:
        candidates.append(Path(codex_home) / "sessions")

    candidates.append(DEFAULT_ROOT)

    # Desktop sessions launched from Windows can write native Codex rollouts to
    # the Windows user's CODEX_HOME, while agent commands run inside WSL and see
    # a different HOME. Search the mounted Windows homes too so canary lookup
    # can find the live desktop transcript.
    candidates.extend(sorted(Path("/mnt").glob("*/Users/*/.codex/sessions")))

    deduped: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        normalized = candidate.expanduser()
        if normalized in seen:
            continue
        deduped.append(normalized)
        seen.add(normalized)
    return deduped


def _existing_roots(search_root: Path | None) -> list[Path]:
    roots = [root for root in _candidate_roots(search_root) if root.exists()]
    if roots:
        return roots

    searched = ", ".join(str(root) for root in _candidate_roots(search_root))
    raise TranscriptError(f"Codex CLI transcript roots do not exist: {searched}")


def find_current_transcript(search_root: Path | None = None) -> Path | None:
    roots = _existing_roots(search_root)

    thread_id = os.environ.get(THREAD_ID_ENV)
    if not thread_id:
        return None

    # Codex exposes the active thread id, so we can read the live session file
    # directly instead of racing transcript flushes for a printed canary.
    matches: list[Path] = []
    for root in roots:
        matches.extend(sorted(root.rglob(f"*{thread_id}.jsonl")))

    if not matches:
        return None
    return choose_most_recent_match(matches)


def find_matching_transcripts(
    *,
    canary: str,
    timeout_ms: int,
    poll_ms: int,
    search_root: Path | None = None,
) -> list[Path]:
    roots = _existing_roots(search_root)
    deadline = time.monotonic() + (timeout_ms / 1000)
    use_rg = shutil.which("rg") is not None

    while True:
        matches: list[Path] = []
        for root in roots:
            if use_rg:
                matches.extend(rg_search(root, canary=canary))
            else:
                matches.extend(python_search(root, canary=canary))

        if matches:
            return matches

        if time.monotonic() >= deadline:
            break
        time.sleep(poll_ms / 1000)

    searched = ", ".join(str(root) for root in roots)
    raise TranscriptError(
        f"No transcript file under [{searched}] contained canary {canary!r} within {timeout_ms}ms."
    )


def extract_transcript(path: Path) -> list[TranscriptTurn]:
    selected_turns: list[TranscriptTurn] = []
    pending_assistant: TranscriptTurn | None = None
    saw_user = False

    for line_number, record in iter_jsonl_records(path):
        record_type = record.get("type")
        payload = record.get("payload", {})

        if record_type == "event_msg" and payload.get("type") == "user_message":
            if saw_user and pending_assistant is not None:
                selected_turns.append(pending_assistant)
                pending_assistant = None

            user_message = payload.get("message")
            if isinstance(user_message, str):
                selected_turns.append(
                    TranscriptTurn(
                        order=line_number,
                        role="user",
                        text=user_message,
                    )
                )
                saw_user = True
            continue

        if record_type != "response_item":
            continue
        if payload.get("type") != "message" or payload.get("role") != "assistant":
            continue

        content_blocks = payload.get("content", [])
        if not isinstance(content_blocks, list):
            continue

        # Use the last non-empty visible assistant reply in each interval,
        # regardless of whether Codex labeled it commentary or final_answer.
        # Real sessions can end an interval with commentary plus an empty
        # final_answer placeholder, and the user still saw the commentary.
        visible_reply = "".join(
            block.get("text", "")
            for block in content_blocks
            if block.get("type") == "output_text"
        )
        if visible_reply:
            pending_assistant = TranscriptTurn(
                order=line_number,
                role="assistant",
                text=visible_reply,
            )

    return selected_turns
