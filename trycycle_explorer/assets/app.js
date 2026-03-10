const PLACEHOLDER_RE = /\{([A-Z][A-Z0-9_]*)\}/g;
const state = {
  model: null,
  bindings: {},
  selectedSampleId: null,
  selectedGateId: null,
  selectedOutcomeId: null,
  selectedPromptSourceId: null,
  previousSnapshot: null,
  currentSnapshot: null,
};

document.addEventListener("DOMContentLoaded", () => {
  void bootstrap();
});

async function bootstrap() {
  const response = await fetch("./explorer-model.json");
  state.model = await response.json();
  document.getElementById("page-title").textContent = state.model.display.title;
  document.getElementById("page-subtitle").textContent =
    state.model.display.subtitle;

  renderLegend();
  renderSamples();
  wireInputs();

  const initialSample = state.model.sample_inputs[0];
  if (initialSample) {
    applySample(initialSample.id);
  } else {
    rerender();
  }
}

function wireInputs() {
  document
    .getElementById("sample-select")
    .addEventListener("change", (event) => applySample(event.target.value));
  document
    .getElementById("rerender")
    .addEventListener("click", () => rerender());
  document
    .getElementById("flow-groups")
    .addEventListener("click", handleFlowClick);
  document
    .getElementById("prompt-source-tabs")
    .addEventListener("click", handlePromptTabClick);
}

function handleFlowClick(event) {
  const gateButton = event.target.closest("[data-gate-id]");
  if (gateButton) {
    state.selectedGateId = gateButton.dataset.gateId;
    state.selectedOutcomeId = null;
    state.selectedPromptSourceId = null;
    rerender();
    return;
  }

  const outcomeButton = event.target.closest("[data-outcome-id]");
  if (outcomeButton) {
    state.selectedOutcomeId = outcomeButton.dataset.outcomeId;
    rerender();
  }
}

function handlePromptTabClick(event) {
  const tabButton = event.target.closest("[data-prompt-source-id]");
  if (!tabButton) {
    return;
  }
  state.selectedPromptSourceId = tabButton.dataset.promptSourceId;
  rerender();
}

function renderSamples() {
  const select = document.getElementById("sample-select");
  select.innerHTML = "";
  for (const sample of state.model.sample_inputs) {
    const option = document.createElement("option");
    option.value = sample.id;
    option.textContent = sample.label;
    select.append(option);
  }
}

function applySample(sampleId) {
  const sample = state.model.sample_inputs.find((entry) => entry.id === sampleId);
  if (!sample) {
    return;
  }
  state.selectedSampleId = sample.id;
  state.bindings = structuredClone(sample.bindings);
  state.selectedGateId = sample.selected_gate_id;
  state.selectedOutcomeId = sample.selected_outcome_id;
  state.selectedPromptSourceId = sample.selected_prompt_source_id;
  state.previousSnapshot = null;
  state.currentSnapshot = null;
  document.getElementById("sample-select").value = sample.id;
  renderBindingFields();
  rerender();
}

function renderBindingFields() {
  const fields = document.getElementById("binding-fields");
  fields.innerHTML = "";

  for (const [name, config] of Object.entries(state.model.bindings)) {
    const field = document.createElement("label");
    field.className = "field";

    const label = document.createElement("span");
    label.textContent = config.label;
    field.append(label);

    const control =
      config.widget === "textarea"
        ? document.createElement("textarea")
        : document.createElement("input");
    control.name = name;
    control.value = state.bindings[name] ?? "";
    if (control.tagName === "INPUT") {
      control.type = "text";
    }
    control.addEventListener("input", () => {
      state.bindings[name] = control.value;
    });
    field.append(control);

    if (config.help) {
      const help = document.createElement("small");
      help.textContent = config.help;
      field.append(help);
    }

    fields.append(field);
  }
}

