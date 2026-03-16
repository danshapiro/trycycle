#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from template_ast import TemplateError, parse_template_text, render_nodes
from validate_rendered import ValidationError, validate_rendered_prompt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Render a trycycle prompt template with placeholders and conditional "
            "blocks, then validate the rendered output before writing stdout."
        )
    )
    parser.add_argument(
        "--template",
        required=True,
        type=Path,
        help="Path to the UTF-8 template file to render.",
    )
    parser.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="Bind a literal placeholder value.",
    )
    parser.add_argument(
        "--set-file",
        action="append",
        default=[],
        metavar="NAME=PATH",
        help="Bind a placeholder value from a UTF-8 file.",
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
    parser.add_argument(
        "--output",
        type=Path,
        help="Write the rendered prompt to this UTF-8 file instead of stdout.",
    )
    return parser.parse_args()


def parse_binding(raw: str) -> tuple[str, str]:
    if "=" not in raw:
        raise TemplateError(f"Binding must be NAME=VALUE, got: {raw!r}")
    name, value = raw.split("=", 1)
    if not re.fullmatch(r"[A-Z][A-Z0-9_]*", name):
        raise TemplateError(f"Invalid placeholder name: {name!r}")
    return name, value


def add_binding(bindings: dict[str, str], name: str, value: str) -> None:
    if name in bindings:
        raise TemplateError(f"duplicate binding for {name}")
    bindings[name] = value


def load_bindings(args: argparse.Namespace) -> dict[str, str]:
    bindings: dict[str, str] = {}

    for raw in args.set:
        name, value = parse_binding(raw)
        add_binding(bindings, name, value)

    for raw in args.set_file:
        name, file_path = parse_binding(raw)
        if name in bindings:
            raise TemplateError(f"Duplicate binding for {name}")
        try:
            value = Path(file_path).read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise TemplateError(
                f"Could not read binding file for {name}: {file_path}"
            ) from exc
        add_binding(bindings, name, value)

    return bindings


def validate_rendered_output(prompt_text: str, args: argparse.Namespace) -> None:
    try:
        validate_rendered_prompt(
            prompt_text,
            required_nonempty_tags=args.require_nonempty_tag,
            ignore_tags_for_placeholders=args.ignore_tag_for_placeholders,
        )
    except ValidationError as exc:
        raise TemplateError(str(exc)) from exc


def write_output(text: str, output_path: Path | None) -> None:
    if output_path is None:
        sys.stdout.write(text)
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")


def main() -> int:
    args = parse_args()
    try:
        template_text = args.template.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise TemplateError(f"Could not read template: {args.template}") from exc

    bindings = load_bindings(args)
    nodes = parse_template_text(template_text)
    rendered_prompt = render_nodes(nodes, bindings)
    validate_rendered_output(rendered_prompt, args)
    write_output(rendered_prompt, args.output)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except TemplateError as exc:
        print(f"prompt builder error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
