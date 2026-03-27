#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from typing import Any
import uuid


DEFAULT_TIMEOUT_SECONDS = 60 * 60
EXECUTING_TIMEOUT_SECONDS = 3 * 60 * 60
CODEX_HOME_ENV = "CODEX_HOME"
DEFAULT_CODEX_SESSIONS_ROOT = Path.home() / ".codex" / "sessions"
KIMI_SHARE_DIR_ENV = "KIMI_SHARE_DIR"
DEFAULT_KIMI_SHARE_ROOT = Path.home() / ".kimi"
CODEX_PROFILE_ENV = "TRYCYCLE_CODEX_PROFILE"
MODEL_OVERRIDE_ENV_BY_BACKEND = {
    "codex": "TRYCYCLE_CODEX_MODEL",
    "claude": "TRYCYCLE_CLAUDE_MODEL",
    "kimi": "TRYCYCLE_KIMI_MODEL",
    "opencode": "TRYCYCLE_OPENCODE_MODEL",
}


def _binary_name_candidates(binary: str) -> list[str]:
    candidates = [binary]
    if os.name == "nt":
        for suffix in (".exe", ".cmd", ".bat"):
            if not binary.lower().endswith(suffix):
                candidates.append(f"{binary}{suffix}")
    return candidates


def _search_paths() -> list[str]:
    path_entries = os.environ.get("PATH", "").split(os.pathsep) if os.environ.get("PATH") else []
    extra_entries = [
        str(Path.home() / "bin"),
        str(Path.home() / ".local" / "bin"),
    ]
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        localappdata = os.environ.get("LOCALAPPDATA")
        if appdata:
            extra_entries.append(str(Path(appdata) / "npm"))
        if localappdata:
            extra_entries.append(str(Path(localappdata) / "Programs"))

    seen: set[str] = set()
    ordered: list[str] = []
    for entry in [*path_entries, *extra_entries]:
        if not entry or entry in seen:
            continue
        seen.add(entry)
        ordered.append(entry)
    return ordered


def _resolve_binary(binary: str) -> str | None:
    for candidate in _binary_name_candidates(binary):
        resolved = shutil.which(candidate, path=os.pathsep.join(_search_paths()))
        if resolved is not None:
            return resolved
    return None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_nonempty_env(name: str) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _default_timeout_seconds_for_phase(phase: str) -> int:
    if phase == "executing":
        return EXECUTING_TIMEOUT_SECONDS
    return DEFAULT_TIMEOUT_SECONDS


def _resolve_timeout_seconds(phase: str, explicit_timeout_seconds: int | None) -> int:
    if explicit_timeout_seconds is not None:
        return explicit_timeout_seconds
    return _default_timeout_seconds_for_phase(phase)


def _append_event(path: Path, *, severity: str, event: str, **fields: Any) -> None:
    record = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "severity": severity,
        "event": event,
    }
    record.update(fields)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def _run_probe(argv: list[str]) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            argv,
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)

    combined = "\n".join(part for part in (result.stdout, result.stderr) if part)
    if result.returncode != 0:
        return False, combined.strip() or f"exit code {result.returncode}"
    return True, combined


def _probe_codex(binary: str) -> dict[str, Any]:
    path = _resolve_binary(binary)
    if path is None:
        return {
            "available": False,
            "binary": binary,
            "reason": "binary not found on PATH",
        }

    ok, output = _run_probe([path, "exec", "--help"])
    if not ok:
        return {
            "available": False,
            "binary": path,
            "reason": output,
        }

    required_tokens = ["--output-last-message", "Run Codex non-interactively", "resume"]
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


def _probe_claude(binary: str) -> dict[str, Any]:
    path = _resolve_binary(binary)
    if path is None:
        return {
            "available": False,
            "binary": binary,
            "reason": "binary not found on PATH",
        }

    ok, output = _run_probe([path, "--help"])
    if not ok:
        return {
            "available": False,
            "binary": path,
            "reason": output,
        }

    required_tokens = ["-p, --print", "--output-format", "--resume", "--session-id"]
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


def _probe_kimi(binary: str) -> dict[str, Any]:
    path = _resolve_binary(binary)
    if path is None:
        return {
            "available": False,
            "binary": binary,
            "reason": "binary not found on PATH",
        }

    ok, output = _run_probe([path, "--help"])
    if not ok:
        return {
            "available": False,
            "binary": path,
            "reason": output,
        }

    required_tokens = ["--print", "--session", "--continue", "--work-dir", "final assistant"]
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


def _detect_host_backend() -> str | None:
    if os.environ.get("CODEX_THREAD_ID") or os.environ.get("CODEX_HOME"):
        return "codex"
    if os.environ.get("CLAUDECODE"):
        return "claude"
    if os.environ.get("OPENCODE"):
        return "opencode"
    return None


def _detect_backend_preferences() -> list[str]:
    host_backend = _detect_host_backend()
    if host_backend == "codex":
        return ["codex", "claude", "kimi", "opencode"]
    if host_backend == "claude":
        return ["claude", "codex", "kimi", "opencode"]
    if host_backend == "opencode":
        return ["opencode", "codex", "claude", "kimi"]
    return ["codex", "claude", "kimi", "opencode"]


def _probe_backends() -> dict[str, Any]:
    backends = {
        "codex": _probe_codex("codex"),
        "claude": _probe_claude("claude"),
        "kimi": _probe_kimi("kimi"),
        "opencode": _probe_opencode("opencode"),
    }

    preferred_order = _detect_backend_preferences()
    selected_backend = None
    for name in preferred_order:
        if backends[name]["available"]:
            selected_backend = name
            break

    return {
        "host_backend": _detect_host_backend(),
        "selected_backend": selected_backend,
        "backend_order": preferred_order,
        "backends": backends,
    }


