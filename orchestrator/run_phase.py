#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PROMPT_BUILDER = SCRIPT_DIR / "prompt_builder" / "build.py"
TRANSCRIPT_BUILDER = SCRIPT_DIR / "user-request-transcript" / "build.py"
SUBAGENT_RUNNER = SCRIPT_DIR / "subagent_runner.py"


class PhaseError(RuntimeError):
    pass


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _emit_json(payload: dict[str, Any]) -> None:
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


def _parse_placeholder_name(raw: str) -> str:
    if not re.fullmatch(r"[A-Z][A-Z0-9_]*", raw):
        raise PhaseError(f"Invalid placeholder name: {raw!r}")
    return raw


def _parse_binding(raw: str) -> tuple[str, str]:
    if "=" not in raw:
        raise PhaseError(f"Binding must be NAME=VALUE, got: {raw!r}")
    name, value = raw.split("=", 1)
    return _parse_placeholder_name(name), value


def _detect_transcript_cli(selected: str) -> str:
    if selected != "auto":
        return selected
    if os.environ.get("CODEX_THREAD_ID") or os.environ.get("CODEX_HOME"):
        return "codex-cli"
    if os.environ.get("CLAUDECODE"):
        return "claude-code"
    if os.environ.get("OPENCODE"):
        return "opencode"
    raise PhaseError("Could not detect transcript CLI. Pass --transcript-cli explicitly.")


def _run_command(
    argv: list[str],
    *,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        argv,
        text=True,
        capture_output=True,
        check=False,
        cwd=cwd,
    )
    if result.returncode != 0:
        raise PhaseError(result.stderr.strip() or f"Command failed: {' '.join(argv)}")
    return result


def _prepare_transcripts(
    args: argparse.Namespace,
    artifacts_dir: Path,
    *,
    workdir: Path,
) -> tuple[str | None, dict[str, str]]:
    placeholders = [_parse_placeholder_name(raw) for raw in args.transcript_placeholder]
    if not placeholders:
        return None, {}

    cli_name = _detect_transcript_cli(args.transcript_cli)
    if cli_name == "claude-code" and not args.canary:
        raise PhaseError(
            "Claude transcript lookup requires --canary from a prior top-level canary command."
        )

    inputs_dir = artifacts_dir / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    rendered_paths: dict[str, str] = {}

    first_placeholder = placeholders[0]
    first_output_path = inputs_dir / f"{first_placeholder}.txt"
    transcript_search_root = None
    if args.transcript_search_root:
        transcript_search_root = args.transcript_search_root
        if not transcript_search_root.is_absolute():
            transcript_search_root = (Path.cwd() / transcript_search_root).resolve()

    command = [
        sys.executable,
        str(TRANSCRIPT_BUILDER),
        "--cli",
        cli_name,
        "--output",
        str(first_output_path),
    ]
    if args.canary:
        command.extend(["--canary", args.canary])
    if transcript_search_root:
        command.extend(["--search-root", str(transcript_search_root)])
    _run_command(command, cwd=workdir)
    rendered_paths[first_placeholder] = str(first_output_path)

    for placeholder in placeholders[1:]:
        path = inputs_dir / f"{placeholder}.txt"
        shutil.copyfile(first_output_path, path)
        rendered_paths[placeholder] = str(path)

    return cli_name, rendered_paths


def _build_prompt(
    args: argparse.Namespace,
    artifacts_dir: Path,
    transcript_paths: dict[str, str],
) -> Path:
    prompt_path = artifacts_dir / "prompt.txt"
    command = [
        sys.executable,
        str(PROMPT_BUILDER),
        "--template",
        str(Path(args.template).resolve()),
        "--output",
        str(prompt_path),
    ]
    for raw in args.set:
        command.extend(["--set", raw])
    for raw in args.set_file:
        command.extend(["--set-file", raw])
    for name, path in transcript_paths.items():
        command.extend(["--set-file", f"{name}={path}"])
    for tag in args.require_nonempty_tag:
        command.extend(["--require-nonempty-tag", tag])
    for tag in args.ignore_tag_for_placeholders:
        command.extend(["--ignore-tag-for-placeholders", tag])
    _run_command(command)
    return prompt_path


def _prepare_phase(args: argparse.Namespace) -> dict[str, Any]:
    workdir = Path(args.workdir).resolve()
    artifacts_dir = (
        Path(args.artifacts_dir).resolve()
        if args.artifacts_dir
        else Path(tempfile.mkdtemp(prefix=f"trycycle-phase-{args.phase}-")).resolve()
    )
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    transcript_cli, transcript_paths = _prepare_transcripts(
        args,
        artifacts_dir,
        workdir=workdir,
    )
    prompt_path = _build_prompt(args, artifacts_dir, transcript_paths)

    payload = {
        "status": "prepared",
        "phase": args.phase,
        "artifacts_dir": str(artifacts_dir),
        "result_path": str(artifacts_dir / "result.json"),
        "template_path": str(Path(args.template).resolve()),
        "workdir": str(workdir),
        "prompt_path": str(prompt_path),
        "transcript_cli": transcript_cli,
        "transcript_paths": transcript_paths,
    }
    if args.canary:
        payload["canary"] = args.canary
    _write_json(Path(payload["result_path"]), payload)
    return payload


