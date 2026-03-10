from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, TypeAlias


TOKEN_RE = re.compile(
    r"{{#if (?P<if>[A-Z][A-Z0-9_]*)}}|{{(?P<else>else)}}|{{(?P<endif>/if)}}"
)
PLACEHOLDER_RE = re.compile(r"\{([A-Z][A-Z0-9_]*)\}")


@dataclass(frozen=True)
class TextNode:
    text: str


@dataclass(frozen=True)
class IfNode:
    name: str
    truthy: list["Node"]
    falsy: list["Node"]


Node: TypeAlias = TextNode | IfNode
SerializedNode: TypeAlias = dict[str, object]
MissingHandler: TypeAlias = Callable[[str], str]


class TemplateError(RuntimeError):
    pass


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
                raise TemplateError(f"Unclosed conditional block for {value}")

            end_kind, _ = tokens[index]
            if end_kind == "else":
                falsy, index = parse_nodes(tokens, index + 1, {"endif"})
                if index >= len(tokens) or tokens[index][0] != "endif":
                    raise TemplateError(
                        f"Conditional block for {value} is missing {{/if}}"
                    )
            elif end_kind != "endif":
                raise TemplateError(
                    f"Unexpected token {end_kind!r} in conditional block for {value}"
                )

            nodes.append(IfNode(name=value, truthy=truthy, falsy=falsy))
            index += 1
            continue

        raise TemplateError(f"unexpected template token: {kind}")

    if stop:
        expected = " or ".join(sorted(stop))
        raise TemplateError(f"Expected {expected} before end of template")

    return nodes, index


def parse_template_text(template_text: str) -> list[Node]:
    tokens = tokenize(template_text)
    nodes, index = parse_nodes(tokens)
    if index != len(tokens):
        raise TemplateError("Template parsing stopped early")
    return nodes


def render_text(
    text: str,
    bindings: dict[str, str],
    on_missing: MissingHandler | None = None,
) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name in bindings:
            return bindings[name]
        if on_missing is not None:
            return on_missing(name)
        raise TemplateError(f"Missing placeholder value for {name}")

    return PLACEHOLDER_RE.sub(replace, text)


def render_nodes(
    nodes: list[Node],
    bindings: dict[str, str],
    on_missing: MissingHandler | None = None,
) -> str:
    rendered: list[str] = []

    for node in nodes:
        if isinstance(node, TextNode):
            rendered.append(render_text(node.text, bindings, on_missing=on_missing))
            continue

        branch = node.truthy if bindings.get(node.name, "") else node.falsy
        rendered.append(render_nodes(branch, bindings, on_missing=on_missing))

    return "".join(rendered)


def ast_to_data(nodes: list[Node]) -> list[SerializedNode]:
    serialized: list[SerializedNode] = []
    for node in nodes:
        if isinstance(node, TextNode):
            serialized.append({"type": "text", "text": node.text})
            continue
        serialized.append(
            {
                "type": "if",
                "name": node.name,
                "truthy": ast_to_data(node.truthy),
                "falsy": ast_to_data(node.falsy),
            }
        )
    return serialized


def ast_from_data(data: list[SerializedNode]) -> list[Node]:
    nodes: list[Node] = []
    for entry in data:
        node_type = entry.get("type")
        if node_type == "text":
            text = entry.get("text")
            if not isinstance(text, str):
                raise TemplateError("Serialized text node is missing string text")
            nodes.append(TextNode(text=text))
            continue

        if node_type == "if":
            name = entry.get("name")
            truthy = entry.get("truthy")
            falsy = entry.get("falsy")
            if not isinstance(name, str):
                raise TemplateError("Serialized if node is missing string name")
            if not isinstance(truthy, list) or not isinstance(falsy, list):
                raise TemplateError("Serialized if node is missing branch lists")
            nodes.append(
                IfNode(
                    name=name,
                    truthy=ast_from_data(truthy),
                    falsy=ast_from_data(falsy),
                )
            )
            continue

        raise TemplateError(f"Unknown serialized node type: {node_type!r}")

    return nodes