def _resolve_backend_selection(
    requested_backend: str,
    *,
    probe: dict[str, Any],
) -> tuple[str | None, str | None]:
    if requested_backend == "auto":
        return probe["selected_backend"], None
    if requested_backend == "host":
        host_backend = probe["host_backend"]
        if host_backend is None:
            return None, "Could not detect the host backend. Pass --backend explicitly."
        return host_backend, None
    return requested_backend, None


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _candidate_codex_session_roots() -> list[Path]:
    candidates: list[Path] = []
    codex_home = os.environ.get(CODEX_HOME_ENV)
    if codex_home:
        candidates.append(Path(codex_home) / "sessions")
    candidates.append(DEFAULT_CODEX_SESSIONS_ROOT)
    candidates.extend(sorted(Path("/mnt").glob("*/Users/*/.codex/sessions")))

    deduped: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        deduped.append(candidate)
    return deduped


def _extract_codex_session_id(path: Path) -> str | None:
    match = re.search(r"([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})", path.stem)
    if match:
        return match.group(1)
    return None


def _codex_session_matches(path: Path, *, prompt_text: str, workdir: Path) -> bool:
    normalized_prompt = prompt_text.rstrip("\n")
    saw_matching_cwd = False

    try:
        with path.open(encoding="utf-8") as handle:
            for raw_line in handle:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    record = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue

                payload = record.get("payload", {})
                if (
                    record.get("type") == "session_meta"
                    and payload.get("cwd") == str(workdir)
                ):
                    saw_matching_cwd = True
                    continue

                if not saw_matching_cwd:
                    continue

                message = None
                if record.get("type") == "event_msg" and payload.get("type") == "user_message":
                    message = payload.get("message")
                elif (
                    record.get("type") == "response_item"
                    and payload.get("type") == "message"
                    and payload.get("role") == "user"
                ):
                    for block in payload.get("content", []):
                        if block.get("type") == "input_text":
                            message = block.get("text")
                            break

                if message is None:
                    continue
                if str(message).rstrip("\n") == normalized_prompt:
                    return True
    except OSError:
        return False
    return False


def _find_codex_session_id(*, prompt_text: str, workdir: Path, started_at: float) -> str | None:
    candidates: list[tuple[float, Path]] = []
    for root in _candidate_codex_session_roots():
        if not root.exists():
            continue
        for path in root.rglob("*.jsonl"):
            try:
                stat = path.stat()
            except OSError:
                continue
            if stat.st_mtime + 5 < started_at:
                continue
            candidates.append((stat.st_mtime, path))

    for _, path in sorted(candidates, key=lambda item: item[0], reverse=True):
        if _codex_session_matches(path, prompt_text=prompt_text, workdir=workdir):
            return _extract_codex_session_id(path)
    return None


def _normalize_status(reply_text: str, exit_code: int) -> str:
    if exit_code != 0:
        return "escalate_to_user"
    if not reply_text.strip():
        return "escalate_to_user"
    if reply_text.lstrip().startswith("USER DECISION REQUIRED:"):
        return "user_decision_required"
    return "ok"


def _resolve_kimi_share_root() -> Path:
    configured = os.environ.get(KIMI_SHARE_DIR_ENV)
    if configured:
        return Path(configured).expanduser().resolve()
    return DEFAULT_KIMI_SHARE_ROOT.expanduser().resolve()


def _kimi_workdir_sessions_root(*, workdir: Path) -> Path:
    workdir_hash = hashlib.md5(str(workdir.resolve()).encode("utf-8")).hexdigest()
    return _resolve_kimi_share_root() / "sessions" / workdir_hash


def _kimi_session_dir(*, workdir: Path, session_id: str) -> Path:
    return _kimi_workdir_sessions_root(workdir=workdir) / session_id


def _kimi_legacy_session_path(*, workdir: Path, session_id: str) -> Path:
    return _kimi_workdir_sessions_root(workdir=workdir) / f"{session_id}.jsonl"


def _kimi_top_level_context_candidates(session_dir: Path, session_id: str) -> list[Path]:
    candidates: list[Path] = []
    try:
        entries = list(session_dir.iterdir())
    except OSError:
        return []

    for path in entries:
        if not path.is_file():
            continue
        if path.suffix != ".jsonl":
            continue
        if path.name == "wire.jsonl":
            continue
        if path.name.startswith("context_sub_"):
            continue
        if path.name == "context.jsonl" or path.name.startswith("context_"):
            candidates.append(path)
            continue
        if path.name == f"{session_id}.jsonl":
            candidates.append(path)
    return candidates


def _find_kimi_context_path(*, workdir: Path, session_id: str) -> Path | None:
    session_dir = _kimi_session_dir(workdir=workdir, session_id=session_id)
    context_path = session_dir / "context.jsonl"
    if context_path.exists():
        return context_path

    top_level_contexts = [
        path
        for path in _kimi_top_level_context_candidates(session_dir, session_id)
        if path.name == "context.jsonl" or path.name.startswith("context_")
    ]
    if top_level_contexts:
        return sorted(
            top_level_contexts,
            key=lambda path: (path.stat().st_mtime_ns, str(path)),
            reverse=True,
        )[0]

    legacy_path = _kimi_legacy_session_path(workdir=workdir, session_id=session_id)
    if legacy_path.exists():
        return legacy_path

    nested_legacy_path = session_dir / f"{session_id}.jsonl"
    if nested_legacy_path.exists():
        return nested_legacy_path
    return None


