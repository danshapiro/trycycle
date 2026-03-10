from __future__ import annotations

import argparse
import sys
from pathlib import Path


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
    dump_model_parser.set_defaults(handler=handle_dump_model)
    return parser


def handle_build(args: argparse.Namespace) -> int:
    print(
        "trycycle explorer build is not implemented yet",
        file=sys.stderr,
    )
    return 1


def handle_dump_model(args: argparse.Namespace) -> int:
    print(
        "trycycle explorer dump-model is not implemented yet",
        file=sys.stderr,
    )
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)
