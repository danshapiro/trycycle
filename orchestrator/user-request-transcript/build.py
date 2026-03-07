from __future__ import annotations

import argparse
from pathlib import Path
import sys

import claude_code
import codex_cli
from common import TranscriptError, choose_most_recent_match, render_transcript


ADAPTERS = {
    "claude-code": claude_code,
    "codex-cli": codex_cli,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cli",
        dest="cli_name",
        required=True,
        choices=tuple(ADAPTERS.keys()),
        help="CLI transcript format to parse.",
    )
    parser.add_argument(
        "--canary",
        required=True,
        help="Unique canary string already present in the target transcript.",
    )
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=60000,
        help="How long to wait for the canary to appear in transcript files.",
    )
    parser.add_argument(
        "--poll-ms",
        type=int,
        default=100,
        help="Polling interval while waiting for the canary to appear.",
    )
    parser.add_argument(
        "--search-root",
        type=Path,
        default=None,
        help="Override the transcript search root. Intended for validation and debugging.",
    )
    args = parser.parse_args()
    if args.timeout_ms < 0:
        parser.error("--timeout-ms must be >= 0")
    if args.poll_ms < 1:
        parser.error("--poll-ms must be >= 1")
    return args


def main() -> None:
    args = parse_args()
    adapter = ADAPTERS[args.cli_name]
    try:
        matches = adapter.find_matching_transcripts(
            canary=args.canary,
            timeout_ms=args.timeout_ms,
            poll_ms=args.poll_ms,
            search_root=args.search_root,
        )
        chosen_path = choose_most_recent_match(matches)
        transcript = render_transcript(adapter.extract_transcript(chosen_path))
    except TranscriptError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
    sys.stdout.write(transcript)


if __name__ == "__main__":
    main()