def _snapshot_kimi_line_counts(*, workdir: Path, session_id: str) -> dict[str, int]:
    session_dir = _kimi_session_dir(workdir=workdir, session_id=session_id)
    counts: dict[str, int] = {}
    for path in _kimi_top_level_context_candidates(session_dir, session_id):
        try:
            counts[str(path.resolve())] = len(path.read_text(encoding="utf-8").splitlines())
        except OSError:
            continue
    legacy_path = _kimi_legacy_session_path(workdir=workdir, session_id=session_id)
    if legacy_path.exists():
        try:
            counts[str(legacy_path.resolve())] = len(
                legacy_path.read_text(encoding="utf-8").splitlines()
            )
        except OSError:
            pass
    return counts


def _kimi_visible_text(record: dict) -> str:
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


def _extract_kimi_final_visible_assistant_text(
    path: Path,
    *,
    baseline_line_count: int = 0,
) -> str | None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None

    final_text: str | None = None
    for raw_line in lines[baseline_line_count:]:
        if not raw_line.strip():
            continue
        try:
            record = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        role = record.get("role") or record.get("type")
        if role != "assistant":
            continue
        visible_text = _kimi_visible_text(record)
        if visible_text:
            final_text = visible_text
    return final_text


def _normalize_kimi_reply_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if normalized.endswith("\n"):
        normalized = normalized[:-1]
    return normalized


def _kimi_reply_matches_session(
    *,
    reply_text: str,
    workdir: Path,
    session_id: str | None,
    baseline_line_counts: dict[str, int] | None,
) -> bool:
    if not session_id:
        return False
    if not reply_text.strip():
        return False

    context_path = _find_kimi_context_path(workdir=workdir, session_id=session_id)
    if context_path is None:
        return False

    baseline_line_count = 0
    if baseline_line_counts is not None:
        baseline_line_count = baseline_line_counts.get(str(context_path.resolve()), 0)

    persisted_reply = _extract_kimi_final_visible_assistant_text(
        path=context_path,
        baseline_line_count=baseline_line_count,
    )
    if persisted_reply is None:
        return False
    return _normalize_kimi_reply_text(reply_text) == _normalize_kimi_reply_text(
        persisted_reply
    )


def _first_visible_reply_line(text: str) -> str | None:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    for line in normalized.split("\n"):
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def _classify_run_result(
    *,
    backend: str,
    run_result: dict[str, Any],
    timeout_seconds: int,
    success_message: str,
    workdir: Path,
) -> tuple[str, str]:
    if run_result["dry_run"]:
        return "ok", "Dry run completed."
    if run_result["timed_out"]:
        return "escalate_to_user", f"{backend} timed out after {timeout_seconds} seconds."

    if backend == "kimi":
        if run_result["exit_code"] != 0:
            status = _normalize_status(run_result["reply_text"], run_result["exit_code"])
        elif _kimi_reply_matches_session(
            reply_text=run_result["reply_text"],
            workdir=workdir,
            session_id=run_result["session_id"],
            baseline_line_counts=run_result.get("kimi_baseline_line_counts"),
        ):
            status = _normalize_status(run_result["reply_text"], run_result["exit_code"])
        else:
            first_line = _first_visible_reply_line(run_result["reply_text"])
            if first_line:
                return (
                    "escalate_to_user",
                    f"Kimi did not produce a valid persisted reply: {first_line}",
                )
            return "escalate_to_user", "Kimi did not produce a valid persisted reply."
    else:
        status = _normalize_status(run_result["reply_text"], run_result["exit_code"])

    if status == "ok":
        return status, success_message
    if status == "user_decision_required":
        return status, "Subagent requested a user decision."
    return status, f"{backend} exited with code {run_result['exit_code']}."


def _codex_command(
    *,
    binary: str,
    workdir: Path,
    reply_path: Path,
    effort: str | None,
    model: str | None,
    profile: str | None,
) -> list[str]:
    command = [
        binary,
        "-a",
        "never",
        "exec",
        "-C",
        str(workdir),
        "-s",
        "danger-full-access",
        "--color",
        "never",
        "-o",
        str(reply_path),
        "-",
    ]
    config_inserts: list[str] = []
    if profile:
        config_inserts.extend(["--profile", profile])
    if model:
        config_inserts.extend(["-m", model])
    if effort:
        config_inserts.extend(["-c", f"model_reasoning_effort={effort}"])
    if config_inserts:
        command[3:3] = config_inserts
    return command


def _codex_resume_command(
    *,
    binary: str,
    session_id: str,
    reply_path: Path,
    effort: str | None,
    model: str | None,
    profile: str | None,
) -> list[str]:
    command = [
        binary,
        "-a",
        "never",
        "exec",
        "resume",
        session_id,
        "-o",
        str(reply_path),
        "-",
    ]
    config_inserts: list[str] = []
    if profile:
        config_inserts.extend(["--profile", profile])
    if model:
        config_inserts.extend(["-m", model])
    if effort:
        config_inserts.extend(["-c", f"model_reasoning_effort={effort}"])
    if config_inserts:
        command[3:3] = config_inserts
    return command


def _resolve_model_override(backend: str, explicit_model: str | None) -> tuple[str | None, str | None]:
    if explicit_model:
        return explicit_model, "argument"
    env_name = MODEL_OVERRIDE_ENV_BY_BACKEND.get(backend)
    if env_name is None:
        return None, None
    env_value = _read_nonempty_env(env_name)
    if env_value:
        return env_value, f"env:{env_name}"
    return None, None


