#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


TOKEN_RE = re.compile(
    r"{{#if (?P<if>[A-Z][A-Z0-9_]*)}}|{{(?P<else>else)}}|{{(?P<endif>/if)}}"
)
PLACEHOLDER_RE = re.compile(r"\{([A-Z][A-Z0-9_]*)\}")


@dataclass
class TextNode:
    text: str


@dataclass
class IfNode:
    name: str
    truthy: list["Node"]
    falsy: list["Node"]


Node = TextNode | IfNode


class TemplateError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render a trycycle prompt template with placeholders and conditional blocks."
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
    return parser.parse_args()


def parse_binding(raw: str) -> tuple[str, str]:
    if "=" not in raw:
        raise TemplateError(f"binding must be NAME=VALUE, got {raw!r}")
    name, value = raw.split("=", 1)
    if not re.fullmatch(r"[A-Z][A-Z0-9_]*", name):
        raise TemplateError(f"invalid placeholder name: {name!r}")
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
            raise TemplateError(f"duplicate binding for {name}")
        try:
            value = Path(file_path).read_text(encoding="utf-8")
        except OSError as exc:
            raise TemplateError(
                f"could not read binding file for {name}: {file_path}"
            ) from exc
        add_binding(bindings, name, value)

    return bindings


def tokenize(template: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    cursor = 0

    for match in TOKEN_RE.finditer(template):
        if match.start() > cursor:
            tokens.append(("text", template[cursor : match.start()]))
        if match.group("if"):
            tokens.append(("if", match.group("if")))
        elif match.group("else"):
            tokens.append(("else", ""))
        else:
            tokens.append(("endif", ""))
        cursor = match.end()

    if cursor < len(template):
        tokens.append(("text", template[cursor:]))

    return tokens


def parse_nodes(
    tokens: list[tuple[str, str]],
    index: int = 0,
    stop: set[str] | None = None,
) -> tuple[list[Node], int]:
    nodes: list[Node] = []
    stop = stop or set()

    while index < len(tokens):
        kind, value = tokens[index]

        if kind in stop:
            return nodes, index

        if kind == "text":
            nodes.append(TextNode(value))
            index += 1
            continue

        if kind == "if":
            truthy, index = parse_nodes(tokens, index + 1, {"else", "endif"})
            falsy: list[Node] = []

            if index >= len(tokens):
                raise TemplateError(f"unclosed conditional block for {value}")

            end_kind, _ = tokens[index]
            if end_kind == "else":
                falsy, index = parse_nodes(tokens, index + 1, {"endif"})
                if index >= len(tokens) or tokens[index][0] != "endif":
                    raise TemplateError(
                        f"conditional block for {value} is missing {{/if}}"
                    )
            elif end_kind != "endif":
                raise TemplateError(
                    f"unexpected token {end_kind!r} in conditional block for {value}"
                )

            nodes.append(IfNode(name=value, truthy=truthy, falsy=falsy))
            index += 1
            continue

        raise TemplateError(f"unexpected template token: {kind}")

    if stop:
        expected = " or ".join(sorted(stop))
        raise TemplateError(f"expected {expected} before end of template")

    return nodes, index


def render_text(text: str, bindings: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in bindings:
            raise TemplateError(f"missing placeholder value for {name}")
        return bindings[name]

    return PLACEHOLDER_RE.sub(replace, text)


def render_nodes(nodes: list[Node], bindings: dict[str, str]) -> str:
    rendered: list[str] = []

    for node in nodes:
        if isinstance(node, TextNode):
            rendered.append(render_text(node.text, bindings))
            continue

        branch = node.truthy if bindings.get(node.name, "") else node.falsy
        rendered.append(render_nodes(branch, bindings))

    return "".join(rendered)


def main() -> int:
    args = parse_args()
    try:
        template_text = args.template.read_text(encoding="utf-8")
    except OSError as exc:
        raise TemplateError(f"could not read template: {args.template}") from exc

    bindings = load_bindings(args)
    tokens = tokenize(template_text)
    nodes, index = parse_nodes(tokens)
    if index != len(tokens):
        raise TemplateError("template parsing stopped early")

    sys.stdout.write(render_nodes(nodes, bindings))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except TemplateError as exc:
        print(f"prompt builder error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
