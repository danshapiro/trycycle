from __future__ import annotations

import argparse
from pathlib import Path
import sys

import claude_code
import codex_cli
import kimi_cli
import opencode_cli
from common import TranscriptError, choose_most_recent_match, render_transcript


ADAPTERS = {
    "claude-code": claude_code,
    "codex-cli": codex_cli,
    "kimi-cli": kimi_cli,
    "opencode": opencode_cli,
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
        help="Canary string used to identify the current transcript when direct lookup is unavailable or inconclusive.",
    )
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=60000,
        help="How long to wait for a fallback canary to appear in transcript files.",
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
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write the rendered transcript to this UTF-8 file instead of stdout.",
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
        chosen_path = None
        find_current_transcript = getattr(adapter, "find_current_transcript", None)
        can_lookup_directly = callable(find_current_transcript)
        if can_lookup_directly:
            chosen_path = find_current_transcript(search_root=args.search_root)

        if chosen_path is None:
            if not args.canary:
                if can_lookup_directly:
                    raise TranscriptError(
                        "A canary is required when the current session transcript cannot be determined directly."
                    )
                raise TranscriptError(f"A canary is required for {args.cli_name} transcript lookup.")
            matches = adapter.find_matching_transcripts(
                canary=args.canary,
                timeout_ms=args.timeout_ms,
                poll_ms=args.poll_ms,
                search_root=args.search_root,
            )
            if len(matches) == 1:
                chosen_path = matches[0]
            else:
                chosen_path = choose_most_recent_match(matches)

        transcript = render_transcript(adapter.extract_transcript(chosen_path))
    except TranscriptError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
    if args.output is None:
        sys.stdout.write(transcript)
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(transcript, encoding="utf-8")



if __name__ == "__main__":
    main()