def _command_prepare(args: argparse.Namespace) -> int:
    payload = _prepare_phase(args)
    _emit_json(payload)
    return 0


def _command_run(args: argparse.Namespace) -> int:
    payload = _prepare_phase(args)
    dispatch_dir = Path(payload["artifacts_dir"]) / "dispatch"
    dispatch_dir.mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable,
        str(SUBAGENT_RUNNER),
        "run",
        "--phase",
        args.phase,
        "--prompt-file",
        payload["prompt_path"],
        "--workdir",
        str(Path(args.workdir).resolve()),
        "--artifacts-dir",
        str(dispatch_dir),
        "--backend",
        args.backend,
    ]
    if args.effort:
        command.extend(["--effort", args.effort])
    if args.profile:
        command.extend(["--profile", args.profile])
    if args.model:
        command.extend(["--model", args.model])
    if args.timeout_seconds is not None:
        command.extend(["--timeout-seconds", str(args.timeout_seconds)])
    if args.dry_run:
        command.append("--dry-run")

    dispatch_result = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
    )
    dispatch_payload: dict[str, Any] | None = None
    if dispatch_result.stdout.strip():
        try:
            dispatch_payload = json.loads(dispatch_result.stdout)
        except json.JSONDecodeError as exc:
            raise PhaseError(
                f"subagent runner returned non-JSON stdout: {dispatch_result.stdout!r}"
            ) from exc
    if dispatch_payload is None:
        result_path = dispatch_dir / "result.json"
        if result_path.exists():
            dispatch_payload = json.loads(result_path.read_text(encoding="utf-8"))
        else:
            raise PhaseError(dispatch_result.stderr.strip() or "subagent runner returned no result")

    final_payload = {
        **payload,
        "status": dispatch_payload["status"],
        "dispatch": dispatch_payload,
        "result_path": str(Path(payload["artifacts_dir"]) / "result.json"),
    }
    _write_json(Path(final_payload["result_path"]), final_payload)
    _emit_json(final_payload)
    return 0 if dispatch_result.returncode == 0 else dispatch_result.returncode


def _add_prepare_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--phase", required=True, help="Logical trycycle phase name.")
    parser.add_argument("--template", required=True, help="Prompt template path.")
    parser.add_argument("--workdir", required=True, help="Worktree or repo path.")
    parser.add_argument(
        "--artifacts-dir",
        help="Directory for prompt, transcript, and result artifacts.",
    )
    parser.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="Bind a literal placeholder value for prompt rendering.",
    )
    parser.add_argument(
        "--set-file",
        action="append",
        default=[],
        metavar="NAME=PATH",
        help="Bind a placeholder value from an existing UTF-8 file.",
    )
    parser.add_argument(
        "--transcript-placeholder",
        action="append",
        default=[],
        metavar="NAME",
        help="Bind the current session transcript to this placeholder name.",
    )
    parser.add_argument(
        "--transcript-cli",
        choices=["auto", "codex-cli", "claude-code", "kimi-cli", "opencode"],
        default="auto",
        help="Transcript provider to use for transcript placeholders.",
    )
    parser.add_argument(
        "--transcript-search-root",
        type=Path,
        help="Override transcript search root for testing or debugging.",
    )
    parser.add_argument(
        "--canary",
        help="Existing transcript canary to use when direct lookup is unavailable.",
    )
    parser.add_argument(
        "--require-nonempty-tag",
        action="append",
        default=[],
        metavar="TAG",
        help="Require a rendered prompt tag to contain non-empty content.",
    )
    parser.add_argument(
        "--ignore-tag-for-placeholders",
        action="append",
        default=[],
        metavar="TAG",
        help="Ignore placeholder-like text inside this rendered tag.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare and optionally dispatch a trycycle phase prompt.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser(
        "prepare",
        help="Build transcript and prompt artifacts for a phase.",
    )
    _add_prepare_arguments(prepare_parser)
    prepare_parser.set_defaults(func=_command_prepare)

    run_parser = subparsers.add_parser(
        "run",
        help="Prepare a phase prompt, then dispatch it through the fallback subagent runner.",
    )
    _add_prepare_arguments(run_parser)
    run_parser.add_argument(
        "--backend",
        choices=["auto", "host", "codex", "claude", "kimi", "opencode"],
        default="auto",
        help="Subagent backend selection policy.",
    )
    run_parser.add_argument(
        "--effort",
        choices=["low", "medium", "high", "max"],
        help="Reasoning effort hint for the subagent backend.",
    )
    run_parser.add_argument(
        "--profile",
        help="Codex only. Advanced profile override forwarded to subagent_runner.py.",
    )
    run_parser.add_argument(
        "--model",
        help="Advanced exact model override forwarded to subagent_runner.py. Use only with a valid exact backend model name.",
    )
    run_parser.add_argument(
        "--timeout-seconds",
        type=int,
        help="Override the runner timeout in seconds. If omitted, subagent_runner.py phase defaults apply.",
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Prepare normally, then dry-run the fallback subagent dispatch.",
    )
    run_parser.set_defaults(func=_command_run)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except PhaseError as exc:
        print(f"run_phase error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
