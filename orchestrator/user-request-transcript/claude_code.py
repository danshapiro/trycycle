from __future__ import annotations

from pathlib import Path

from common import TranscriptError, TranscriptTurn, iter_jsonl_records, wait_for_matches


DEFAULT_ROOT = Path.home() / ".claude" / "projects"


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