def _resolve_codex_profile(explicit_profile: str | None) -> tuple[str | None, str | None]:
    if explicit_profile:
        return explicit_profile, "argument"
    env_value = _read_nonempty_env(CODEX_PROFILE_ENV)
    if env_value:
        return env_value, f"env:{CODEX_PROFILE_ENV}"
    return None, None


def _claude_command(
    *,
    binary: str,
    effort: str | None,
    model: str | None,
) -> tuple[list[str], str]:
    session_id = str(uuid.uuid4())
    command = [
        binary,
        "-p",
        "--session-id",
        session_id,
        "--output-format",
        "text",
        "--dangerously-skip-permissions",
    ]
    if model:
        command.extend(["--model", model])
    if effort:
        command.extend(["--effort", effort])
    return command, session_id


def _claude_resume_command(
    *,
    binary: str,
    session_id: str,
    effort: str | None,
    model: str | None,
) -> list[str]:
    command = [
        binary,
        "-p",
        "--resume",
        session_id,
        "--output-format",
        "text",
        "--dangerously-skip-permissions",
    ]
    if model:
        command.extend(["--model", model])
    if effort:
        command.extend(["--effort", effort])
    return command


def _kimi_command(
    *,
    binary: str,
    workdir: Path,
    effort: str | None,
    model: str | None,
) -> tuple[list[str], str]:
    session_id = str(uuid.uuid4())
    command = [
        binary,
        "--print",
        "--final-message-only",
        "--work-dir",
        str(workdir),
        "--session",
        session_id,
    ]
    if model:
        command.extend(["--model", model])
    if effort == "low":
        command.append("--no-thinking")
    elif effort:
        command.append("--thinking")
    return command, session_id


def _kimi_resume_command(
    *,
    binary: str,
    session_id: str,
    workdir: Path,
    effort: str | None,
    model: str | None,
) -> list[str]:
    command = [
        binary,
        "--print",
        "--final-message-only",
        "--work-dir",
        str(workdir),
        "--session",
        session_id,
    ]
    if model:
        command.extend(["--model", model])
    if effort == "low":
        command.append("--no-thinking")
    elif effort:
        command.append("--thinking")
    return command


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


OPENCODE_DEFAULT_DB_PATH = Path.home() / ".local" / "share" / "opencode" / "opencode.db"


def _resolve_opencode_db_path() -> Path | None:
    """Locate the OpenCode SQLite database."""
    data_dir = os.environ.get("OPENCODE_DATA_DIR")
    if data_dir:
        db_path = Path(data_dir) / "opencode.db"
        if db_path.exists():
            return db_path
    if OPENCODE_DEFAULT_DB_PATH.exists():
        return OPENCODE_DEFAULT_DB_PATH
    return None


def _extract_opencode_reply_from_db(session_id: str, db_path: Path | None = None) -> str:
    """Tier 2 fallback: extract the last assistant text reply from the OpenCode SQLite DB.

    Used when the JSON event stream from stdout is incomplete (e.g., OpenCode
    does not flush all events before exiting).
    """
    if db_path is None:
        db_path = _resolve_opencode_db_path()
    if db_path is None or not db_path.exists():
        return ""
    try:
        conn = sqlite3.connect(str(db_path), timeout=5)
        conn.row_factory = sqlite3.Row
        try:
            # Find the last assistant message in this session
            rows = conn.execute(
                """
                SELECT p.data AS part_data
                FROM part p
                JOIN message m ON p.message_id = m.id
                WHERE p.session_id = ?
                  AND json_extract(m.data, '$.role') = 'assistant'
                  AND json_extract(p.data, '$.type') = 'text'
                ORDER BY m.time_created DESC, p.time_created DESC
                """,
                (session_id,),
            ).fetchall()
            if not rows:
                return ""
            # All rows from the last assistant message's text parts,
            # but we got them DESC; the first row is the latest part.
            # We need to find all parts from the same message.
            # Actually, let's get the last assistant message first.
            last_msg = conn.execute(
                """
                SELECT m.id
                FROM message m
                WHERE m.session_id = ?
                  AND json_extract(m.data, '$.role') = 'assistant'
                ORDER BY m.time_created DESC
                LIMIT 1
                """,
                (session_id,),
            ).fetchone()
            if not last_msg:
                return ""
            parts = conn.execute(
                """
                SELECT data
                FROM part
                WHERE message_id = ?
                  AND json_extract(data, '$.type') = 'text'
                ORDER BY time_created, id
                """,
                (last_msg["id"],),
            ).fetchall()
            text_parts = []
            for part_row in parts:
                part_data = json.loads(part_row["data"])
                text = part_data.get("text", "")
                if text.strip():
                    text_parts.append(text)
            return "".join(text_parts).strip()
        finally:
            conn.close()
    except (sqlite3.Error, json.JSONDecodeError):
        return ""


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


def _copy_if_needed(source: Path, target: Path) -> None:
    if source.resolve() == target.resolve():
        return
    target.write_text(_read_text(source), encoding="utf-8")


