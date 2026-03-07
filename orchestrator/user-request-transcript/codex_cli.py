from __future__ import annotations

from pathlib import Path

from common import TranscriptError, TranscriptTurn, iter_jsonl_records, wait_for_matches


DEFAULT_ROOT = Path.home() / ".codex" / "sessions"


def find_matching_transcripts(
    *,
    canary: str,
    timeout_ms: int,
    poll_ms: int,
    search_root: Path | None = None,
) -> list[Path]:
    root = search_root or DEFAULT_ROOT
    if not root.exists():
        raise TranscriptError(f"Codex CLI transcript root does not exist: {root}")

    return wait_for_matches(
        root=root,
        canary=canary,
        timeout_ms=timeout_ms,
        poll_ms=poll_ms,
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
