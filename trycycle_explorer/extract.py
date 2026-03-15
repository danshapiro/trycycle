from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from orchestrator.prompt_builder.template_ast import (
    IfNode,
    TextNode,
    ast_to_data,
    parse_template_text,
)

from .model import (
    BindingField,
    Diagnostic,
    DisplayConfig,
    DocumentedFlow,
    DotEdge,
    DotNode,
    ExplorerModel,
    Gate,
    Group,
    Outcome,
    PaletteEntry,
    PromptSource,
    SampleInput,
)


SECTION_RE = re.compile(r"^##\s+(?P<number>\d+)\)\s+(?P<title>.+)$", re.MULTILINE)
PATH_RE = re.compile(r"<skill-directory>/([A-Za-z0-9_./-]+)")
DOT_NODE_RE = re.compile(
    r"(?ms)^\s*(?P<id>[A-Za-z_][A-Za-z0-9_]*)\s*\[(?P<body>.*?)\]\s*;"
)
DOT_EDGE_RE = re.compile(
    r"(?ms)^\s*(?P<from>[A-Za-z_][A-Za-z0-9_]*)\s*->\s*(?P<to>[A-Za-z_][A-Za-z0-9_]*)"
    r"(?:\s*\[(?P<body>.*?)\])?\s*;"
)
LABEL_RE = re.compile(r'label="(?P<label>(?:\\.|[^"])*)"')
NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
PAREN_RE = re.compile(r"\s*\([^)]*\)")
PLACEHOLDER_RE = re.compile(r"\{([A-Z][A-Z0-9_]*)\}")
FRONT_MATTER_RE = re.compile(r"\A---\s*\n.*?\n---\s*\n?", re.DOTALL)
POST_FLOW_HEADING_RE = re.compile(r"^(?:#|##)\s+(?!\d+\))", re.MULTILINE)
REQUIRE_NONEMPTY_TAG_RE = re.compile(
    r"--require-nonempty-tag\s+([a-z][a-z0-9_-]*)"
)
IGNORE_TAG_FOR_PLACEHOLDERS_RE = re.compile(
    r"--ignore-tag-for-placeholders\s+([a-z][a-z0-9_-]*)"
)


class ExplorerError(RuntimeError):
    pass


@dataclass(frozen=True)
class SkillSection:
    step_number: int
    title: str
    gate_id: str
    markdown: str


@dataclass(frozen=True)
class SkillDocument:
    intro_markdown: str
    sections: list[SkillSection]
    outro_markdown: str


def build_model(repo_root: Path, sidecar_path: Path | None = None) -> ExplorerModel:
    repo_root = repo_root.resolve()
    default_sidecar_path = (repo_root / "trycycle_explorer" / "explorer.toml").resolve()
    sidecar_path = (sidecar_path or default_sidecar_path).resolve()

    skill_path = repo_root / "SKILL.md"
    dot_path = repo_root / "docs/trycycle-information-flow.dot"
    sidecar = load_sidecar(default_sidecar_path)
    if sidecar_path != default_sidecar_path:
        sidecar = merge_sidecars(sidecar, load_sidecar(sidecar_path))
    skill_document = parse_skill_document(skill_path.read_text(encoding="utf-8"))
    sections = skill_document.sections
    documented_flow = parse_documented_flow(dot_path.read_text(encoding="utf-8"))

    groups = load_groups(sidecar)
    group_by_gate = build_group_lookup(groups)

    gates: list[Gate] = []
    placeholder_names: set[str] = set()

    for section in sections:
        prompts = extract_prompt_sources(repo_root, section)
        for prompt in prompts:
            placeholder_names.update(prompt.placeholder_names)
        outcomes = load_outcomes(sidecar, section.gate_id)
        group_id = group_by_gate.get(section.gate_id, "ungrouped")
        summary = summarize_section(section.markdown)
        gates.append(
            Gate(
                id=section.gate_id,
                step_number=section.step_number,
                title=section.title,
                group=group_id,
                source_path="SKILL.md",
                summary=summary,
                prompts=prompts,
                outcomes=outcomes,
                default_prompt_source_id=pick_default_prompt(prompts),
            )
        )

    binding_fields = load_binding_fields(sidecar, placeholder_names)
    sample_inputs = load_sample_inputs(repo_root, sidecar)
    provenance_palette = load_palette(sidecar)

    gate_ids = {gate.id for gate in gates}
    validate_sidecar_outcomes(sidecar, gate_ids)
    validate_outcomes(gates, gate_ids)
    validate_samples(sample_inputs, {gate.id: gate for gate in gates})

    return ExplorerModel(
        generated_at=datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        repo_root=str(repo_root),
        display=DisplayConfig(
            title=str(sidecar["display"]["title"]),
            subtitle=str(sidecar["display"]["subtitle"]),
        ),
        intro_markdown=skill_document.intro_markdown,
        outro_markdown=skill_document.outro_markdown,
        groups=groups,
        bindings=binding_fields,
        provenance_palette=provenance_palette,
        documented_flow=documented_flow,
        diagnostics=[],
        gates=gates,
        sample_inputs=sample_inputs,
    )