def _run_backend(
    *,
    backend: str,
    binary: str,
    prompt_text: str,
    workdir: Path,
    reply_path: Path,
    stdout_path: Path,
    stderr_path: Path,
    effort: str | None,
    model: str | None,
    profile: str | None,
    timeout_seconds: int,
    dry_run: bool,
    events_path: Path,
) -> dict[str, Any]:
    session_lookup_started_at = time.time()
    if backend == "codex":
        command = _codex_command(
            binary=binary,
            workdir=workdir,
            reply_path=reply_path,
            effort=effort,
            model=model,
            profile=profile,
        )
        cwd = workdir
        session_id = None
    elif backend == "claude":
        command, session_id = _claude_command(
            binary=binary,
            effort=effort,
            model=model,
        )
        cwd = workdir
    elif backend == "kimi":
        command, session_id = _kimi_command(
            binary=binary,
            workdir=workdir,
            effort=effort,
            model=model,
        )
        cwd = workdir
    elif backend == "opencode":
        command, session_id = _opencode_command(
            binary=binary,
            workdir=workdir,
            effort=effort,
            model=model,
        )
        cwd = workdir
    else:
        raise ValueError(f"unsupported backend: {backend}")

    kimi_baseline_line_counts = None
    if backend == "kimi" and session_id is not None:
        kimi_baseline_line_counts = _snapshot_kimi_line_counts(
            workdir=workdir,
            session_id=session_id,
        )

    if dry_run:
        _append_event(
            events_path,
            severity="INFO",
            event="dry_run",
            backend=backend,
            command=command,
        )
        return {
            "command": command,
            "exit_code": 0,
            "reply_text": "",
            "timed_out": False,
            "dry_run": True,
            "session_id": session_id,
            "kimi_baseline_line_counts": kimi_baseline_line_counts,
        }

    _append_event(
        events_path,
        severity="INFO",
        event="process_spawned",
        backend=backend,
        command=command,
    )

    child_env = os.environ.copy()
    child_env.pop("CLAUDE_CODE_ENTRYPOINT", None)

    process_started_at = time.monotonic()
    try:
        result = subprocess.run(
            command,
            input=prompt_text,
            text=True,
            capture_output=True,
            cwd=cwd,
            check=False,
            timeout=timeout_seconds,
            env=child_env,
        )
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        duration_seconds = round(time.monotonic() - process_started_at, 3)
        stdout_path.write_text(exc.stdout or "", encoding="utf-8")
        stderr_path.write_text(exc.stderr or "", encoding="utf-8")
        _append_event(
            events_path,
            severity="ERROR",
            event="process_timeout",
            backend=backend,
            timeout_seconds=timeout_seconds,
            duration_seconds=duration_seconds,
        )
        return {
            "command": command,
            "exit_code": None,
            "reply_text": "",
            "timed_out": True,
            "dry_run": False,
            "session_id": session_id,
            "kimi_baseline_line_counts": kimi_baseline_line_counts,
        }

    duration_seconds = round(time.monotonic() - process_started_at, 3)
    stdout_path.write_text(result.stdout or "", encoding="utf-8")
    stderr_path.write_text(result.stderr or "", encoding="utf-8")

    if backend == "opencode":
        reply_text = _extract_opencode_reply_from_json(result.stdout or "")
        if session_id is None:
            session_id = _extract_opencode_session_id_from_json(result.stdout or "")
        # Tier 2 fallback: if JSON stream was incomplete, read reply from SQLite DB
        if not reply_text.strip() and session_id and result.returncode == 0:
            reply_text = _extract_opencode_reply_from_db(session_id)
        reply_path.write_text(reply_text, encoding="utf-8")
    elif backend in {"claude", "kimi"}:
        reply_text = result.stdout or ""
        reply_path.write_text(reply_text, encoding="utf-8")
    else:
        reply_text = _read_text(reply_path) if reply_path.exists() else ""
        if not reply_text and result.stdout:
            reply_text = result.stdout
            reply_path.write_text(reply_text, encoding="utf-8")

    _append_event(
        events_path,
        severity="INFO",
        event="process_exit",
        backend=backend,
        exit_code=result.returncode,
        duration_seconds=duration_seconds,
    )

    if backend == "codex" and result.returncode == 0:
        session_id = _find_codex_session_id(
            prompt_text=prompt_text,
            workdir=workdir,
            started_at=session_lookup_started_at,
        )

    return {
        "command": command,
        "exit_code": result.returncode,
        "reply_text": reply_text,
        "timed_out": timed_out,
        "dry_run": False,
        "session_id": session_id,
        "kimi_baseline_line_counts": kimi_baseline_line_counts,
    }


