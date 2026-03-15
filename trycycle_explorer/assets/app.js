const PLACEHOLDER_RE = /\{([A-Z][A-Z0-9_]*)\}/g;
const TAG_NAME_RE = /^[a-z][a-z0-9_-]*$/;

const state = {
  model: null,
  bindings: {},
  selectedSampleId: null,
  selectedGateId: null,
  selectedOutcomeId: null,
  selectedPromptSourceId: null,
  selectedPromptView: "preview",
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

  wireInputs();
  renderLegend();
  renderSamples();
  renderFlow();

  const initialSample = state.model.sample_inputs[0];
  if (initialSample) {
    applySample(initialSample.id);
    return;
  }

  state.selectedGateId = state.model.gates[0]?.id ?? null;
  renderBindingFields();
  rerender();
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
  document
    .getElementById("prompt-view-tabs")
    .addEventListener("click", handlePromptViewClick);
  document
    .getElementById("expand-prompt-view")
    .addEventListener("click", openPromptViewModal);
  document
    .getElementById("expand-diff-panel")
    .addEventListener("click", openDiffModal);
  wireModal();
}

function wireModal() {
  document
    .getElementById("modal-shell")
    .addEventListener("click", handleModalShellClick);
  document.getElementById("modal-close").addEventListener("click", closeModal);
  document.addEventListener("keydown", handleDocumentKeydown);
}

function handleModalShellClick(event) {
  if (event.target.dataset.modalClose === "backdrop") {
    closeModal();
  }
}

