from __future__ import annotations

from dataclasses import dataclass
import json
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Callable, Iterable, Literal


class TranscriptError(RuntimeError):
    pass


@dataclass(frozen=True)
class TranscriptTurn:
    order: int
    role: Literal["user", "assistant"]
    text: str


ANSI_ESCAPE_RE = re.compile(
    r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))"
)


def iter_jsonl_records(path: Path) -> Iterable[tuple[int, dict]]:
    try:
        lines = path.read_text().splitlines()
    except OSError as exc:
        raise TranscriptError(f"Failed to read transcript file {path}: {exc}") from exc

    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            yield line_number, json.loads(line)
        except json.JSONDecodeError as exc:
            raise TranscriptError(
                f"Failed to parse JSON in {path} on line {line_number}: {exc}"
            ) from exc


def choose_most_recent_match(paths: list[Path]) -> Path:
    if not paths:
        raise TranscriptError("No transcript files matched the canary.")
    return sorted(
        paths,
        key=lambda path: (path.stat().st_mtime_ns, str(path)),
        reverse=True,
    )[0]


def render_transcript(turns: list[TranscriptTurn]) -> str:
    # Emit structured JSON instead of XML-like tags so transcript text cannot
    # forge speaker boundaries or break the surrounding prompt container.
    ordered_turns = sorted(turns, key=lambda turn: turn.order)
    payload: list[dict[str, str]] = []
    for turn in ordered_turns:
        payload.append(
            {
                "role": turn.role,
                "text": sanitize_output_text(turn.text),
            }
        )
    return json.dumps(payload, indent=2, ensure_ascii=False)


def sanitize_output_text(text: str) -> str:
    # Preserve visible content while stripping terminal control sequences and
    # other low ASCII bytes that are hostile to files, shells, and prompts.
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    without_ansi = ANSI_ESCAPE_RE.sub("", normalized)
    return "".join(
        character
        for character in without_ansi
        if character in "\n\t" or (ord(character) >= 32 and ord(character) != 127)
    )


def rg_search(
    root: Path,
    canary: str,
    exclude_globs: list[str] | None = None,
    include_globs: list[str] | None = None,
) -> list[Path]:
    command = ["rg", "-l", "-F", canary, str(root)]
    for include_glob in include_globs or ["*.jsonl"]:
        command.extend(["--glob", include_glob])
    for exclude_glob in exclude_globs or []:
        command.extend(["--glob", f"!{exclude_glob}"])

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode not in (0, 1):
        raise TranscriptError(result.stderr.strip() or "ripgrep search failed.")
    return [Path(line) for line in result.stdout.splitlines() if line.strip()]


def rg_search_paths(paths: list[Path], canary: str) -> list[Path]:
    if not paths:
        return []

    command = ["rg", "-l", "-F", canary, *(str(path) for path in paths)]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode not in (0, 1):
        raise TranscriptError(result.stderr.strip() or "ripgrep search failed.")
    return [Path(line) for line in result.stdout.splitlines() if line.strip()]


def python_search(
    root: Path,
    canary: str,
    exclude_paths: Callable[[Path], bool] | None = None,
) -> list[Path]:
    matches: list[Path] = []
    for path in root.rglob("*.jsonl"):
        if exclude_paths and exclude_paths(path):
            continue
        try:
            if canary in path.read_text():
                matches.append(path)
        except OSError:
            continue
    return matches


def python_search_paths(paths: list[Path], canary: str) -> list[Path]:
    matches: list[Path] = []
    for path in paths:
        try:
            if canary in path.read_text():
                matches.append(path)
        except OSError:
            continue
    return matches


def wait_for_matches(
    *,
    root: Path,
    canary: str,
    timeout_ms: int,
    poll_ms: int,
    exclude_globs: list[str] | None = None,
    include_globs: list[str] | None = None,
    exclude_paths: Callable[[Path], bool] | None = None,
) -> list[Path]:
    deadline = time.monotonic() + (timeout_ms / 1000)
    use_rg = shutil.which("rg") is not None

    while True:
        if use_rg:
            matches = rg_search(
                root,
                canary,
                exclude_globs=exclude_globs,
                include_globs=include_globs,
            )
        else:
            matches = python_search(root, canary, exclude_paths=exclude_paths)

        if matches:
            return matches

        if time.monotonic() >= deadline:
            break
        time.sleep(poll_ms / 1000)

    raise TranscriptError(
        f"No transcript file under {root} contained canary {canary!r} within {timeout_ms}ms."
    )
