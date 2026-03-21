from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import time

from common import (
    TranscriptError,
    TranscriptTurn,
    iter_jsonl_records,
    python_search,
    rg_search,
)


DEFAULT_ROOT = Path.home() / ".kimi"
KIMI_SHARE_DIR_ENV = "KIMI_SHARE_DIR"


def _resolve_share_root(search_root: Path | None) -> Path:
    if search_root is not None:
        root = search_root
    elif os.environ.get(KIMI_SHARE_DIR_ENV):
        root = Path(os.environ[KIMI_SHARE_DIR_ENV])
    else:
        root = DEFAULT_ROOT
    return root.expanduser().resolve()


def _load_metadata(share_root: Path) -> dict:
    metadata_path = share_root / "kimi.json"
    if not metadata_path.exists():
        raise TranscriptError(f"Kimi metadata file does not exist: {metadata_path}")
    try:
        return json.loads(metadata_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise TranscriptError(f"Failed to read Kimi metadata file {metadata_path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise TranscriptError(f"Failed to parse Kimi metadata file {metadata_path}: {exc}") from exc


def _sessions_root(share_root: Path) -> Path:
    root = share_root / "sessions"
    if not root.exists():
        raise TranscriptError(f"Kimi sessions root does not exist: {root}")
    return root


def _workdir_entry(metadata: dict, workdir: Path) -> dict | None:
    for entry in metadata.get("work_dirs", []):
        if not isinstance(entry, dict):
            continue
        if entry.get("path") == str(workdir):
            return entry
    return None


def _candidate_session_dir(share_root: Path, workdir: Path, session_id: str) -> Path:
    import hashlib

    workdir_hash = hashlib.md5(str(workdir).encode("utf-8")).hexdigest()
    return _sessions_root(share_root) / workdir_hash / session_id


def _top_level_transcript_candidates(session_dir: Path, session_id: str) -> list[Path]:
    candidates: list[Path] = []
    for path in session_dir.iterdir():
        if not path.is_file():
            continue
        if path.suffix != ".jsonl":
            continue
        if path.name.startswith("context_sub_"):
            continue
        if path.name == "context.jsonl":
            candidates.append(path)
            continue
        if path.name.startswith("context_"):
            candidates.append(path)
            continue
        if path.name == f"{session_id}.jsonl":
            candidates.append(path)
    return candidates


def _select_direct_transcript_path(session_dir: Path, session_id: str) -> Path | None:
    context_path = session_dir / "context.jsonl"
    if context_path.exists():
        return context_path

    top_level_contexts = [
        path
        for path in _top_level_transcript_candidates(session_dir, session_id)
        if path.name == "context.jsonl" or path.name.startswith("context_")
    ]
    if top_level_contexts:
        return sorted(
            top_level_contexts,
            key=lambda path: (path.stat().st_mtime_ns, str(path)),
            reverse=True,
        )[0]

    legacy_path = session_dir / f"{session_id}.jsonl"
    if legacy_path.exists():
        return legacy_path
    return None


def find_current_transcript(search_root: Path | None = None) -> Path | None:
    share_root = _resolve_share_root(search_root)
    workdir = Path.cwd().resolve()
    try:
        metadata = _load_metadata(share_root)
        entry = _workdir_entry(metadata, workdir)
        if entry is None:
            return None

        session_id = entry.get("last_session_id")
        if not session_id:
            return None

        session_dir = _candidate_session_dir(share_root, workdir, str(session_id))
    except TranscriptError:
        return None

    if not session_dir.exists():
        return None
    return _select_direct_transcript_path(session_dir, str(session_id))


def _is_top_level_transcript_match(path: Path, *, sessions_root: Path) -> bool:
    try:
        relative_path = path.resolve().relative_to(sessions_root.resolve())
    except ValueError:
        return False

    if len(relative_path.parts) != 3:
        return False

    session_id = relative_path.parts[1]
    filename = relative_path.name
    if filename == "context.jsonl":
        return True
    if filename.startswith("context_"):
        return True
    return filename == f"{session_id}.jsonl"


def find_matching_transcripts(
    *,
    canary: str,
    timeout_ms: int,
    poll_ms: int,
    search_root: Path | None = None,
) -> list[Path]:
    share_root = _resolve_share_root(search_root)
    sessions_root = _sessions_root(share_root)
    deadline = time.monotonic() + (timeout_ms / 1000)
    use_rg = shutil.which("rg") is not None

    while True:
        if use_rg:
            matches = rg_search(
                sessions_root,
                canary=canary,
                exclude_globs=["**/wire.jsonl", "**/context_sub_*.jsonl"],
            )
        else:
            matches = python_search(
                sessions_root,
                canary=canary,
                exclude_paths=lambda path: not _is_top_level_transcript_match(
                    path,
                    sessions_root=sessions_root,
                ),
            )

        matches = [
            path
            for path in matches
            if _is_top_level_transcript_match(path, sessions_root=sessions_root)
        ]

        if matches:
            return matches

        if time.monotonic() >= deadline:
            break
        time.sleep(poll_ms / 1000)

    raise TranscriptError(
        f"No Kimi transcript file under {sessions_root} contained canary {canary!r} within {timeout_ms}ms."
    )


def _visible_user_text(record: dict) -> str:
    content = record.get("content")
    if content is None:
        content = record.get("message", {}).get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    return "".join(
        block.get("text", "")
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    )


def _visible_assistant_text(record: dict) -> str:
    content = record.get("content")
    if content is None:
        content = record.get("message", {}).get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    return "".join(
        block.get("text", "")
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    )


def extract_transcript(path: Path) -> list[TranscriptTurn]:
    selected_turns: list[TranscriptTurn] = []
    pending_assistant: TranscriptTurn | None = None
    saw_user = False

    for line_number, record in iter_jsonl_records(path):
        role = record.get("role") or record.get("type")

        if role == "user":
            user_text = _visible_user_text(record)
            if not user_text:
                continue
            if saw_user and pending_assistant is not None:
                selected_turns.append(pending_assistant)
                pending_assistant = None
            selected_turns.append(
                TranscriptTurn(order=line_number, role="user", text=user_text)
            )
            saw_user = True
            continue

        if role != "assistant":
            continue

        visible_reply = _visible_assistant_text(record)
        if visible_reply:
            pending_assistant = TranscriptTurn(
                order=line_number,
                role="assistant",
                text=visible_reply,
            )

    if pending_assistant is not None:
        selected_turns.append(pending_assistant)

    return selected_turns