function rerender() {
  if (!state.model || !state.selectedGateId) {
    return;
  }

  const gate = getGate(state.selectedGateId);
  const promptSource = getPromptSource(gate, state.selectedPromptSourceId);
  state.previousSnapshot = state.currentSnapshot;
  state.currentSnapshot = renderPromptSource(
    promptSource,
    state.bindings,
    state.model.bindings,
    state.selectedOutcomeId,
  );
  renderFlow();
  renderPromptPanel(gate, promptSource, state.currentSnapshot);
  renderDiagnostics(state.currentSnapshot.diagnostics);
  renderPromptDiagnosticSummary(state.currentSnapshot.diagnostics);
  renderDiffPanel(state.previousSnapshot, state.currentSnapshot);
}

function renderFlow() {
  const container = document.getElementById("flow-groups");
  container.innerHTML = "";

  for (const group of state.model.groups) {
    const section = document.createElement("section");
    section.className = "flow-group";

    const heading = document.createElement("div");
    heading.className = "flow-group-header";
    heading.innerHTML = `<h3>${escapeHtml(group.label)}</h3>`;
    section.append(heading);

    for (const gateId of group.gates) {
      const gate = getGate(gateId);
      const card = document.createElement("article");
      card.className = "gate-card";
      if (gate.id === state.selectedGateId) {
        card.classList.add("selected");
      }

      const button = document.createElement("button");
      button.type = "button";
      button.className = "gate-button";
      button.dataset.gateId = gate.id;
      button.innerHTML = `
        <span class="gate-step">Step ${gate.step_number}</span>
        <strong>${escapeHtml(gate.title)}</strong>
        <span class="gate-summary">${escapeHtml(gate.summary)}</span>
      `;
      card.append(button);

      if (gate.id === state.selectedGateId && gate.outcomes.length) {
        const outcomeList = document.createElement("div");
        outcomeList.className = "outcome-list";
        for (const outcome of gate.outcomes) {
          const outcomeButton = document.createElement("button");
          outcomeButton.type = "button";
          outcomeButton.className = "outcome-button";
          outcomeButton.dataset.outcomeId = outcome.id;
          if (outcome.id === state.selectedOutcomeId) {
            outcomeButton.classList.add("selected");
          }
          outcomeButton.innerHTML = `
            <span>${escapeHtml(outcome.label)}</span>
            <span class="outcome-arrow">→ ${escapeHtml(
              getGate(outcome.to_gate_id).title,
            )}</span>
          `;
          outcomeList.append(outcomeButton);
        }
        card.append(outcomeList);
      }

      section.append(card);
    }

    container.append(section);
  }
}

function renderPromptPanel(gate, promptSource, snapshot) {
  document.getElementById("prompt-title").textContent = gate.title;
  document.getElementById("prompt-subtitle").textContent =
    `${promptSource.label} · ${promptSource.source_path}`;

  const selectedOutcome = document.getElementById("selected-outcome");
  const outcome = gate.outcomes.find((entry) => entry.id === state.selectedOutcomeId);
  selectedOutcome.textContent = outcome
    ? `Outcome: ${outcome.label}`
    : "Outcome: not selected";

  renderPromptTabs(gate);

  const preview = document.getElementById("prompt-preview");
  preview.innerHTML = window.MarkdownLite
    ? window.MarkdownLite.render(snapshot.prompt_markdown)
    : `<pre>${escapeHtml(snapshot.prompt_markdown)}</pre>`;

  const source = document.getElementById("prompt-source");
  source.innerHTML = "";
  for (const segment of snapshot.segments) {
    const span = document.createElement("span");
    span.className = `segment segment-${segment.category}`;
    if (segment.binding_name) {
      span.dataset.bindingName = segment.binding_name;
    }
    span.textContent = segment.text;
    source.append(span);
  }
}

