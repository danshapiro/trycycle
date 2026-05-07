#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any


SEVERITIES = {"critical", "major", "minor", "nit"}


class LaterWorkError(RuntimeError):
    pass


def _expect_nonempty(value: str | None, field_name: str) -> str:
    if value is None or not value.strip():
        raise LaterWorkError(f"{field_name} is required")
    return value.strip()


def _validate_severity(value: str | None) -> str:
    severity = _expect_nonempty(value, "severity")
    if severity not in SEVERITIES:
        raise LaterWorkError(
            f"severity must be one of: {', '.join(sorted(SEVERITIES))}"
        )
    return severity


def _entry_from_args(args: argparse.Namespace) -> dict[str, str]:
    return {
        "id": f"LW-{uuid.uuid4().hex[:8]}",
        "title": _expect_nonempty(args.title, "title"),
        "severity": _validate_severity(args.severity),
        "why_it_matters": _expect_nonempty(args.why_it_matters, "why-it-matters"),
        "why_later_not_current": _expect_nonempty(
            args.why_later_not_current,
            "why-later-not-current",
        ),
        "evidence": _expect_nonempty(args.evidence, "evidence"),
        "suggested_follow_up": _expect_nonempty(
            args.suggested_follow_up,
            "suggested-follow-up",
        ),
    }


def _append_jsonl(path: Path, entry: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")


def _powershell_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _write_python_wrapper(wrapper_path: Path, script_path: Path, store_path: Path) -> None:
    wrapper_path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "from __future__ import annotations",
                "",
                "import runpy",
                "import sys",
                "",
                "sys.argv = [",
                f"    {str(script_path)!r},",
                '    "append",',
                '    "--path",',
                f"    {str(store_path)!r},",
                "    *sys.argv[1:],",
                "]",
                f"runpy.run_path({str(script_path)!r}, run_name='__main__')",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _command_metadata(python_exe: Path, wrapper_path: Path) -> dict[str, object]:
    argv = [str(python_exe), str(wrapper_path)]
    posix = shlex.join(argv)
    powershell = "& " + " ".join(_powershell_quote(part) for part in argv)
    cmd = subprocess.list2cmdline(argv)
    default = powershell if os.name == "nt" and os.environ.get("PSModulePath") else cmd
    if os.name != "nt":
        default = posix

    return {
        "file_later_work_argv": argv,
        "file_later_work_command": default,
        "file_later_work_command_posix": posix,
        "file_later_work_command_powershell": powershell,
        "file_later_work_command_cmd": cmd,
        "file_later_work_wrapper_path": str(wrapper_path),
    }


def command_init(args: argparse.Namespace) -> int:
    artifacts_dir = Path(args.artifacts_dir).resolve()
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    store_path = artifacts_dir / "later-work.jsonl"
    store_path.touch(exist_ok=True)

    wrapper_path = artifacts_dir / "file-later-work.py"
    python_exe = Path(sys.executable).resolve()
    script_path = Path(__file__).resolve()
    _write_python_wrapper(wrapper_path, script_path, store_path)

    payload = {
        "status": "ok",
        "later_work_path": str(store_path),
        **_command_metadata(python_exe, wrapper_path),
    }
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


def command_append(args: argparse.Namespace) -> int:
    store_path = Path(args.path).resolve()
    entry = _entry_from_args(args)
    _append_jsonl(store_path, entry)
    json.dump({"status": "filed", "id": entry["id"]}, sys.stdout, sort_keys=True)
    sys.stdout.write("\n")
    return 0


def _read_entries(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise LaterWorkError(f"invalid JSONL at line {line_number}: {exc}") from exc
        if not isinstance(raw, dict):
            raise LaterWorkError(f"entry at line {line_number} must be an object")
        entries.append(raw)
    return entries


def command_summarize(args: argparse.Namespace) -> int:
    entries = _read_entries(Path(args.path).resolve())
    if not entries:
        print("No later work was filed.")
        return 0

    print("## Later Work Found During This Run")
    print()
    for entry in entries:
        print(f"### {entry.get('title', 'Untitled later work')}")
        print()
        print(f"- ID: {entry.get('id', '')}")
        print(f"- Severity: {entry.get('severity', '')}")
        print(f"- Why it matters: {entry.get('why_it_matters', '')}")
        print(
            "- Why this is later work: "
            f"{entry.get('why_later_not_current', '')}"
        )
        print(f"- Evidence: {entry.get('evidence', '')}")
        print(f"- Suggested follow-up: {entry.get('suggested_follow_up', '')}")
        print()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Write-only later-work filing helper for Trycycle runs."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser(
        "init",
        help="Create a later-work store and cross-platform filing wrapper.",
    )
    init.add_argument("--artifacts-dir", required=True)
    init.set_defaults(func=command_init)

    append = subparsers.add_parser("append", help="Append one later-work finding.")
    append.add_argument("--path", required=True)
    append.add_argument("--title", required=True)
    append.add_argument("--severity", required=True)
    append.add_argument("--why-it-matters", required=True)
    append.add_argument("--why-later-not-current", required=True)
    append.add_argument("--evidence", required=True)
    append.add_argument("--suggested-follow-up", required=True)
    append.set_defaults(func=command_append)

    summarize = subparsers.add_parser(
        "summarize",
        help="Summarize later work at the end of a Trycycle run.",
    )
    summarize.add_argument("--path", required=True)
    summarize.set_defaults(func=command_summarize)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except LaterWorkError as exc:
        print(f"later_work error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