def _resume_backend(
    *,
    backend: str,
    binary: str,
    session_id: str,
    prompt_text: str,
    workdir: Path,
    reply_path: Path,
    stdout_path: Path,
    stderr_path: Path,
    effort: str | None,
    model: str | None,
    profile: str | None,
    timeout_seconds: int,
    dry_run: bool,
    events_path: Path,
) -> dict[str, Any]:
    if backend == "codex":
        command = _codex_resume_command(
            binary=binary,
            session_id=session_id,
            reply_path=reply_path,
            effort=effort,
            model=model,
            profile=profile,
        )
        cwd = workdir
    elif backend == "claude":
        command = _claude_resume_command(
            binary=binary,
            session_id=session_id,
            effort=effort,
            model=model,
        )
        cwd = workdir
    elif backend == "kimi":
        command = _kimi_resume_command(
            binary=binary,
            session_id=session_id,
            workdir=workdir,
            effort=effort,
            model=model,
        )
        cwd = workdir
    elif backend == "opencode":
        command = _opencode_resume_command(
            binary=binary,
            session_id=session_id,
            workdir=workdir,
            effort=effort,
            model=model,
        )
        cwd = workdir
    else:
        raise ValueError(f"unsupported backend: {backend}")

    kimi_baseline_line_counts = None
    if backend == "kimi":
        kimi_baseline_line_counts = _snapshot_kimi_line_counts(
            workdir=workdir,
            session_id=session_id,
        )

    if dry_run:
        _append_event(
            events_path,
            severity="INFO",
            event="dry_run_resume",
            backend=backend,
            command=command,
            session_id=session_id,
        )
        return {
            "command": command,
            "exit_code": 0,
            "reply_text": "",
            "timed_out": False,
            "dry_run": True,
            "session_id": session_id,
            "kimi_baseline_line_counts": kimi_baseline_line_counts,
        }

    _append_event(
        events_path,
        severity="INFO",
        event="process_spawned",
        backend=backend,
        command=command,
        session_id=session_id,
    )

    child_env = os.environ.copy()
    child_env.pop("CLAUDE_CODE_ENTRYPOINT", None)

    started_at = time.monotonic()
    try:
        result = subprocess.run(
            command,
            input=prompt_text,
            text=True,
            capture_output=True,
            cwd=cwd,
            check=False,
            timeout=timeout_seconds,
            env=child_env,
        )
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        duration_seconds = round(time.monotonic() - started_at, 3)
        stdout_path.write_text(exc.stdout or "", encoding="utf-8")
        stderr_path.write_text(exc.stderr or "", encoding="utf-8")
        _append_event(
            events_path,
            severity="ERROR",
            event="process_timeout",
            backend=backend,
            timeout_seconds=timeout_seconds,
            duration_seconds=duration_seconds,
            session_id=session_id,
        )
        return {
            "command": command,
            "exit_code": None,
            "reply_text": "",
            "timed_out": True,
            "dry_run": False,
            "session_id": session_id,
            "kimi_baseline_line_counts": kimi_baseline_line_counts,
        }

    duration_seconds = round(time.monotonic() - started_at, 3)
    stdout_path.write_text(result.stdout or "", encoding="utf-8")
    stderr_path.write_text(result.stderr or "", encoding="utf-8")

    if backend == "opencode":
        reply_text = _extract_opencode_reply_from_json(result.stdout or "")
        # Tier 2 fallback: if JSON stream was incomplete, read reply from SQLite DB
        if not reply_text.strip() and session_id and result.returncode == 0:
            reply_text = _extract_opencode_reply_from_db(session_id)
        reply_path.write_text(reply_text, encoding="utf-8")
    elif backend in {"claude", "kimi"}:
        reply_text = result.stdout or ""
        reply_path.write_text(reply_text, encoding="utf-8")
    else:
        reply_text = _read_text(reply_path) if reply_path.exists() else ""
        if not reply_text and result.stdout:
            reply_text = result.stdout
            reply_path.write_text(reply_text, encoding="utf-8")

    _append_event(
        events_path,
        severity="INFO",
        event="process_exit",
        backend=backend,
        exit_code=result.returncode,
        duration_seconds=duration_seconds,
        session_id=session_id,
    )

    return {
        "command": command,
        "exit_code": result.returncode,
        "reply_text": reply_text,
        "timed_out": timed_out,
        "dry_run": False,
        "session_id": session_id,
        "kimi_baseline_line_counts": kimi_baseline_line_counts,
    }


def _command_probe(_: argparse.Namespace) -> int:
    payload = _probe_backends()
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


def _command_run(args: argparse.Namespace) -> int:
    prompt_file = Path(args.prompt_file).resolve()
    workdir = Path(args.workdir).resolve()
    artifacts_dir = (
        Path(args.artifacts_dir).resolve()
        if args.artifacts_dir
        else Path(tempfile.mkdtemp(prefix="trycycle-runner-")).resolve()
    )
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    events_path = artifacts_dir / "events.jsonl"
    result_path = artifacts_dir / "result.json"
    stdout_path = artifacts_dir / "stdout.txt"
    stderr_path = artifacts_dir / "stderr.txt"
    reply_path = artifacts_dir / "reply.txt"
    prompt_copy_path = artifacts_dir / "prompt.txt"

    _copy_if_needed(prompt_file, prompt_copy_path)
    prompt_text = _read_text(prompt_file)
    probe = _probe_backends()

    backend, backend_error = _resolve_backend_selection(args.backend, probe=probe)

    if backend is None:
        payload = {
            "status": "escalate_to_user",
            "phase": args.phase,
            "backend": None,
            "message": backend_error or "No supported backend is available.",
            "artifacts_dir": str(artifacts_dir),
            "result_path": str(result_path),
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
            "reply_path": str(reply_path),
            "probe": probe,
        }
        _write_json(result_path, payload)
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 1

    backend_info = probe["backends"][backend]
    if not backend_info["available"]:
        payload = {
            "status": "escalate_to_user",
            "phase": args.phase,
            "backend": backend,
            "message": backend_info["reason"],
            "artifacts_dir": str(artifacts_dir),
            "result_path": str(result_path),
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
            "reply_path": str(reply_path),
            "probe": probe,
        }
        _write_json(result_path, payload)
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 1

    if args.profile and backend != "codex":
        payload = {
            "status": "escalate_to_user",
            "phase": args.phase,
            "backend": backend,
            "message": "--profile is supported only for the codex backend.",
            "artifacts_dir": str(artifacts_dir),
            "result_path": str(result_path),
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
            "reply_path": str(reply_path),
            "probe": probe,
        }
        _write_json(result_path, payload)
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 1

    resolved_model, model_source = _resolve_model_override(backend, args.model)
    if backend == "codex":
        resolved_profile, profile_source = _resolve_codex_profile(args.profile)
    else:
        resolved_profile, profile_source = None, None

    timeout_seconds = _resolve_timeout_seconds(args.phase, args.timeout_seconds)

    _append_event(
        events_path,
        severity="INFO",
        event="phase_start",
        phase=args.phase,
        backend=backend,
        workdir=str(workdir),
        model=resolved_model,
        model_source=model_source,
        profile=resolved_profile,
        profile_source=profile_source,
        timeout_seconds=timeout_seconds,
    )

    run_result = _run_backend(
        backend=backend,
        binary=backend_info["binary"],
        prompt_text=prompt_text,
        workdir=workdir,
        reply_path=reply_path,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        effort=args.effort,
        model=resolved_model,
        profile=resolved_profile,
        timeout_seconds=timeout_seconds,
        dry_run=args.dry_run,
        events_path=events_path,
    )

    status, message = _classify_run_result(
        backend=backend,
        run_result=run_result,
        timeout_seconds=timeout_seconds,
        success_message="Subagent completed successfully.",
        workdir=workdir,
    )

    _append_event(
        events_path,
        severity="INFO" if status != "escalate_to_user" else "ERROR",
        event="phase_complete",
        phase=args.phase,
        backend=backend,
        status=status,
    )

    payload = {
        "status": status,
        "phase": args.phase,
        "backend": backend,
        "session_id": run_result["session_id"],
        "message": message,
        "artifacts_dir": str(artifacts_dir),
        "result_path": str(result_path),
        "prompt_path": str(prompt_copy_path),
        "reply_path": str(reply_path),
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "events_path": str(events_path),
        "process": {
            "command": run_result["command"],
            "exit_code": run_result["exit_code"],
            "timed_out": run_result["timed_out"],
            "dry_run": run_result["dry_run"],
            "timeout_seconds": timeout_seconds,
        },
        "selection": {
            "model": resolved_model,
            "model_source": model_source,
            "profile": resolved_profile if backend == "codex" else None,
            "profile_source": profile_source if backend == "codex" else None,
        },
        "probe": probe,
    }

    _write_json(result_path, payload)
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if status != "escalate_to_user" else 1


