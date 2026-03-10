from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .extract import ExplorerError, build_model, select_sample
from .site import build_site


def emit_log(severity: str, event: str, **fields: object) -> None:
    payload = {"severity": severity, "event": event, **fields}
    print(json.dumps(payload, ensure_ascii=False), file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m trycycle_explorer",
        description="Build or inspect the static trycycle explorer.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser(
        "build",
        help="Build the static trycycle explorer site.",
    )
    build_parser.add_argument(
        "--repo",
        type=Path,
        default=Path("."),
        help="Path to the trycycle repository root.",
    )
    build_parser.add_argument(
        "--output",
        type=Path,
        default=Path("build/trycycle-explorer"),
        help="Directory to write the built static site into.",
    )
    build_parser.add_argument(
        "--sidecar",
        type=Path,
        default=None,
        help="Override the explorer sidecar config path.",
    )
    build_parser.add_argument(
        "--sample",
        default=None,
        help="Limit the built site to a single sample input id.",
    )
    build_parser.set_defaults(handler=handle_build)

    dump_model_parser = subparsers.add_parser(
        "dump-model",
        help="Write the extracted explorer model as JSON.",
    )
    dump_model_parser.add_argument(
        "--repo",
        type=Path,
        default=Path("."),
        help="Path to the trycycle repository root.",
    )
    dump_model_parser.add_argument(
        "--output",
        type=Path,
        default=Path("build/trycycle-explorer/explorer-model.json"),
        help="Path to the JSON file to write.",
    )
    dump_model_parser.add_argument(
        "--sidecar",
        type=Path,
        default=None,
        help="Override the explorer sidecar config path.",
    )
    dump_model_parser.add_argument(
        "--sample",
        default=None,
        help="Limit the dumped model to a single sample input id.",
    )
    dump_model_parser.set_defaults(handler=handle_dump_model)
    return parser


def handle_build(args: argparse.Namespace) -> int:
    repo_root = args.repo.resolve()
    output_dir = args.output.resolve()
    sidecar_path = args.sidecar.resolve() if args.sidecar is not None else None
    emit_log(
        "INFO",
        "build_start",
        repo_root=str(repo_root),
        output=str(output_dir),
        sidecar=str(sidecar_path) if sidecar_path is not None else None,
        sample=args.sample,
    )
    try:
        build_site(
            repo_root,
            output_dir,
            sidecar_path=sidecar_path,
            sample_id=args.sample,
        )
    except ExplorerError as exc:
        emit_log("ERROR", "build_failed", error=str(exc))
        print(f"trycycle explorer error: {exc}", file=sys.stderr)
        return 1

    emit_log("INFO", "build_complete", output=str(output_dir))
    return 0


def handle_dump_model(args: argparse.Namespace) -> int:
    repo_root = args.repo.resolve()
    output_path = args.output.resolve()
    sidecar_path = args.sidecar.resolve() if args.sidecar is not None else None
    emit_log(
        "INFO",
        "dump_model_start",
        repo_root=str(repo_root),
        output=str(output_path),
        sidecar=str(sidecar_path) if sidecar_path is not None else None,
        sample=args.sample,
    )
    try:
        model = build_model(repo_root, sidecar_path=sidecar_path)
        model = select_sample(model, args.sample)
    except ExplorerError as exc:
        emit_log("ERROR", "dump_model_failed", error=str(exc))
        print(f"trycycle explorer error: {exc}", file=sys.stderr)
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(model.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    emit_log(
        "INFO",
        "dump_model_complete",
        gate_count=len(model.gates),
        sample_count=len(model.sample_inputs),
        output=str(output_path),
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)
