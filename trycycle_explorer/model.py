from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class DisplayConfig:
    title: str
    subtitle: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class Group:
    id: str
    label: str
    gates: list[str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class BindingField:
    name: str
    label: str
    help: str
    widget: str
    source_category: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class PaletteEntry:
    label: str
    fill: str
    ink: str
    accent: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class Diagnostic:
    severity: str
    code: str
    message: str
    gate_id: str | None = None
    prompt_source_id: str | None = None
    binding_name: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class PromptSource:
    id: str
    label: str
    source_path: str
    source_kind: str
    render_mode: str
    source_markdown: str
    template_ast: list[dict[str, object]] | None
    placeholder_names: list[str]
    required_nonempty_tags: list[str]
    ignore_tags_for_placeholders: list[str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class Outcome:
    id: str
    label: str
    to_gate_id: str
    provenance: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class Gate:
    id: str
    step_number: int
    title: str
    group: str
    source_path: str
    summary: str
    prompts: list[PromptSource]
    outcomes: list[Outcome]
    default_prompt_source_id: str

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "step_number": self.step_number,
            "title": self.title,
            "group": self.group,
            "source_path": self.source_path,
            "summary": self.summary,
            "prompts": [prompt.to_dict() for prompt in self.prompts],
            "outcomes": [outcome.to_dict() for outcome in self.outcomes],
            "default_prompt_source_id": self.default_prompt_source_id,
        }


@dataclass(frozen=True)
class SampleInput:
    id: str
    label: str
    description: str
    selected_gate_id: str
    selected_outcome_id: str | None
    selected_prompt_source_id: str | None
    bindings: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class DotNode:
    id: str
    label: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class DotEdge:
    from_node_id: str
    to_node_id: str
    label: str | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class DocumentedFlow:
    nodes: list[DotNode]
    edges: list[DotEdge]

    def to_dict(self) -> dict[str, object]:
        return {
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
        }


@dataclass(frozen=True)
class ExplorerModel:
    generated_at: str
    repo_root: str
    display: DisplayConfig
    intro_markdown: str
    outro_markdown: str
    groups: list[Group]
    bindings: dict[str, BindingField]
    provenance_palette: dict[str, PaletteEntry]
    documented_flow: DocumentedFlow
    diagnostics: list[Diagnostic]
    gates: list[Gate]
    sample_inputs: list[SampleInput]

    def to_dict(self) -> dict[str, object]:
        return {
            "repo_root": self.repo_root,
            "display": self.display.to_dict(),
            "intro_markdown": self.intro_markdown,
            "outro_markdown": self.outro_markdown,
            "groups": [group.to_dict() for group in self.groups],
            "bindings": {
                name: binding.to_dict() for name, binding in sorted(self.bindings.items())
            },
            "provenance_palette": {
                name: entry.to_dict()
                for name, entry in sorted(self.provenance_palette.items())
            },
            "documented_flow": self.documented_flow.to_dict(),
            "diagnostics": [diagnostic.to_dict() for diagnostic in self.diagnostics],
            "gates": [gate.to_dict() for gate in self.gates],
            "sample_inputs": [sample.to_dict() for sample in self.sample_inputs],
        }