def _command_resume(args: argparse.Namespace) -> int:
    prompt_file = Path(args.prompt_file).resolve()
    workdir = Path(args.workdir).resolve()
    artifacts_dir = (
        Path(args.artifacts_dir).resolve()
        if args.artifacts_dir
        else Path(tempfile.mkdtemp(prefix="trycycle-runner-")).resolve()
    )
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    events_path = artifacts_dir / "events.jsonl"
    result_path = artifacts_dir / "result.json"
    stdout_path = artifacts_dir / "stdout.txt"
    stderr_path = artifacts_dir / "stderr.txt"
    reply_path = artifacts_dir / "reply.txt"
    prompt_copy_path = artifacts_dir / "prompt.txt"

    _copy_if_needed(prompt_file, prompt_copy_path)
    prompt_text = _read_text(prompt_file)
    probe = _probe_backends()

    backend, backend_error = _resolve_backend_selection(args.backend, probe=probe)

    if backend is None:
        payload = {
            "status": "escalate_to_user",
            "phase": args.phase,
            "backend": None,
            "session_id": args.session_id,
            "message": backend_error or "No supported backend is available.",
            "artifacts_dir": str(artifacts_dir),
            "result_path": str(result_path),
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
            "reply_path": str(reply_path),
            "probe": probe,
        }
        _write_json(result_path, payload)
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 1

    backend_info = probe["backends"][backend]
    if not backend_info["available"]:
        payload = {
            "status": "escalate_to_user",
            "phase": args.phase,
            "backend": backend,
            "session_id": args.session_id,
            "message": backend_info["reason"],
            "artifacts_dir": str(artifacts_dir),
            "result_path": str(result_path),
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
            "reply_path": str(reply_path),
            "probe": probe,
        }
        _write_json(result_path, payload)
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 1

    if not backend_info.get("supports_resume", False):
        payload = {
            "status": "escalate_to_user",
            "phase": args.phase,
            "backend": backend,
            "session_id": args.session_id,
            "message": f"{backend} is available but does not advertise resume support.",
            "artifacts_dir": str(artifacts_dir),
            "result_path": str(result_path),
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
            "reply_path": str(reply_path),
            "probe": probe,
        }
        _write_json(result_path, payload)
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 1

    if args.profile and backend != "codex":
        payload = {
            "status": "escalate_to_user",
            "phase": args.phase,
            "backend": backend,
            "session_id": args.session_id,
            "message": "--profile is supported only for the codex backend.",
            "artifacts_dir": str(artifacts_dir),
            "result_path": str(result_path),
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
            "reply_path": str(reply_path),
            "probe": probe,
        }
        _write_json(result_path, payload)
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 1

    resolved_model, model_source = _resolve_model_override(backend, args.model)
    if backend == "codex":
        resolved_profile, profile_source = _resolve_codex_profile(args.profile)
    else:
        resolved_profile, profile_source = None, None

    timeout_seconds = _resolve_timeout_seconds(args.phase, args.timeout_seconds)

    _append_event(
        events_path,
        severity="INFO",
        event="phase_resume",
        phase=args.phase,
        backend=backend,
        workdir=str(workdir),
        session_id=args.session_id,
        model=resolved_model,
        model_source=model_source,
        profile=resolved_profile,
        profile_source=profile_source,
        timeout_seconds=timeout_seconds,
    )

    run_result = _resume_backend(
        backend=backend,
        binary=backend_info["binary"],
        session_id=args.session_id,
        prompt_text=prompt_text,
        workdir=workdir,
        reply_path=reply_path,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        effort=args.effort,
        model=resolved_model,
        profile=resolved_profile,
        timeout_seconds=timeout_seconds,
        dry_run=args.dry_run,
        events_path=events_path,
    )

    status, message = _classify_run_result(
        backend=backend,
        run_result=run_result,
        timeout_seconds=timeout_seconds,
        success_message="Subagent resumed successfully.",
        workdir=workdir,
    )

    _append_event(
        events_path,
        severity="INFO" if status != "escalate_to_user" else "ERROR",
        event="phase_complete",
        phase=args.phase,
        backend=backend,
        status=status,
        session_id=args.session_id,
    )

    payload = {
        "status": status,
        "phase": args.phase,
        "backend": backend,
        "session_id": run_result["session_id"],
        "message": message,
        "artifacts_dir": str(artifacts_dir),
        "result_path": str(result_path),
        "prompt_path": str(prompt_copy_path),
        "reply_path": str(reply_path),
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "events_path": str(events_path),
        "process": {
            "command": run_result["command"],
            "exit_code": run_result["exit_code"],
            "timed_out": run_result["timed_out"],
            "dry_run": run_result["dry_run"],
            "timeout_seconds": timeout_seconds,
        },
        "selection": {
            "model": resolved_model,
            "model_source": model_source,
            "profile": resolved_profile if backend == "codex" else None,
            "profile_source": profile_source if backend == "codex" else None,
        },
        "probe": probe,
    }

    _write_json(result_path, payload)
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if status != "escalate_to_user" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Safe fallback runner for trycycle subagent dispatch via Codex, Claude, Kimi, or OpenCode.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    probe_parser = subparsers.add_parser(
        "probe",
        help="Detect supported Codex, Claude, Kimi, and OpenCode backends.",
    )
    probe_parser.set_defaults(func=_command_probe)

    run_parser = subparsers.add_parser(
        "run",
        help="Run a subagent prompt through Codex, Claude, Kimi, or OpenCode without shell quoting.",
    )
    run_parser.add_argument(
        "--phase",
        required=True,
        help="Logical trycycle phase for logging only.",
    )
    run_parser.add_argument(
        "--prompt-file",
        required=True,
        help="Path to the rendered prompt file to send verbatim.",
    )
    run_parser.add_argument(
        "--workdir",
        required=True,
        help="Working directory for the backend process.",
    )
    run_parser.add_argument(
        "--artifacts-dir",
        help="Directory for captured prompt, stdout, stderr, reply, and result files.",
    )
    run_parser.add_argument(
        "--backend",
        choices=["auto", "host", "codex", "claude", "kimi", "opencode"],
        default="auto",
        help="Backend selection policy. Use 'host' to stay on the parent backend.",
    )
    run_parser.add_argument(
        "--effort",
        choices=["low", "medium", "high", "max"],
        help="Reasoning effort hint. Codex maps this to model_reasoning_effort; Kimi maps it to thinking mode.",
    )
    run_parser.add_argument(
        "--profile",
        help=f"Codex only. Advanced override for an exact Codex profile name. If omitted, {CODEX_PROFILE_ENV} is used when set.",
    )
    run_parser.add_argument(
        "--model",
        help="Advanced backend-specific model override. Use only with an exact valid model name. If omitted, TRYCYCLE_<BACKEND>_MODEL is used when set.",
    )
    run_parser.add_argument(
        "--timeout-seconds",
        type=int,
        help="Override the hard timeout for the backend process. If omitted, trycycle phase defaults apply.",
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the selected backend and argv without executing the model.",
    )
    run_parser.set_defaults(func=_command_run)

    resume_parser = subparsers.add_parser(
        "resume",
        help="Resume a previously started subagent session.",
    )
    resume_parser.add_argument(
        "--phase",
        required=True,
        help="Logical trycycle phase for logging only.",
    )
    resume_parser.add_argument(
        "--session-id",
        required=True,
        help="Backend session id to resume.",
    )
    resume_parser.add_argument(
        "--prompt-file",
        required=True,
        help="Path to the rendered prompt file to send verbatim.",
    )
    resume_parser.add_argument(
        "--workdir",
        required=True,
        help="Working directory for the backend process.",
    )
    resume_parser.add_argument(
        "--artifacts-dir",
        help="Directory for captured prompt, stdout, stderr, reply, and result files.",
    )
    resume_parser.add_argument(
        "--backend",
        choices=["auto", "host", "codex", "claude", "kimi", "opencode"],
        default="auto",
        help="Backend selection policy. Use 'host' to stay on the parent backend.",
    )
    resume_parser.add_argument(
        "--effort",
        choices=["low", "medium", "high", "max"],
        help="Reasoning effort hint. Codex maps this to model_reasoning_effort; Kimi maps it to thinking mode.",
    )
    resume_parser.add_argument(
        "--profile",
        help=f"Codex only. Advanced override for an exact Codex profile name. If omitted, {CODEX_PROFILE_ENV} is used when set.",
    )
    resume_parser.add_argument(
        "--model",
        help="Advanced backend-specific model override. Use only with an exact valid model name. If omitted, TRYCYCLE_<BACKEND>_MODEL is used when set.",
    )
    resume_parser.add_argument(
        "--timeout-seconds",
        type=int,
        help="Override the hard timeout for the backend process. If omitted, trycycle phase defaults apply.",
    )
    resume_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the selected backend and argv without executing the model.",
    )
    resume_parser.set_defaults(func=_command_resume)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