function handleDocumentKeydown(event) {
  if (event.key === "Escape" && isModalOpen()) {
    closeModal();
  }
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

function handlePromptViewClick(event) {
  const viewButton = event.target.closest("[data-prompt-view]");
  if (!viewButton) {
    return;
  }
  state.selectedPromptView = viewButton.dataset.promptView;
  renderActivePromptView();
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
  closeModal();
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
    const field = document.createElement("div");
    field.className = "field";

    const controlId = makeBindingControlId(name);
    const header = document.createElement("div");
    header.className = "field-header";

    const label = document.createElement("label");
    label.className = "field-label";
    label.htmlFor = controlId;
    label.textContent = config.label;
    header.append(label);
    header.append(
      createExpandButton(`Expand ${config.label}`, () =>
        openBindingModal(name, config),
      ),
    );
    field.append(header);

    const control =
      config.widget === "textarea"
        ? document.createElement("textarea")
        : document.createElement("input");
    control.id = controlId;
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
  closeModal();
  renderFlow();

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
  renderPromptPanel(gate, promptSource, state.currentSnapshot);
  renderDiagnostics(state.currentSnapshot.diagnostics);
  renderPromptDiagnosticSummary(state.currentSnapshot.diagnostics);
  renderDiffPanel(state.previousSnapshot, state.currentSnapshot);
}

function renderFlow() {
  renderCopyBlock("flow-intro", {
    title: "Intro",
    markdown: state.model?.intro_markdown ?? "",
    emptyMessage: "No copy appears before step 1 in the current SKILL.md.",
  });

  const container = document.getElementById("flow-groups");
  container.innerHTML = "";

  for (const group of state.model?.groups ?? []) {
    const section = document.createElement("section");
    section.className = "flow-group";

    const heading = document.createElement("div");
    heading.className = "flow-group-header";
    heading.innerHTML = `<h3>${escapeHtml(group.label)}</h3>`;
    section.append(heading);

    for (const gateId of group.gates) {
      const gate = getGate(gateId);
      if (!gate) {
        continue;
      }

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
          const destinationGate = getGate(outcome.to_gate_id);
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
              destinationGate?.title ?? outcome.to_gate_id,
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

  renderCopyBlock("flow-outro", {
    title: "Outro",
    markdown: state.model?.outro_markdown ?? "",
    emptyMessage:
      "No trailing copy appears after the last numbered step in the current SKILL.md.",
  });
}

function renderCopyBlock(containerId, { title, markdown, emptyMessage }) {
  const container = document.getElementById(containerId);
  container.innerHTML = "";

  const heading = document.createElement("div");
  heading.className = "section-heading";

  const titleNode = document.createElement("h3");
  titleNode.textContent = title;
  heading.append(titleNode);

  if (markdown.trim()) {
    heading.append(
      createExpandButton(`Expand ${title}`, () =>
        openMarkdownModal({
          eyebrow: "Flow copy",
          title,
          description:
            title === "Intro"
              ? "Everything in SKILL.md before step 1."
              : "Everything in SKILL.md after the numbered flow.",
          markdown,
          className: "copy-body modal-copy",
        }),
      ),
    );
  }

  container.append(heading);

  const body = document.createElement("div");
  body.className = "copy-body";
  if (markdown.trim()) {
    body.innerHTML = renderMarkdown(markdown);
  } else {
    const empty = document.createElement("p");
    empty.className = "copy-empty";
    empty.textContent = emptyMessage;
    body.append(empty);
  }
  container.append(body);
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
  renderPromptInterface(promptSource);
  renderActivePromptView();
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
    item.dataset.severity = diagnostic.severity;
    item.dataset.code = diagnostic.code;
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
    item.dataset.severity = diagnostic.severity;
    item.dataset.code = diagnostic.code;
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

  if (!currentSnapshot) {
    summary.textContent =
      "Choose a gate to inspect how the current render changes over time.";
    document.getElementById("expand-diff-panel").disabled = true;
    return;
  }

  if (!previousSnapshot) {
    summary.textContent =
      "Rerender after changing an input or outcome to see the delta.";
    const empty = document.createElement("p");
    empty.className = "diff-empty";
    empty.textContent = "No previous render yet.";
    panel.append(empty);
    document.getElementById("expand-diff-panel").disabled = false;
    return;
  }

  const diff = diffLines(
    previousSnapshot.prompt_markdown,
    currentSnapshot.prompt_markdown,
  );
  const added = diff.filter((entry) => entry.type === "added").length;
  const removed = diff.filter((entry) => entry.type === "removed").length;
  summary.textContent = `Added ${added} lines, removed ${removed} lines.`;
  renderDiffEntries(panel, diff);
  document.getElementById("expand-diff-panel").disabled = false;
}

function renderPromptSource(promptSource, bindings, bindingFields, outcomeId) {
  if (promptSource.render_mode !== "template") {
    return {
      outcome_id: outcomeId,
      prompt_markdown: promptSource.source_markdown,
      segments: [
        {
          text: promptSource.source_markdown,
          category: "template-text",
          source_kind: promptSource.source_kind,
        },
      ],
      diagnostics: [],
    };
  }

  const segments = [];
  const diagnostics = [];
  const nodes = promptSource.template_ast ?? [
    { type: "text", text: promptSource.source_markdown },
  ];
  renderNodes(nodes, bindings, bindingFields, promptSource, segments, diagnostics);
  const promptMarkdown = segments.map((segment) => segment.text).join("");
  diagnostics.push(...validateRequiredTags(promptSource, promptMarkdown));
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

function renderPromptInterface(promptSource) {
  const container = document.getElementById("prompt-interface");
  container.innerHTML = "";

  for (const tag of promptSource.required_nonempty_tags ?? []) {
    container.append(
      createPromptPill(`Requires <${tag}>`, `Builder requires a non-empty <${tag}> block.`),
    );
  }

  for (const tag of promptSource.ignore_tags_for_placeholders ?? []) {
    container.append(
      createPromptPill(
        `Ignore placeholders in <${tag}>`,
        `Builder ignores placeholder-like text inside <${tag}> when scanning the rendered prompt.`,
      ),
    );
  }
}

function createPromptPill(label, title) {
  const pill = document.createElement("span");
  pill.className = "pill pill-interface";
  pill.title = title;
  pill.textContent = label;
  return pill;
}

function validateRequiredTags(promptSource, promptMarkdown) {
  const diagnostics = [];
  for (const tag of promptSource.required_nonempty_tags ?? []) {
    if (!TAG_NAME_RE.test(tag)) {
      continue;
    }
    const pattern = new RegExp(`<${escapeRegex(tag)}>([\\s\\S]*?)</${escapeRegex(tag)}>`);
    const match = pattern.exec(promptMarkdown);
    if (!match) {
      diagnostics.push({
        severity: "error",
        code: "missing-required-tag",
        message: `Rendered prompt is missing required <${tag}> block.`,
        prompt_source_id: promptSource.id,
      });
      continue;
    }
    if (!match[1].trim()) {
      diagnostics.push({
        severity: "error",
        code: "empty-required-tag",
        message: `Rendered prompt has empty <${tag}> block.`,
        prompt_source_id: promptSource.id,
      });
    }
  }
  return diagnostics;
}

function openBindingModal(bindingName, config) {
  openModal({
    eyebrow: "Input binding",
    title: config.label,
    description:
      config.help || "Edit the full value in a large textarea. Changes sync immediately.",
    renderBody(modalBody) {
      const textarea = document.createElement("textarea");
      textarea.className = "modal-textarea";
      textarea.dataset.modalPrimaryFocus = "true";
      textarea.value = state.bindings[bindingName] ?? "";
      textarea.addEventListener("input", () => {
        state.bindings[bindingName] = textarea.value;
        const control = document.getElementById(makeBindingControlId(bindingName));
        if (control) {
          control.value = textarea.value;
        }
      });
      modalBody.append(textarea);
      textarea.focus();
      textarea.selectionStart = textarea.value.length;
      textarea.selectionEnd = textarea.value.length;
    },
  });
}

function openPromptPreviewModal() {
  if (!state.currentSnapshot || !state.selectedGateId) {
    return;
  }
  const gate = getGate(state.selectedGateId);
  openRenderedMarkdownModal({
    eyebrow: "Rendered prompt",
    title: `${gate.title} preview`,
    description: "Markdown rendered from the currently selected prompt source.",
    markdown: state.currentSnapshot.prompt_markdown,
    className: "prompt-preview modal-markdown",
  });
}

function openPromptSourceModal() {
  if (!state.currentSnapshot || !state.selectedGateId) {
    return;
  }
  const gate = getGate(state.selectedGateId);
  const promptSource = getPromptSource(gate, state.selectedPromptSourceId);
  openModal({
    eyebrow: "Markdown source",
    title: `${gate.title} source`,
    description: `${promptSource.label} · ${promptSource.source_path}`,
    renderBody(modalBody) {
      const source = document.createElement("pre");
      source.className = "prompt-source modal-source";
      renderPromptSourceSegments(source, state.currentSnapshot.segments);
      modalBody.append(source);
    },
  });
}

function openPromptViewModal() {
  if (state.selectedPromptView === "source") {
    openPromptSourceModal();
    return;
  }
  openPromptPreviewModal();
}

function openDiffModal() {
  if (!state.currentSnapshot || !state.selectedGateId) {
    return;
  }
  const gate = getGate(state.selectedGateId);
  openModal({
    eyebrow: "Before / after",
    title: `${gate.title} diff`,
    description: document.getElementById("diff-summary").textContent,
    renderBody(modalBody) {
      const panel = document.createElement("div");
      panel.className = "diff-panel modal-diff";
      if (!state.previousSnapshot) {
        const empty = document.createElement("p");
        empty.className = "diff-empty";
        empty.textContent = "No previous render yet.";
        panel.append(empty);
      } else {
        const diff = diffLines(
          state.previousSnapshot.prompt_markdown,
          state.currentSnapshot.prompt_markdown,
        );
        renderDiffEntries(panel, diff);
      }
      modalBody.append(panel);
    },
  });
}

function openMarkdownModal({ eyebrow, title, description, markdown, className }) {
  openModal({
    eyebrow,
    title,
    description,
    renderBody(modalBody) {
      const container = document.createElement("div");
      container.className = className;
      container.innerHTML = renderMarkdown(markdown);
      modalBody.append(container);
    },
  });
}

function openRenderedMarkdownModal({ eyebrow, title, description, markdown, className }) {
  openModal({
    eyebrow,
    title,
    description,
    renderBody(modalBody) {
      const container = document.createElement("div");
      container.className = className;
      container.innerHTML = renderPromptPreview(markdown);
      modalBody.append(container);
    },
  });
}

function openModal({ eyebrow, title, description, renderBody }) {
  closeModal();

  const shell = document.getElementById("modal-shell");
  const eyebrowNode = document.getElementById("modal-eyebrow");
  const titleNode = document.getElementById("modal-title");
  const descriptionNode = document.getElementById("modal-description");
  const modalBody = document.getElementById("modal-body");

  titleNode.textContent = title;
  eyebrowNode.textContent = eyebrow || "";
  eyebrowNode.hidden = !eyebrow;
  descriptionNode.textContent = description || "";
  descriptionNode.hidden = !description;
  modalBody.innerHTML = "";
  renderBody(modalBody);

  shell.hidden = false;
  document.body.classList.add("modal-open");
  const focusTarget =
    modalBody.querySelector("[data-modal-primary-focus]") ??
    document.getElementById("modal-close");
  focusTarget.focus();
}

function closeModal() {
  const shell = document.getElementById("modal-shell");
  if (!shell || shell.hidden) {
    return;
  }
  shell.hidden = true;
  document.getElementById("modal-body").innerHTML = "";
  document.body.classList.remove("modal-open");
}

function isModalOpen() {
  const shell = document.getElementById("modal-shell");
  return Boolean(shell && !shell.hidden);
}

function renderPromptSourceSegments(container, segments) {
  container.innerHTML = "";
  for (const segment of segments) {
    const span = document.createElement("span");
    span.className = `segment segment-${segment.category}`;
    if (segment.binding_name) {
      span.dataset.bindingName = segment.binding_name;
    }
    span.textContent = segment.text;
    container.append(span);
  }
}

function renderDiffEntries(container, diffEntries) {
  container.innerHTML = "";
  for (const entry of diffEntries) {
    const line = document.createElement("div");
    line.className = `diff-line diff-${entry.type}`;
    line.innerHTML = `
      <span class="diff-marker">${diffMarker(entry.type)}</span>
      <code>${escapeHtml(entry.text || " ")}</code>
    `;
    container.append(line);
  }
}

function renderMarkdown(markdown) {
  if (window.MarkdownLite) {
    return window.MarkdownLite.render(markdown);
  }
  return `<pre>${escapeHtml(markdown)}</pre>`;
}

function renderPromptPreview(markdown) {
  const lines = String(markdown).replace(/\r\n/g, "\n").split("\n");
  const html = [];
  let chunk = [];

  function flushChunk() {
    const block = chunk.join("\n");
    if (block.trim()) {
      html.push(renderMarkdown(block));
    }
    chunk = [];
  }

  for (let index = 0; index < lines.length; index += 1) {
    const openMatch = lines[index].trim().match(/^<([a-z][a-z0-9_-]*)>$/);
    if (!openMatch) {
      chunk.push(lines[index]);
      continue;
    }

    const tag = openMatch[1];
    const closeLine = `</${tag}>`;
    let closeIndex = index + 1;
    while (closeIndex < lines.length && lines[closeIndex].trim() !== closeLine) {
      closeIndex += 1;
    }

    if (closeIndex >= lines.length) {
      chunk.push(lines[index]);
      continue;
    }

    flushChunk();
    html.push(
      renderTaggedBlock(tag, lines.slice(index + 1, closeIndex).join("\n")),
    );
    index = closeIndex;
  }

  flushChunk();
  return html.join("\n");
}

function renderTaggedBlock(tag, body) {
  const trimmed = body.trim();
  if (!trimmed) {
    return `
      <section class="prompt-tag-block">
        <div class="prompt-tag-label">&lt;${escapeHtml(tag)}&gt;</div>
        <div class="prompt-tag-empty">Empty</div>
        <div class="prompt-tag-label">&lt;/${escapeHtml(tag)}&gt;</div>
      </section>
    `;
  }

  return `
    <section class="prompt-tag-block">
      <div class="prompt-tag-label">&lt;${escapeHtml(tag)}&gt;</div>
      <pre><code>${escapeHtml(formatPromptBlockBody(trimmed))}</code></pre>
      <div class="prompt-tag-label">&lt;/${escapeHtml(tag)}&gt;</div>
    </section>
  `;
}

function formatPromptBlockBody(body) {
  const trimmed = String(body).trim();
  if (!/^[\[{]/.test(trimmed)) {
    return body;
  }

  try {
    return JSON.stringify(JSON.parse(trimmed), null, 2);
  } catch {
    return body;
  }
}

function renderActivePromptView() {
  const previewButton = document.querySelector('[data-prompt-view="preview"]');
  const sourceButton = document.querySelector('[data-prompt-view="source"]');
  const preview = document.getElementById("prompt-preview");
  const source = document.getElementById("prompt-source");
  const expandButton = document.getElementById("expand-prompt-view");
  const isSource = state.selectedPromptView === "source";

  previewButton?.classList.toggle("selected", !isSource);
  previewButton?.setAttribute("aria-pressed", String(!isSource));
  sourceButton?.classList.toggle("selected", isSource);
  sourceButton?.setAttribute("aria-pressed", String(isSource));

  if (!state.currentSnapshot) {
    preview.innerHTML = "";
    source.innerHTML = "";
    preview.hidden = false;
    source.hidden = true;
    expandButton.disabled = true;
    return;
  }

  preview.innerHTML = renderPromptPreview(state.currentSnapshot.prompt_markdown);
  renderPromptSourceSegments(source, state.currentSnapshot.segments);

  preview.hidden = isSource;
  source.hidden = !isSource;
  expandButton.disabled = isSource
    ? !state.currentSnapshot.segments.length
    : !state.currentSnapshot.prompt_markdown.trim();
}

function createExpandButton(ariaLabel, onClick) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "expand-button";
  button.textContent = "Expand";
  button.setAttribute("aria-label", ariaLabel);
  button.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    onClick();
  });
  return button;
}

function makeBindingControlId(name) {
  return `binding-${String(name).toLowerCase().replace(/[^a-z0-9_-]+/g, "-")}`;
}

function escapeRegex(text) {
  return String(text).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function getGate(gateId) {
  return state.model?.gates.find((gate) => gate.id === gateId);
}

function getPromptSource(gate, promptSourceId) {
  const targetId = promptSourceId || gate.default_prompt_source_id;
  return gate.prompts.find((prompt) => prompt.id === targetId) ?? gate.prompts[0];
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