function renderPromptTabs(gate) {
  const container = document.getElementById("prompt-source-tabs");
  container.innerHTML = "";
  for (const prompt of gate.prompts) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "tab-button";
    button.dataset.promptSourceId = prompt.id;
    if (prompt.id === getPromptSource(gate, state.selectedPromptSourceId).id) {
      button.classList.add("selected");
    }
    button.textContent = prompt.label;
    container.append(button);
  }
}

function renderLegend() {
  const legend = document.getElementById("legend");
  legend.innerHTML = "";
  for (const [name, entry] of Object.entries(state.model?.provenance_palette ?? {})) {
    const item = document.createElement("div");
    item.className = "legend-item";
    item.innerHTML = `
      <span class="legend-swatch" style="--legend-fill:${entry.fill};--legend-accent:${entry.accent};"></span>
      <span>${escapeHtml(entry.label)}</span>
      <code>${escapeHtml(name)}</code>
    `;
    legend.append(item);
  }
}

function renderDiagnostics(diagnostics) {
  const container = document.getElementById("diagnostics");
  container.innerHTML = "";

  if (!diagnostics.length) {
    const clean = document.createElement("p");
    clean.className = "diagnostic-empty";
    clean.textContent = "No diagnostics for the current render.";
    container.append(clean);
    return;
  }

  for (const diagnostic of diagnostics) {
    const item = document.createElement("article");
    item.className = "diagnostic-item";
    item.dataset.severity = diagnostic.code;
    item.innerHTML = `
      <strong>${escapeHtml(diagnostic.code)}</strong>
      <p>${escapeHtml(diagnostic.message)}</p>
    `;
    container.append(item);
  }
}

function renderPromptDiagnosticSummary(diagnostics) {
  const container = document.getElementById("prompt-diagnostic-summary");
  container.innerHTML = "";
  if (!diagnostics.length) {
    return;
  }

  for (const diagnostic of diagnostics.slice(0, 3)) {
    const item = document.createElement("article");
    item.className = "prompt-diagnostic-item";
    item.innerHTML = `
      <strong>${escapeHtml(diagnostic.code)}</strong>
      <p>${escapeHtml(diagnostic.message)}</p>
    `;
    container.append(item);
  }
}

function renderDiffPanel(previousSnapshot, currentSnapshot) {
  const panel = document.getElementById("diff-panel");
  const summary = document.getElementById("diff-summary");
  panel.innerHTML = "";

  if (!previousSnapshot) {
    summary.textContent =
      "Rerender after changing an input or outcome to see the delta.";
    const empty = document.createElement("p");
    empty.className = "diff-empty";
    empty.textContent = "No previous render yet.";
    panel.append(empty);
    return;
  }

  const diff = diffLines(
    previousSnapshot.prompt_markdown,
    currentSnapshot.prompt_markdown,
  );
  const added = diff.filter((entry) => entry.type === "added").length;
  const removed = diff.filter((entry) => entry.type === "removed").length;
  summary.textContent = `Added ${added} lines, removed ${removed} lines.`;

  for (const entry of diff) {
    const line = document.createElement("div");
    line.className = `diff-line diff-${entry.type}`;
    line.innerHTML = `
      <span class="diff-marker">${diffMarker(entry.type)}</span>
      <code>${escapeHtml(entry.text || " ")}</code>
    `;
    panel.append(line);
  }
}

function renderPromptSource(promptSource, bindings, bindingFields, outcomeId) {
  const segments = [];
  const diagnostics = [];
  const nodes = promptSource.template_ast ?? [
    { type: "text", text: promptSource.source_markdown },
  ];
  renderNodes(nodes, bindings, bindingFields, promptSource, segments, diagnostics);
  const promptMarkdown = segments.map((segment) => segment.text).join("");
  return {
    outcome_id: outcomeId,
    prompt_markdown: promptMarkdown,
    segments,
    diagnostics,
  };
}

