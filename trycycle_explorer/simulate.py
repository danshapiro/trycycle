from __future__ import annotations

import re
from dataclasses import dataclass

from orchestrator.prompt_builder.template_ast import IfNode, TextNode, ast_from_data

from .model import BindingField, Diagnostic, ExplorerModel, Gate, PromptSource


PLACEHOLDER_RE = re.compile(r"\{([A-Z][A-Z0-9_]*)\}")
TAG_RE_TEMPLATE = r"<{tag}>(?P<body>.*?)</{tag}>"
MISSING_PREFIX = "<<MISSING:"
MISSING_SUFFIX = ">>"


@dataclass(frozen=True)
class RenderedSegment:
    text: str
    category: str
    source_kind: str
    binding_name: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "text": self.text,
            "category": self.category,
            "source_kind": self.source_kind,
            "binding_name": self.binding_name,
        }


@dataclass(frozen=True)
class RenderSnapshot:
    gate_id: str
    outcome_id: str | None
    prompt_source_id: str
    prompt_markdown: str
    prompt_html_safe_source: str
    segments: list[RenderedSegment]
    diagnostics: list[Diagnostic]

    def to_dict(self) -> dict[str, object]:
        return {
            "gate_id": self.gate_id,
            "outcome_id": self.outcome_id,
            "prompt_source_id": self.prompt_source_id,
            "prompt_markdown": self.prompt_markdown,
            "prompt_html_safe_source": self.prompt_html_safe_source,
            "segments": [segment.to_dict() for segment in self.segments],
            "diagnostics": [diagnostic.to_dict() for diagnostic in self.diagnostics],
        }


def simulate_render(
    model: ExplorerModel,
    gate_id: str,
    bindings: dict[str, str],
    outcome_id: str | None = None,
    prompt_source_id: str | None = None,
) -> RenderSnapshot:
    gate = require_gate(model, gate_id)
    selected_prompt = pick_prompt_source(gate, prompt_source_id)
    markdown, segments, diagnostics = render_prompt(
        selected_prompt, bindings, model.bindings
    )
    return RenderSnapshot(
        gate_id=gate.id,
        outcome_id=outcome_id,
        prompt_source_id=selected_prompt.id,
        prompt_markdown=markdown,
        prompt_html_safe_source=escape_html(markdown),
        segments=segments,
        diagnostics=diagnostics,
    )


def require_gate(model: ExplorerModel, gate_id: str) -> Gate:
    for gate in model.gates:
        if gate.id == gate_id:
            return gate
    raise KeyError(gate_id)


def pick_prompt_source(gate: Gate, prompt_source_id: str | None) -> PromptSource:
    if prompt_source_id is None:
        prompt_source_id = gate.default_prompt_source_id
    for prompt in gate.prompts:
        if prompt.id == prompt_source_id:
            return prompt
    raise KeyError(prompt_source_id)


def render_prompt(
    prompt: PromptSource,
    bindings: dict[str, str],
    binding_fields: dict[str, BindingField],
) -> tuple[str, list[RenderedSegment], list[Diagnostic]]:
    if prompt.render_mode != "template" or prompt.template_ast is None:
        segment = RenderedSegment(
            text=prompt.source_markdown,
            category="template-text",
            source_kind=prompt.source_kind,
        )
        return prompt.source_markdown, [segment], []

    nodes = ast_from_data(prompt.template_ast)
    segments: list[RenderedSegment] = []
    diagnostics: list[Diagnostic] = []
    render_nodes(
        nodes,
        bindings,
        binding_fields,
        prompt,
        segments,
        diagnostics,
    )
    markdown = "".join(segment.text for segment in segments)
    diagnostics.extend(validate_required_tags(prompt, markdown))
    return markdown, segments, diagnostics


def render_nodes(
    nodes: list[TextNode | IfNode],
    bindings: dict[str, str],
    binding_fields: dict[str, BindingField],
    prompt: PromptSource,
    segments: list[RenderedSegment],
    diagnostics: list[Diagnostic],
) -> None:
    for node in nodes:
        if isinstance(node, TextNode):
            render_text_node(
                node.text,
                bindings,
                binding_fields,
                prompt,
                segments,
                diagnostics,
            )
            continue

        binding_value = bindings.get(node.name, "")
        if not binding_value:
            diagnostics.append(
                Diagnostic(
                    severity="warning",
                    code="missing-binding",
                    message=f"Conditional binding {node.name} is missing or empty.",
                    prompt_source_id=prompt.id,
                    binding_name=node.name,
                )
            )
        branch = node.truthy if binding_value else node.falsy
        render_nodes(
            branch,
            bindings,
            binding_fields,
            prompt,
            segments,
            diagnostics,
        )


def render_text_node(
    text: str,
    bindings: dict[str, str],
    binding_fields: dict[str, BindingField],
    prompt: PromptSource,
    segments: list[RenderedSegment],
    diagnostics: list[Diagnostic],
) -> None:
    cursor = 0
    for match in PLACEHOLDER_RE.finditer(text):
        if match.start() > cursor:
            segments.append(
                RenderedSegment(
                    text=text[cursor : match.start()],
                    category="template-text",
                    source_kind=prompt.source_kind,
                )
            )
        name = match.group(1)
        binding_value = bindings.get(name)
        if binding_value is not None and binding_value.strip():
            category = (
                binding_fields[name].source_category
                if name in binding_fields
                else "user-input"
            )
            segments.append(
                RenderedSegment(
                    text=binding_value,
                    category=category,
                    source_kind=prompt.source_kind,
                    binding_name=name,
                )
            )
        else:
            diagnostics.append(
                Diagnostic(
                    severity="warning",
                    code="missing-binding",
                    message=f"Missing placeholder value for {name}.",
                    prompt_source_id=prompt.id,
                    binding_name=name,
                )
            )
            segments.append(
                RenderedSegment(
                    text=f"{MISSING_PREFIX}{name}{MISSING_SUFFIX}",
                    category="missing-binding",
                    source_kind=prompt.source_kind,
                    binding_name=name,
                )
            )
        cursor = match.end()

    if cursor < len(text):
        segments.append(
            RenderedSegment(
                text=text[cursor:],
                category="template-text",
                source_kind=prompt.source_kind,
            )
        )


def validate_required_tags(
    prompt: PromptSource, markdown: str
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for tag in prompt.required_nonempty_tags:
        pattern = re.compile(TAG_RE_TEMPLATE.format(tag=re.escape(tag)), re.DOTALL)
        match = pattern.search(markdown)
        if not match:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="missing-required-tag",
                    message=f"Rendered prompt is missing required <{tag}> block.",
                    prompt_source_id=prompt.id,
                )
            )
            continue
        if not match.group("body").strip():
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="empty-required-tag",
                    message=f"Rendered prompt has empty <{tag}> block.",
                    prompt_source_id=prompt.id,
                )
            )
    return diagnostics


def escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
