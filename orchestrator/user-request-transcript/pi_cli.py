from __future__ import annotations

from pathlib import Path

from common import TranscriptTurn, iter_jsonl_records, wait_for_matches


DEFAULT_PI_SESSIONS_ROOT = Path.home() / ".pi" / "agent" / "sessions"


def _encode_cwd(cwd: str) -> str:
    """Encode a cwd path into a Pi session directory name.

    Pi encodes: strip leading '/', replace '/' with '-', replace ':' with '-',
    wrap in '--'.
    """
    encoded = cwd.lstrip("/")
    encoded = encoded.replace("/", "-")
    encoded = encoded.replace(":", "-")
    return f"--{encoded}--"


def _resolve_sessions_root(search_root: Path | None = None) -> Path:
    if search_root is not None:
        return search_root
    return DEFAULT_PI_SESSIONS_ROOT


def find_matching_transcripts(
    *,
    canary: str,
    timeout_ms: int,
    poll_ms: int,
    search_root: Path | None = None,
) -> list[Path]:
    root = _resolve_sessions_root(search_root)
    if not root.exists():
        from common import TranscriptError

        raise TranscriptError(f"Pi sessions root does not exist: {root}")

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

        if record_type != "message":
            continue

        message = record.get("message", {})
        role = message.get("role")
        content_blocks = message.get("content", [])

        if not isinstance(content_blocks, list):
            continue

        if role == "user":
            user_text = "".join(
                block.get("text", "")
                for block in content_blocks
                if isinstance(block, dict) and block.get("type") == "text"
            )
            if user_text:
                if saw_user and pending_assistant is not None:
                    selected_turns.append(pending_assistant)
                    pending_assistant = None
                selected_turns.append(
                    TranscriptTurn(order=line_number, role="user", text=user_text)
                )
                saw_user = True
            continue

        if role == "assistant":
            # Only include visible text, exclude thinking and toolCall
            visible_reply = "".join(
                block.get("text", "")
                for block in content_blocks
                if isinstance(block, dict) and block.get("type") == "text"
            )
            if visible_reply:
                pending_assistant = TranscriptTurn(
                    order=line_number,
                    role="assistant",
                    text=visible_reply,
                )

    if pending_assistant is not None:
        selected_turns.append(pending_assistant)

    return selected_turns