function renderNodes(nodes, bindings, bindingFields, promptSource, segments, diagnostics) {
  for (const node of nodes) {
    if (node.type === "text") {
      renderTextNode(
        node.text,
        bindings,
        bindingFields,
        promptSource,
        segments,
        diagnostics,
      );
      continue;
    }

    const conditionalValue = bindings[node.name] ?? "";
    if (!conditionalValue) {
      diagnostics.push({
        severity: "warning",
        code: "missing-binding",
        message: `Conditional binding ${node.name} is missing or empty.`,
        prompt_source_id: promptSource.id,
        binding_name: node.name,
      });
    }
    const branch = conditionalValue ? node.truthy : node.falsy;
    renderNodes(branch, bindings, bindingFields, promptSource, segments, diagnostics);
  }
}

function renderTextNode(
  text,
  bindings,
  bindingFields,
  promptSource,
  segments,
  diagnostics,
) {
  PLACEHOLDER_RE.lastIndex = 0;
  let cursor = 0;
  for (const match of text.matchAll(PLACEHOLDER_RE)) {
    const start = match.index ?? 0;
    if (start > cursor) {
      segments.push({
        text: text.slice(cursor, start),
        category: "template-text",
        source_kind: promptSource.source_kind,
      });
    }

    const name = match[1];
    const bindingValue = bindings[name];
    if (
      Object.hasOwn(bindings, name) &&
      typeof bindingValue === "string" &&
      bindingValue.trim()
    ) {
      segments.push({
        text: bindingValue,
        category: bindingFields[name]?.source_category ?? "user-input",
        source_kind: promptSource.source_kind,
        binding_name: name,
      });
    } else {
      diagnostics.push({
        severity: "warning",
        code: "missing-binding",
        message: `Missing placeholder value for ${name}.`,
        prompt_source_id: promptSource.id,
        binding_name: name,
      });
      segments.push({
        text: `<<MISSING:${name}>>`,
        category: "missing-binding",
        source_kind: promptSource.source_kind,
        binding_name: name,
      });
    }
    cursor = start + match[0].length;
  }

  if (cursor < text.length) {
    segments.push({
      text: text.slice(cursor),
      category: "template-text",
      source_kind: promptSource.source_kind,
    });
  }
}

function getGate(gateId) {
  return state.model.gates.find((gate) => gate.id === gateId);
}

function getPromptSource(gate, promptSourceId) {
  const targetId = promptSourceId || gate.default_prompt_source_id;
  return (
    gate.prompts.find((prompt) => prompt.id === targetId) ??
    gate.prompts[0]
  );
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function diffMarker(type) {
  if (type === "added") {
    return "+";
  }
  if (type === "removed") {
    return "−";
  }
  return "·";
}

function diffLines(previousText, currentText) {
  const before = String(previousText).split("\n");
  const after = String(currentText).split("\n");
  const rows = before.length + 1;
  const cols = after.length + 1;
  const table = Array.from({ length: rows }, () => Array(cols).fill(0));

  for (let row = before.length - 1; row >= 0; row -= 1) {
    for (let col = after.length - 1; col >= 0; col -= 1) {
      if (before[row] === after[col]) {
        table[row][col] = table[row + 1][col + 1] + 1;
      } else {
        table[row][col] = Math.max(table[row + 1][col], table[row][col + 1]);
      }
    }
  }

  const diff = [];
  let row = 0;
  let col = 0;
  while (row < before.length && col < after.length) {
    if (before[row] === after[col]) {
      diff.push({ type: "context", text: before[row] });
      row += 1;
      col += 1;
      continue;
    }
    if (table[row + 1][col] >= table[row][col + 1]) {
      diff.push({ type: "removed", text: before[row] });
      row += 1;
      continue;
    }
    diff.push({ type: "added", text: after[col] });
    col += 1;
  }

  while (row < before.length) {
    diff.push({ type: "removed", text: before[row] });
    row += 1;
  }

  while (col < after.length) {
    diff.push({ type: "added", text: after[col] });
    col += 1;
  }

  return diff;
}
