#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


PLACEHOLDER_RE = re.compile(r"\{([A-Z][A-Z0-9_]*)\}")
TAG_RE_TEMPLATE = r"<{tag}>(?P<body>.*?)</{tag}>"


class ValidationError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate a rendered trycycle prompt before dispatch. Fails on "
            "unsubstituted placeholders and optionally on empty tagged blocks."
        )
    )
    parser.add_argument(
        "--prompt-file",
        required=True,
        type=Path,
        help="Path to the rendered prompt file to validate.",
    )
    parser.add_argument(
        "--require-nonempty-tag",
        action="append",
        default=[],
        metavar="TAG",
        help=(
            "Require that the rendered prompt contains a non-empty <TAG>...</TAG> "
            "block after trimming whitespace."
        ),
    )
    parser.add_argument(
        "--ignore-tag-for-placeholders",
        action="append",
        default=[],
        metavar="TAG",
        help=(
            "Ignore placeholder-like text inside <TAG>...</TAG> when checking "
            "for unsubstituted placeholders."
        ),
    )
    return parser.parse_args()


def read_prompt(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ValidationError(f"could not read prompt file: {path}") from exc


def validate_no_placeholders(prompt_text: str) -> None:
    matches = sorted(set(PLACEHOLDER_RE.findall(prompt_text)))
    if matches:
        raise ValidationError(
            "rendered prompt still contains unsubstituted placeholders: "
            + ", ".join(matches)
        )


def strip_tag_bodies(prompt_text: str, tags: list[str]) -> str:
    stripped = prompt_text
    for tag in tags:
        if not re.fullmatch(r"[a-z][a-z0-9_-]*", tag):
            raise ValidationError(f"invalid tag name: {tag!r}")
        pattern = re.compile(TAG_RE_TEMPLATE.format(tag=re.escape(tag)), re.DOTALL)
        stripped = pattern.sub(f"<{tag}></{tag}>", stripped)
    return stripped


def validate_nonempty_tag(prompt_text: str, tag: str) -> None:
    if not re.fullmatch(r"[a-z][a-z0-9_-]*", tag):
        raise ValidationError(f"invalid tag name: {tag!r}")

    pattern = re.compile(TAG_RE_TEMPLATE.format(tag=re.escape(tag)), re.DOTALL)
    match = pattern.search(prompt_text)
    if not match:
        raise ValidationError(f"rendered prompt is missing required <{tag}> block")

    if not match.group("body").strip():
        raise ValidationError(f"rendered prompt has empty <{tag}> block")


def validate_rendered_prompt(
    prompt_text: str,
    required_nonempty_tags: list[str] | None = None,
    ignore_tags_for_placeholders: list[str] | None = None,
) -> None:
    placeholder_scan_text = strip_tag_bodies(
        prompt_text, ignore_tags_for_placeholders or []
    )
    validate_no_placeholders(placeholder_scan_text)
    for tag in required_nonempty_tags or []:
        validate_nonempty_tag(prompt_text, tag)


def main() -> int:
    args = parse_args()
    prompt_text = read_prompt(args.prompt_file)
    validate_rendered_prompt(
        prompt_text,
        required_nonempty_tags=args.require_nonempty_tag,
        ignore_tags_for_placeholders=args.ignore_tag_for_placeholders,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValidationError as exc:
        print(f"rendered prompt validation error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