def load_sidecar(path: Path) -> dict[str, Any]:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise ExplorerError(f"Could not read sidecar config: {path}") from exc


def merge_sidecars(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            merged[key] = merge_sidecars(base[key], value)
            continue
        merged[key] = value
    return merged


def parse_skill_document(skill_text: str) -> SkillDocument:
    skill_body = strip_front_matter(skill_text).strip()
    matches = list(SECTION_RE.finditer(skill_body))
    sections: list[SkillSection] = []
    outro_markdown = ""

    if not matches:
        return SkillDocument(
            intro_markdown=normalize_markdown_block(skill_body),
            sections=[],
            outro_markdown="",
        )

    intro_markdown = normalize_markdown_block(skill_body[: matches[0].start()])

    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(skill_body)
        title = match.group("title").strip()
        body = skill_body[start:end]
        if index == len(matches) - 1:
            split_match = POST_FLOW_HEADING_RE.search(body)
            if split_match:
                outro_markdown = normalize_markdown_block(body[split_match.start() :])
                body = body[: split_match.start()]
        normalized_body = body.strip()
        markdown = f"## {match.group('number')}) {title}\n"
        if normalized_body:
            markdown = f"{markdown}\n{normalized_body}\n"
        sections.append(
            SkillSection(
                step_number=int(match.group("number")),
                title=title,
                gate_id=slugify_title(title),
                markdown=markdown,
            )
        )

    return SkillDocument(
        intro_markdown=intro_markdown,
        sections=sections,
        outro_markdown=outro_markdown,
    )


def strip_front_matter(skill_text: str) -> str:
    return FRONT_MATTER_RE.sub("", skill_text, count=1)


def normalize_markdown_block(markdown: str) -> str:
    normalized = markdown.strip()
    if not normalized:
        return ""
    return f"{normalized}\n"


def slugify_title(title: str) -> str:
    without_parens = PAREN_RE.sub("", title).strip().lower()
    return NON_ALNUM_RE.sub("-", without_parens).strip("-")


def parse_documented_flow(dot_text: str) -> DocumentedFlow:
    nodes: list[DotNode] = []
    seen_nodes: set[str] = set()
    for match in DOT_NODE_RE.finditer(dot_text):
        raw = match.group(0)
        if "->" in raw:
            continue
        node_id = match.group("id")
        if node_id in {"graph", "node", "edge"} or node_id in seen_nodes:
            continue
        body = match.group("body")
        label_match = LABEL_RE.search(body)
        label = decode_dot_label(label_match.group("label")) if label_match else node_id
        nodes.append(DotNode(id=node_id, label=label))
        seen_nodes.add(node_id)

    edges: list[DotEdge] = []
    for match in DOT_EDGE_RE.finditer(dot_text):
        body = match.group("body") or ""
        label_match = LABEL_RE.search(body)
        label = decode_dot_label(label_match.group("label")) if label_match else None
        edges.append(
            DotEdge(
                from_node_id=match.group("from"),
                to_node_id=match.group("to"),
                label=label,
            )
        )

    return DocumentedFlow(nodes=nodes, edges=edges)


def decode_dot_label(raw: str) -> str:
    return raw.replace("\\n", "\n").replace('\\"', '"')


def load_groups(sidecar: dict[str, Any]) -> list[Group]:
    groups: list[Group] = []
    for entry in sidecar.get("groups", []):
        groups.append(
            Group(
                id=str(entry["id"]),
                label=str(entry["label"]),
                gates=[str(item) for item in entry.get("gates", [])],
            )
        )
    return groups


def build_group_lookup(groups: list[Group]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for group in groups:
        for gate_id in group.gates:
            lookup[gate_id] = group.id
    return lookup


def load_outcomes(sidecar: dict[str, Any], gate_id: str) -> list[Outcome]:
    outcomes: list[Outcome] = []
    for entry in sidecar.get("outcomes", []):
        if entry.get("from") != gate_id:
            continue
        outcomes.append(
            Outcome(
                id=str(entry["id"]),
                label=str(entry["label"]),
                to_gate_id=str(entry["to"]),
                provenance="sidecar-overlay",
            )
        )
    return outcomes


def summarize_section(markdown: str) -> str:
    lines = [line.strip() for line in markdown.splitlines()[1:] if line.strip()]
    return lines[0] if lines else ""


def extract_prompt_sources(repo_root: Path, section: SkillSection) -> list[PromptSource]:
    prompts = [
        build_prompt_source(
            prompt_id=f"{section.gate_id}::orchestrator",
            label="Orchestrator gate",
            source_path="SKILL.md",
            source_kind="orchestrator-section",
            render_mode="literal",
            markdown=section.markdown,
            required_nonempty_tags=[],
            ignore_tags_for_placeholders=[],
        )
    ]

    seen_paths: set[str] = set()
    for relative_path in PATH_RE.findall(section.markdown):
        if not (
            relative_path.startswith("subagents/")
            or relative_path.startswith("subskills/")
        ):
            continue
        if relative_path in seen_paths:
            continue
        seen_paths.add(relative_path)
        path = repo_root / relative_path
        try:
            markdown = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise ExplorerError(f"Could not read prompt source: {path}") from exc
        source_kind = (
            "subagent-template"
            if relative_path.startswith("subagents/")
            else "subskill"
        )
        required_nonempty_tags, ignore_tags_for_placeholders = (
            extract_prompt_constraints(section.markdown, relative_path)
        )
        prompts.append(
            build_prompt_source(
                prompt_id=f"{section.gate_id}::{source_kind}::{path.stem.lower()}",
                label=derive_prompt_label(relative_path, source_kind),
                source_path=relative_path,
                source_kind=source_kind,
                render_mode=(
                    "template" if source_kind == "subagent-template" else "literal"
                ),
                markdown=markdown,
                required_nonempty_tags=required_nonempty_tags,
                ignore_tags_for_placeholders=ignore_tags_for_placeholders,
            )
        )

    return prompts


def derive_prompt_label(relative_path: str, source_kind: str) -> str:
    if source_kind == "subagent-template":
        stem = Path(relative_path).stem.replace("prompt-", "")
        return stem.replace("-", " ").title()
    return Path(relative_path).parent.name.replace("-", " ").title()


def build_prompt_source(
    *,
    prompt_id: str,
    label: str,
    source_path: str,
    source_kind: str,
    render_mode: str,
    markdown: str,
    required_nonempty_tags: list[str],
    ignore_tags_for_placeholders: list[str],
) -> PromptSource:
    nodes = parse_template_text(markdown)
    placeholder_names = sorted(extract_placeholder_names(nodes))
    return PromptSource(
        id=prompt_id,
        label=label,
        source_path=source_path,
        source_kind=source_kind,
        render_mode=render_mode,
        source_markdown=markdown,
        template_ast=ast_to_data(nodes),
        placeholder_names=placeholder_names,
        required_nonempty_tags=required_nonempty_tags,
        ignore_tags_for_placeholders=ignore_tags_for_placeholders,
    )


def extract_prompt_constraints(
    section_markdown: str, relative_path: str
) -> tuple[list[str], list[str]]:
    required_nonempty_tags: set[str] = set()
    ignore_tags_for_placeholders: set[str] = set()
    prompt_reference = f"<skill-directory>/{relative_path}"

    for line in section_markdown.splitlines():
        if prompt_reference not in line:
            continue
        required_nonempty_tags.update(REQUIRE_NONEMPTY_TAG_RE.findall(line))
        ignore_tags_for_placeholders.update(
            IGNORE_TAG_FOR_PLACEHOLDERS_RE.findall(line)
        )

    return sorted(required_nonempty_tags), sorted(ignore_tags_for_placeholders)


def extract_placeholder_names(nodes: list[TextNode | IfNode]) -> set[str]:
    names: set[str] = set()
    for node in nodes:
        if isinstance(node, TextNode):
            names.update(PLACEHOLDER_RE.findall(node.text))
            continue
        names.add(node.name)
        names.update(extract_placeholder_names(node.truthy))
        names.update(extract_placeholder_names(node.falsy))
    return names


def pick_default_prompt(prompts: list[PromptSource]) -> str:
    for prompt in prompts:
        if prompt.source_kind == "subagent-template":
            return prompt.id
    return prompts[0].id


def load_binding_fields(
    sidecar: dict[str, Any], placeholder_names: set[str]
) -> dict[str, BindingField]:
    fields: dict[str, BindingField] = {}
    bindings_section = sidecar.get("bindings", {})
    for name in sorted(set(placeholder_names) | set(bindings_section.keys())):
        config = bindings_section.get(name, {})
        fields[name] = BindingField(
            name=name,
            label=str(config.get("label", humanize_name(name))),
            help=str(config.get("help", "")),
            widget=str(config.get("widget", "text")),
            source_category=str(config.get("source_category", "user-input")),
        )
    return fields


def humanize_name(name: str) -> str:
    return name.replace("_", " ").title()


def load_palette(sidecar: dict[str, Any]) -> dict[str, PaletteEntry]:
    palette = sidecar.get("provenance_palette", {})
    return {
        name: PaletteEntry(
            label=str(config["label"]),
            fill=str(config["fill"]),
            ink=str(config["ink"]),
            accent=str(config["accent"]),
        )
        for name, config in palette.items()
    }


def load_sample_inputs(repo_root: Path, sidecar: dict[str, Any]) -> list[SampleInput]:
    samples: list[SampleInput] = []
    for entry in sidecar.get("sample_inputs", []):
        path = repo_root / str(entry["path"])
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ExplorerError(f"Could not read sample input: {path}") from exc
        samples.append(
            SampleInput(
                id=str(raw.get("id", entry["id"])),
                label=str(raw.get("label", entry["label"])),
                description=str(raw.get("description", "")),
                selected_gate_id=str(raw.get("selected_gate_id", "testing-strategy")),
                selected_outcome_id=optional_string(raw.get("selected_outcome_id")),
                selected_prompt_source_id=optional_string(
                    raw.get("selected_prompt_source_id")
                ),
                bindings=normalize_bindings(raw.get("bindings", {})),
            )
        )
    return samples


def normalize_bindings(raw_bindings: dict[str, Any]) -> dict[str, str]:
    bindings: dict[str, str] = {}
    for name, value in raw_bindings.items():
        if isinstance(value, str):
            bindings[str(name)] = value
            continue
        bindings[str(name)] = json.dumps(value, indent=2, ensure_ascii=False)
    return bindings


def optional_string(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def validate_outcomes(gates: list[Gate], gate_ids: set[str]) -> None:
    for gate in gates:
        for outcome in gate.outcomes:
            if outcome.to_gate_id not in gate_ids:
                raise ExplorerError(
                    f"sidecar outcome {gate.id}:{outcome.id} points to unknown gate "
                    f"{outcome.to_gate_id}"
                )


def validate_sidecar_outcomes(sidecar: dict[str, Any], gate_ids: set[str]) -> None:
    for entry in sidecar.get("outcomes", []):
        from_gate = str(entry.get("from"))
        to_gate = str(entry.get("to"))
        outcome_id = str(entry.get("id"))
        if from_gate not in gate_ids:
            raise ExplorerError(
                f"sidecar outcome {from_gate}:{outcome_id} points from unknown gate"
            )
        if to_gate not in gate_ids:
            raise ExplorerError(
                f"sidecar outcome {from_gate}:{outcome_id} points to unknown gate "
                f"{to_gate}"
            )


def validate_samples(samples: list[SampleInput], gates_by_id: dict[str, Gate]) -> None:
    seen_ids: set[str] = set()
    for sample in samples:
        if sample.id in seen_ids:
            raise ExplorerError(f"Duplicate sample input id: {sample.id}")
        seen_ids.add(sample.id)
        gate = gates_by_id.get(sample.selected_gate_id)
        if gate is None:
            raise ExplorerError(
                f"sample input {sample.id} points to unknown gate {sample.selected_gate_id}"
            )
        if sample.selected_prompt_source_id and not any(
            prompt.id == sample.selected_prompt_source_id for prompt in gate.prompts
        ):
            raise ExplorerError(
                "sample input "
                f"{sample.id} points to unknown prompt source "
                f"{sample.selected_prompt_source_id}"
            )


def select_sample(model: ExplorerModel, sample_id: str | None) -> ExplorerModel:
    if sample_id is None:
        return model

    matches = [sample for sample in model.sample_inputs if sample.id == sample_id]
    if not matches:
        raise ExplorerError(f"Unknown sample id: {sample_id}")
    return replace(model, sample_inputs=matches)
