# Trycycle Explorer Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use trycycle-executing to implement this plan task-by-task.

**Goal:** Build a Python-first static-site generator that turns the real trycycle repo into a navigable explorer: users can pick a sample or enter custom bindings, click gates and outcomes, view the exact rendered prompt markdown for the active path, see provenance and diagnostics, rerender locally, and compare the new result without any LLM or backend integration.

**Architecture:** Treat `docs/trycycle-information-flow.dot` as the canonical graph topology, the prompt templates in `subagents/*.md` as the canonical prompt text, and `SKILL.md` as the canonical dispatch semantics. Keep only the non-derivable pieces in a root sidecar, `.trycycle-explorer.toml`: prompt-variant recipes per DOT node, outcome labels where DOT prose is too thin, binding-field metadata, palette metadata, and sample scenarios. Refactor the existing prompt builder into a shared AST and render-trace module so the explorer can rerender prompts in-browser from serialized template structure, preserving trycycle’s real placeholder/conditional semantics while emitting provenance segments and missing-binding diagnostics.

**Tech Stack:** Python 3.12 standard library, TOML, existing `orchestrator/prompt_builder` logic factored into shared AST/trace helpers, vanilla HTML/CSS/ES modules, vendored browser markdown renderer, disposable verification scripts under `/tmp`, `python3 -m http.server`, Playwright CLI

---

### Task 1: Refactor the prompt builder into a reusable AST and render-trace library

**Files:**
- Create: `orchestrator/prompt_builder/template_ast.py`
- Modify: `orchestrator/prompt_builder/build.py`

**Why this task exists:** The explorer cannot be trustworthy if it invents a second prompt-language implementation. The shared module must expose placeholder nodes, conditional nodes, JSON-safe serialization, and render traces so the browser can show what came from template text versus bound values.

**Step 1: Write a failing disposable probe**

Run:

```bash
tmpdir="$(mktemp -d /tmp/trycycle-explorer-ast-XXXXXX)"
cat >"$tmpdir/probe.py" <<'PY'
from orchestrator.prompt_builder.template_ast import parse_template_text, render_with_trace
PY
python3 "$tmpdir/probe.py"
rm -rf "$tmpdir"
```

Expected: the import fails because the shared AST module does not exist yet.

**Step 2: Implement the shared AST and trace helpers**

Create `orchestrator/prompt_builder/template_ast.py` with these core types:

```python
@dataclass(frozen=True)
class TextNode:
    text: str


@dataclass(frozen=True)
class PlaceholderNode:
    name: str


@dataclass(frozen=True)
class IfNode:
    name: str
    truthy: list["Node"]
    falsy: list["Node"]


@dataclass(frozen=True)
class RenderSegment:
    text: str
    category: str
    source_key: str | None
```

Implement these exact behaviors:

- Move tokenization and recursive parsing out of `build.py` into this shared module.
- Split literal text from placeholders so provenance can highlight bound values separately from template prose.
- Add `parse_template_text()`, `render_to_string()`, `render_with_trace()`, and `serialize_nodes()` helpers.
- `render_with_trace()` must return both the final string and ordered `RenderSegment` records tagged at minimum as `template-text`, `binding-value`, and `missing-binding`.
- Missing placeholders must still raise in strict mode for the existing CLI, but the shared render path must also support a non-strict mode that substitutes `<<MISSING:NAME>>` and emits a diagnostic segment. The explorer will use that mode later.
- Keep `orchestrator/prompt_builder/build.py` behavior unchanged for current callers: same CLI flags, same error prefix, same exit behavior.

**Step 3: Verify the refactor**

Run:

```bash
python3 -m py_compile \
  orchestrator/prompt_builder/template_ast.py \
  orchestrator/prompt_builder/build.py

tmpdir="$(mktemp -d /tmp/trycycle-explorer-ast-XXXXXX)"
cat >"$tmpdir/template.md" <<'EOF'
hello {NAME}
{{#if EXTRA}}extra: {EXTRA}{{else}}no extra{{/if}}
EOF
python3 orchestrator/prompt_builder/build.py \
  --template "$tmpdir/template.md" \
  --set NAME=world \
  --set EXTRA=value
python3 - <<'PY' "$tmpdir/template.md"
from pathlib import Path
from orchestrator.prompt_builder.template_ast import parse_template_text, render_with_trace

nodes = parse_template_text(Path(__import__('sys').argv[1]).read_text(encoding='utf-8'))
rendered, trace = render_with_trace(nodes, {"NAME": "world"})
assert "hello world" in rendered
assert any(segment.category == "binding-value" and segment.source_key == "NAME" for segment in trace)
assert any(segment.category == "missing-binding" and segment.source_key == "EXTRA" for segment in trace)
print("trace ok")
PY
rm -rf "$tmpdir"
```

Expected:

- `py_compile` succeeds.
- The existing prompt builder still renders `hello world` and `extra: value`.
- The trace probe prints `trace ok`.

**Step 4: Commit**

```bash
git add orchestrator/prompt_builder/template_ast.py orchestrator/prompt_builder/build.py
git commit -m "feat: share prompt template ast for explorer"
```

### Task 2: Add the explorer package, CLI scaffold, and model types

**Files:**
- Create: `orchestrator/trycycle_explorer/__init__.py`
- Create: `orchestrator/trycycle_explorer/__main__.py`
- Create: `orchestrator/trycycle_explorer/cli.py`
- Create: `orchestrator/trycycle_explorer/model.py`
- Modify: `.gitignore`

**Why this task exists:** The repo is tooling-oriented and already keeps Python helpers under `orchestrator/`. The explorer should follow that shape instead of introducing a new top-level application layout or packaging story.

**Step 1: Write a failing CLI probe**

Run:

```bash
python3 -m orchestrator.trycycle_explorer --help
python3 - <<'PY'
from orchestrator.trycycle_explorer.model import ExplorerModel
PY
```

Expected: both commands fail because the package and model module do not exist yet.

**Step 2: Implement the package scaffold**

Create `orchestrator/trycycle_explorer/model.py` with JSON-oriented dataclasses at least as rich as:

```python
@dataclass(frozen=True)
class GraphNode:
    id: str
    title: str
    cluster: str | None
    prompt_variants: list["PromptVariant"]


@dataclass(frozen=True)
class GraphEdge:
    id: str
    from_node_id: str
    to_node_id: str
    label: str
    style: str


@dataclass(frozen=True)
class PromptVariant:
    id: str
    template_path: str
    binding_order: list[str]
    activate_on_edge_ids: list[str]
```

Implement `orchestrator/trycycle_explorer/cli.py` and `__main__.py` with these commands:

- `python3 -m orchestrator.trycycle_explorer dump-model`
- `python3 -m orchestrator.trycycle_explorer build`

Required CLI behaviors:

- `--repo` defaults to `.`
- `--sidecar` defaults to `.trycycle-explorer.toml`
- `--output` defaults to `build/trycycle-explorer`
- `dump-model` writes canonical JSON
- `build` will later write the static site
- `.gitignore` must ignore `build/trycycle-explorer/`

**Step 3: Verify the scaffold**

Run:

```bash
python3 -m py_compile \
  orchestrator/trycycle_explorer/__init__.py \
  orchestrator/trycycle_explorer/__main__.py \
  orchestrator/trycycle_explorer/cli.py \
  orchestrator/trycycle_explorer/model.py
python3 -m orchestrator.trycycle_explorer --help
python3 -m orchestrator.trycycle_explorer dump-model --help
```

Expected: all compile checks pass and the help output names both `dump-model` and `build`.

**Step 4: Commit**

```bash
git add .gitignore orchestrator/trycycle_explorer/__init__.py orchestrator/trycycle_explorer/__main__.py orchestrator/trycycle_explorer/cli.py orchestrator/trycycle_explorer/model.py
git commit -m "feat: add trycycle explorer cli scaffold"
```

### Task 3: Extract the real graph from DOT and merge only the missing metadata from a sidecar

**Files:**
- Create: `.trycycle-explorer.toml`
- Create: `orchestrator/trycycle_explorer/extract.py`
- Create: `orchestrator/trycycle_explorer/samples/simple-feature.json`
- Create: `orchestrator/trycycle_explorer/samples/plan-review-loop.json`
- Create: `orchestrator/trycycle_explorer/samples/post-review-fix.json`
- Modify: `orchestrator/trycycle_explorer/cli.py`

**Why this task exists:** The current plan’s weakest point was treating `SKILL.md` step headings as the primary graph. That is the wrong source. `docs/trycycle-information-flow.dot` is the graph; the sidecar should annotate it, not replace it.

**Step 1: Write a failing model-build probe**

Run:

```bash
outdir="$(mktemp -d /tmp/trycycle-explorer-model-XXXXXX)"
python3 -m orchestrator.trycycle_explorer dump-model --repo . --output "$outdir/model.json"
rm -rf "$outdir"
```

Expected: the command fails because the extractor and sidecar schema do not exist yet.

**Step 2: Implement DOT-first extraction and sidecar validation**

Implement `orchestrator/trycycle_explorer/extract.py` with this source-of-truth order:

1. Parse `docs/trycycle-information-flow.dot` for node ids, labels, clusters, and edges.
2. Parse `.trycycle-explorer.toml` for prompt variants, outcome labels, binding metadata, palette categories, and sample manifests.
3. Validate that every sidecar node id and edge id refers to a real DOT node or edge.
4. Validate that every sidecar template path exists under the repo.
5. Load sample JSON files referenced by the sidecar.

Use a sidecar shape like:

```toml
[ui]
title = "Trycycle Explorer"

[bindings.USER_REQUEST_TRANSCRIPT]
label = "Task input transcript JSON"
widget = "textarea"
source_category = "transcript"

[prompt_variants.planner.initial]
template = "subagents/prompt-planning-initial.md"
binding_order = ["WORKTREE_PATH", "USER_REQUEST_TRANSCRIPT"]
activate_on_edge_ids = []

[prompt_variants.planner.revision]
template = "subagents/prompt-planning-edit.md"
binding_order = ["WORKTREE_PATH", "USER_REQUEST_TRANSCRIPT", "IMPLEMENTATION_PLAN_PATH"]
activate_on_edge_ids = ["plan_reviewer_to_planner_review_findings"]

[[sample_inputs]]
id = "simple-feature"
label = "Simple feature request"
path = "orchestrator/trycycle_explorer/samples/simple-feature.json"
```

Critical decisions:

- Keep prompt-variant definitions keyed by DOT node id so the graph remains derived from the repo.
- Use `SKILL.md` only for human-facing descriptions and binding help text where useful; do not re-derive topology from prose.
- Store dashed-loop edge ids in the extractor deterministically so sidecar variant activation can reference stable ids.

**Step 3: Verify model extraction**

Run:

```bash
outdir="$(mktemp -d /tmp/trycycle-explorer-model-XXXXXX)"
python3 -m orchestrator.trycycle_explorer dump-model --repo . --output "$outdir/model.json"
python3 - <<'PY' "$outdir/model.json"
import json
import sys

model = json.load(open(sys.argv[1], encoding="utf-8"))
node_ids = {node["id"] for node in model["nodes"]}
assert {"planner", "plan_reviewer", "executor", "post_review"} <= node_ids
planner = next(node for node in model["nodes"] if node["id"] == "planner")
variant_ids = {variant["id"] for variant in planner["prompt_variants"]}
assert {"initial", "revision"} <= variant_ids
assert len(model["sample_inputs"]) >= 3
assert model["bindings"]["USER_REQUEST_TRANSCRIPT"]["widget"] == "textarea"
print("model ok")
PY
rm -rf "$outdir"
```

Expected: the probe prints `model ok` and the model is keyed by real DOT nodes rather than invented heading slugs.

**Step 4: Commit**

```bash
git add .trycycle-explorer.toml orchestrator/trycycle_explorer/extract.py orchestrator/trycycle_explorer/samples/simple-feature.json orchestrator/trycycle_explorer/samples/plan-review-loop.json orchestrator/trycycle_explorer/samples/post-review-fix.json orchestrator/trycycle_explorer/cli.py
git commit -m "feat: extract trycycle explorer graph from dot"
```

### Task 4: Simulate path state, choose prompt variants, and render provenance-rich prompt snapshots

**Files:**
- Create: `orchestrator/trycycle_explorer/simulate.py`
- Modify: `orchestrator/trycycle_explorer/model.py`
- Modify: `orchestrator/trycycle_explorer/extract.py`
- Modify: `orchestrator/trycycle_explorer/cli.py`

**Why this task exists:** “Click a gate and outcome” is not enough. The same gate can have different prompts depending on how the user arrived there. The simulator must choose the active prompt variant from path context and then render with the shared AST trace.

**Step 1: Write a failing simulation probe**

Run:

```bash
python3 - <<'PY'
from orchestrator.trycycle_explorer.simulate import simulate_gate
PY
```

Expected: the import fails because the simulation module does not exist yet.

**Step 2: Implement the simulation engine**

Implement `orchestrator/trycycle_explorer/simulate.py` with these outputs:

```python
@dataclass(frozen=True)
class PromptSnapshot:
    gate_id: str
    variant_id: str | None
    edge_path: list[str]
    raw_markdown: str | None
    rendered_segments: list[dict[str, object]]
    diagnostics: list[dict[str, str]]
```

Required behaviors:

- Resolve the active prompt variant from the selected node plus the traversed edge path.
- Render template ASTs with the non-strict trace mode from Task 1 so missing bindings appear as `<<MISSING:NAME>>` rather than killing the whole simulation.
- Tag rendered segments with categories at minimum:
  - `template-text`
  - `binding-value`
  - `missing-binding`
  - `sidecar-note`
  - `path-derived`
- Emit diagnostics for:
  - missing bindings
  - node with no applicable prompt variant
  - sidecar variant that cannot activate because its trigger edge is missing
- Preserve the previous snapshot input so the browser can compute a before/after diff later.
- Do not invent LLM behavior. Regeneration means rerendering the same static logic with changed bindings or changed selected path.

**Step 3: Verify prompt-variant selection and diagnostics**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
from orchestrator.trycycle_explorer.extract import load_explorer_model
from orchestrator.trycycle_explorer.simulate import simulate_gate

model = load_explorer_model(Path("."), Path(".trycycle-explorer.toml"))
bindings = {
    "WORKTREE_PATH": "/tmp/example-worktree",
    "USER_REQUEST_TRANSCRIPT": '[{"role":"user","text":"plan it"}]',
    "IMPLEMENTATION_PLAN_PATH": "/tmp/example/docs/plans/example.md",
}
initial = simulate_gate(model=model, gate_id="planner", edge_path=[], bindings=bindings)
revision = simulate_gate(
    model=model,
    gate_id="planner",
    edge_path=["plan_reviewer_to_planner_review_findings"],
    bindings=bindings,
)
missing = simulate_gate(model=model, gate_id="planner", edge_path=[], bindings={"WORKTREE_PATH": "/tmp/example-worktree"})
assert initial.variant_id == "initial"
assert revision.variant_id == "revision"
assert any(diag["code"] == "missing-binding" for diag in missing.diagnostics)
assert "<<MISSING:USER_REQUEST_TRANSCRIPT>>" in (missing.raw_markdown or "")
print("simulation ok")
PY
```

Expected: the probe prints `simulation ok`.

**Step 4: Commit**

```bash
git add orchestrator/trycycle_explorer/simulate.py orchestrator/trycycle_explorer/model.py orchestrator/trycycle_explorer/extract.py orchestrator/trycycle_explorer/cli.py
git commit -m "feat: simulate explorer prompt variants"
```

### Task 5: Emit the static site shell and render the graph overview

**Files:**
- Create: `orchestrator/trycycle_explorer/site.py`
- Create: `orchestrator/trycycle_explorer/assets/index.html`
- Create: `orchestrator/trycycle_explorer/assets/app.js`
- Create: `orchestrator/trycycle_explorer/assets/app.css`
- Create: `orchestrator/trycycle_explorer/assets/vendor/marked.min.js`
- Modify: `orchestrator/trycycle_explorer/cli.py`

**Why this task exists:** The explorer is a built artifact, not just a JSON dump. The first browser milestone is a clean overview page that loads the model and renders the real trycycle graph legibly.

**Step 1: Write a failing site-build probe**

Run:

```bash
outdir="$(mktemp -d /tmp/trycycle-explorer-site-XXXXXX)"
python3 -m orchestrator.trycycle_explorer build --repo . --output "$outdir"
rm -rf "$outdir"
```

Expected: the command fails because the site generator does not exist yet.

**Step 2: Implement the static site emitter and overview UI**

Implement `orchestrator/trycycle_explorer/site.py` so `build` writes:

- `<output>/index.html`
- `<output>/app.js`
- `<output>/app.css`
- `<output>/explorer-model.json`
- `<output>/vendor/marked.min.js`

Implement the initial browser shell with these stable regions and hooks:

- `[data-test="flow-map"]`
- `[data-test="input-panel"]`
- `[data-test="prompt-panel"]`
- `[data-test="sample-select"]`

The first milestone UI requirements are:

- load `explorer-model.json`
- render every DOT node and edge with stable `data-node-id` and `data-edge-id` attributes
- show the bundled sample selector
- show an empty-state prompt panel when no prompt-bearing node is selected
- establish the final visual direction early: warm paper page background, dark surfaces, teal/rust/gold accents, distinct cluster treatments, and non-generic typography

Do not add path traversal or rerendering yet in this task; this task is only the overview shell.

**Step 3: Verify the overview page**

Run:

```bash
outdir="$(mktemp -d /tmp/trycycle-explorer-site-XXXXXX)"
python3 -m orchestrator.trycycle_explorer build --repo . --output "$outdir/site"
(cd "$outdir/site" && python3 -m http.server 4173 >"$outdir/http.log" 2>&1 & echo $! >"$outdir/http.pid")
cat >"$outdir/check.mjs" <<'EOF'
import { chromium } from 'playwright';
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });
await page.goto('http://127.0.0.1:4173/', { waitUntil: 'networkidle' });
await page.waitForSelector('[data-test="flow-map"]');
await page.waitForSelector('[data-test="input-panel"]');
await page.waitForSelector('[data-test="prompt-panel"]');
await page.screenshot({ path: process.argv[2], fullPage: true });
await browser.close();
EOF
node "$outdir/check.mjs" "$outdir/01-overview.png"
kill "$(cat "$outdir/http.pid")"
```

Expected: the page loads, all three panels render, and `01-overview.png` is created.

**Step 4: Inspect the screenshot before committing**

Open `01-overview.png` with the available image-viewing tool in the execution environment and verify:

- graph labels are readable without zooming
- clusters are visually distinct
- no text overlaps or clipped nodes are visible
- the page looks intentional rather than like default browser styles

If any of those fail, fix the UI before committing.

**Step 5: Commit**

```bash
git add orchestrator/trycycle_explorer/site.py orchestrator/trycycle_explorer/assets/index.html orchestrator/trycycle_explorer/assets/app.js orchestrator/trycycle_explorer/assets/app.css orchestrator/trycycle_explorer/assets/vendor/marked.min.js orchestrator/trycycle_explorer/cli.py
git commit -m "feat: generate trycycle explorer overview site"
```

### Task 6: Add sample selection, custom bindings, gate/outcome traversal, and prompt rendering

**Files:**
- Modify: `orchestrator/trycycle_explorer/site.py`
- Modify: `orchestrator/trycycle_explorer/assets/index.html`
- Modify: `orchestrator/trycycle_explorer/assets/app.js`
- Modify: `orchestrator/trycycle_explorer/assets/app.css`

**Why this task exists:** This is the core user flow. The explorer only becomes useful when a user can choose a sample, edit bindings, click through outcomes, and see the exact rendered prompt for the active path.

**Step 1: Write a failing interaction probe**

Run:

```bash
outdir="$(mktemp -d /tmp/trycycle-explorer-interact-XXXXXX)"
python3 -m orchestrator.trycycle_explorer build --repo . --output "$outdir/site"
(cd "$outdir/site" && python3 -m http.server 4173 >"$outdir/http.log" 2>&1 & echo $! >"$outdir/http.pid")
cat >"$outdir/check.mjs" <<'EOF'
import { chromium } from 'playwright';
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });
await page.goto('http://127.0.0.1:4173/', { waitUntil: 'networkidle' });
await page.selectOption('[data-test="sample-select"]', 'plan-review-loop');
await page.click('[data-node-id="planner"]');
await page.click('[data-edge-id="planner_to_implementation_plan"]');
await page.waitForSelector('[data-test="prompt-source"]', { timeout: 3000 });
await browser.close();
EOF
node "$outdir/check.mjs"
kill "$(cat "$outdir/http.pid")"
rm -rf "$outdir"
```

Expected: the probe fails because traversal and prompt rendering do not exist yet.

**Step 2: Implement interaction and prompt display**

Implement these exact UI behaviors:

- selecting a sample populates all binding widgets from sidecar metadata
- binding widgets are generated from the sidecar, not hard-coded
- clicking a node selects the gate and highlights incoming/outgoing edges
- clicking an outcome edge updates the active path and rerenders the prompt snapshot
- prompt panel shows:
  - gate title
  - active prompt variant id
  - rendered markdown HTML
  - raw markdown source
  - prompt template path
- raw markdown source uses serialized AST rendering from the model, not reparsing source `.md` files in the browser
- no network calls beyond fetching the built static assets

Add these stable hooks:

- `[data-test="prompt-html"]`
- `[data-test="prompt-source"]`
- `[data-test="path-inspector"]`
- `[data-test="rerender"]`

**Step 3: Verify interaction and capture screenshots**

Run:

```bash
outdir="$(mktemp -d /tmp/trycycle-explorer-interact-XXXXXX)"
python3 -m orchestrator.trycycle_explorer build --repo . --output "$outdir/site"
(cd "$outdir/site" && python3 -m http.server 4173 >"$outdir/http.log" 2>&1 & echo $! >"$outdir/http.pid")
cat >"$outdir/check.mjs" <<'EOF'
import { chromium } from 'playwright';
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });
await page.goto('http://127.0.0.1:4173/', { waitUntil: 'networkidle' });
await page.selectOption('[data-test="sample-select"]', 'plan-review-loop');
await page.click('[data-node-id="planner"]');
await page.screenshot({ path: process.argv[2] + '/02-selected-gate.png', fullPage: true });
await page.click('[data-edge-id="plan_reviewer_to_planner_review_findings"]');
await page.waitForSelector('[data-test="prompt-source"]');
const promptText = await page.textContent('[data-test="prompt-source"]');
if (!promptText || !promptText.includes('<current_implementation_plan_path>')) {
  throw new Error('expected planning-edit prompt content');
}
await page.screenshot({ path: process.argv[2] + '/03-selected-path.png', fullPage: true });
await browser.close();
EOF
mkdir -p "$outdir/shots"
node "$outdir/check.mjs" "$outdir/shots"
kill "$(cat "$outdir/http.pid")"
```

Expected: both screenshots are created and the selected path shows the revision planning prompt.

**Step 4: Inspect the screenshots before committing**

Open `02-selected-gate.png` and `03-selected-path.png` and verify:

- the selected node and selected edge are unmistakable
- the prompt panel remains readable when populated with real markdown
- the path inspector explains how the current prompt variant was chosen
- the page still looks cohesive after real content appears

If any of those fail, fix them before committing.

**Step 5: Commit**

```bash
git add orchestrator/trycycle_explorer/site.py orchestrator/trycycle_explorer/assets/index.html orchestrator/trycycle_explorer/assets/app.js orchestrator/trycycle_explorer/assets/app.css
git commit -m "feat: add explorer traversal and prompt rendering"
```

### Task 7: Add provenance coloring, diagnostics, before/after diffing, and responsive polish

**Files:**
- Modify: `.trycycle-explorer.toml`
- Modify: `orchestrator/trycycle_explorer/simulate.py`
- Modify: `orchestrator/trycycle_explorer/assets/index.html`
- Modify: `orchestrator/trycycle_explorer/assets/app.js`
- Modify: `orchestrator/trycycle_explorer/assets/app.css`

**Why this task exists:** The user asked for a prompt-debugging tool, not just a browser for templates. Provenance, visible diagnostics, and before/after comparisons are what make it useful for spotting missing information and trying alternate inputs.

**Step 1: Write a failing diagnostics and mobile probe**

Run:

```bash
outdir="$(mktemp -d /tmp/trycycle-explorer-polish-XXXXXX)"
python3 -m orchestrator.trycycle_explorer build --repo . --output "$outdir/site"
(cd "$outdir/site" && python3 -m http.server 4173 >"$outdir/http.log" 2>&1 & echo $! >"$outdir/http.pid")
cat >"$outdir/check.mjs" <<'EOF'
import { chromium } from 'playwright';

async function assertNoOverflow(page, selector) {
  const ok = await page.$eval(selector, (el) => el.scrollWidth <= el.clientWidth + 1);
  if (!ok) throw new Error(`overflow in ${selector}`);
}

const browser = await chromium.launch({ headless: true });
const desktop = await browser.newPage({ viewport: { width: 1440, height: 960 } });
await desktop.goto('http://127.0.0.1:4173/', { waitUntil: 'networkidle' });
await desktop.fill('[name="USER_REQUEST_TRANSCRIPT"]', '');
await desktop.click('[data-test="rerender"]');
await desktop.waitForSelector('[data-test="diagnostics"] [data-code="missing-binding"]', { timeout: 3000 });
await desktop.waitForSelector('[data-test="provenance-legend"]', { timeout: 3000 });
await desktop.waitForSelector('[data-test="diff-panel"]', { timeout: 3000 });
await assertNoOverflow(desktop, '[data-test="prompt-panel"]');
const mobile = await browser.newPage({ viewport: { width: 390, height: 844 } });
await mobile.goto('http://127.0.0.1:4173/', { waitUntil: 'networkidle' });
await assertNoOverflow(mobile, '[data-test="input-panel"]');
await browser.close();
EOF
node "$outdir/check.mjs"
kill "$(cat "$outdir/http.pid")"
rm -rf "$outdir"
```

Expected: the probe fails because diagnostics, legend, diffing, and mobile-safe layout do not exist yet.

**Step 2: Implement debugging-oriented UI**

Implement these exact behaviors:

- add provenance coloring and labels for at least:
  - `template-text`
  - `binding-value`
  - `missing-binding`
  - `sidecar-note`
  - `path-derived`
- add a visible legend with stable hook `[data-test="provenance-legend"]`
- add a diagnostics tray with stable hook `[data-test="diagnostics"]`
- preserve the previous prompt snapshot after each rerender and show a line-oriented before/after diff in `[data-test="diff-panel"]`
- keep missing bindings visible in raw markdown as `<<MISSING:NAME>>`
- ensure narrow-screen layout collapses to one column without clipped chips, hidden labels, or horizontal scrolling in the main panels
- keep the in-app scope strict: editing bindings and rerendering is supported, but editing templates or calling an LLM is not

**Step 3: Verify polished states and capture screenshots**

Run:

```bash
outdir="$(mktemp -d /tmp/trycycle-explorer-polish-XXXXXX)"
mkdir -p "$outdir/shots"
python3 -m orchestrator.trycycle_explorer build --repo . --output "$outdir/site"
(cd "$outdir/site" && python3 -m http.server 4173 >"$outdir/http.log" 2>&1 & echo $! >"$outdir/http.pid")
cat >"$outdir/check.mjs" <<'EOF'
import { chromium } from 'playwright';

const browser = await chromium.launch({ headless: true });
const desktop = await browser.newPage({ viewport: { width: 1440, height: 960 } });
await desktop.goto('http://127.0.0.1:4173/', { waitUntil: 'networkidle' });
await desktop.click('[data-node-id="planner"]');
await desktop.click('[data-edge-id="plan_reviewer_to_planner_review_findings"]');
await desktop.screenshot({ path: process.argv[2] + '/04-provenance.png', fullPage: true });
await desktop.fill('[name="USER_REQUEST_TRANSCRIPT"]', '');
await desktop.click('[data-test="rerender"]');
await desktop.screenshot({ path: process.argv[2] + '/05-diagnostics.png', fullPage: true });
const mobile = await browser.newPage({ viewport: { width: 390, height: 844 } });
await mobile.goto('http://127.0.0.1:4173/', { waitUntil: 'networkidle' });
await mobile.screenshot({ path: process.argv[2] + '/06-mobile.png', fullPage: true });
await browser.close();
EOF
node "$outdir/check.mjs" "$outdir/shots"
kill "$(cat "$outdir/http.pid")"
```

Expected: the screenshot set is complete and the desktop state includes provenance, diagnostics, and diff UI.

**Step 4: Inspect the screenshots before committing**

Open `04-provenance.png`, `05-diagnostics.png`, and `06-mobile.png` and verify:

- provenance colors are distinct and the legend is understandable
- diagnostic messages are visible and clearly associated with the missing input
- the diff panel explains what changed after rerender
- the mobile view remains attractive and readable rather than merely unbroken

If any of those fail, fix them before committing.

**Step 5: Commit**

```bash
git add .trycycle-explorer.toml orchestrator/trycycle_explorer/simulate.py orchestrator/trycycle_explorer/assets/index.html orchestrator/trycycle_explorer/assets/app.js orchestrator/trycycle_explorer/assets/app.css
git commit -m "feat: add explorer diagnostics and visual polish"
```

### Task 8: Harden validation, failure reporting, and maintainer docs

**Files:**
- Modify: `orchestrator/trycycle_explorer/extract.py`
- Modify: `orchestrator/trycycle_explorer/site.py`
- Modify: `orchestrator/trycycle_explorer/cli.py`
- Modify: `README.md`
- Create: `docs/trycycle-explorer.md`

**Why this task exists:** The explorer must fail clearly when trycycle changes out from under it, and maintainers need a crisp rule for when to update the sidecar.

**Step 1: Write failing boundary probes**

Run:

```bash
tmpdir="$(mktemp -d /tmp/trycycle-explorer-boundary-XXXXXX)"
cat >"$tmpdir/bad-sidecar.toml" <<'EOF'
[prompt_variants.planner.bad]
template = "subagents/prompt-planning-initial.md"
binding_order = ["WORKTREE_PATH"]
activate_on_edge_ids = ["not-a-real-edge"]
EOF
! python3 -m orchestrator.trycycle_explorer dump-model --repo . --sidecar "$tmpdir/bad-sidecar.toml" --output "$tmpdir/model.json"
! python3 -m orchestrator.trycycle_explorer build --repo . --sample does-not-exist --output "$tmpdir/site"
rm -rf "$tmpdir"
```

Expected: both commands fail, but not yet with explorer-specific errors.

**Step 2: Implement validation and documentation**

Implement these behaviors:

- `dump-model` and `build` exit non-zero with explicit stderr when:
  - a sidecar node or edge reference is unknown
  - a sample id is unknown
  - a sample file is unreadable
  - a template path is unreadable
- `explorer-model.json` includes:
  - `generated_at`
  - `repo_root`
  - `nodes`
  - `edges`
  - `bindings`
  - `sample_inputs`
  - `palette`
  - `build_diagnostics`
- update `README.md` with a short run/serve section for the explorer
- create `docs/trycycle-explorer.md` covering:
  - source-of-truth order
  - sidecar ownership and update triggers
  - sample file format
  - build artifacts
  - the disposable verification commands from Tasks 5 through 8

**Step 3: Verify failures, performance, and docs**

Run:

```bash
tmpdir="$(mktemp -d /tmp/trycycle-explorer-boundary-XXXXXX)"
cat >"$tmpdir/bad-sidecar.toml" <<'EOF'
[prompt_variants.planner.bad]
template = "subagents/prompt-planning-initial.md"
binding_order = ["WORKTREE_PATH"]
activate_on_edge_ids = ["not-a-real-edge"]
EOF
! python3 -m orchestrator.trycycle_explorer dump-model --repo . --sidecar "$tmpdir/bad-sidecar.toml" --output "$tmpdir/model.json" 2>"$tmpdir/error.txt"
rg -n "not-a-real-edge|planner" "$tmpdir/error.txt"
/usr/bin/time -f '%e' python3 -m orchestrator.trycycle_explorer build --repo . --output "$tmpdir/site" >/dev/null
rg -n "trycycle explorer|\\.trycycle-explorer\\.toml|python3 -m orchestrator\\.trycycle_explorer" README.md docs/trycycle-explorer.md
rm -rf "$tmpdir"
```

Expected:

- the bad-sidecar command fails and stderr names the bad edge id explicitly
- the build completes comfortably under 10 seconds
- the docs contain the actual commands and sidecar path shipped by the implementation

**Step 4: Commit**

```bash
git add orchestrator/trycycle_explorer/extract.py orchestrator/trycycle_explorer/site.py orchestrator/trycycle_explorer/cli.py README.md docs/trycycle-explorer.md
git commit -m "docs: add trycycle explorer validation and usage guide"
```

### Task 9: Run final end-to-end verification and record the evidence

**Files:**
- Modify: none unless verification reveals a real bug

**Why this task exists:** This repo forbids committed tests for this feature, so the final bar must come from production-surface verification plus screenshot inspection.

**Step 1: Build the final site and run the browser scenario**

Run:

```bash
final_dir="$(mktemp -d /tmp/trycycle-explorer-final-XXXXXX)"
mkdir -p "$final_dir/shots"
python3 -m orchestrator.trycycle_explorer build --repo . --output "$final_dir/site"
(cd "$final_dir/site" && python3 -m http.server 4173 >"$final_dir/http.log" 2>&1 & echo $! >"$final_dir/http.pid")
cat >"$final_dir/check.mjs" <<'EOF'
import { chromium } from 'playwright';

async function assertNoOverflow(page, selector) {
  const ok = await page.$eval(selector, (el) => el.scrollWidth <= el.clientWidth + 1);
  if (!ok) throw new Error(`overflow in ${selector}`);
}

const browser = await chromium.launch({ headless: true });
const desktop = await browser.newPage({ viewport: { width: 1440, height: 960 } });
await desktop.goto('http://127.0.0.1:4173/', { waitUntil: 'networkidle' });
await desktop.selectOption('[data-test="sample-select"]', 'post-review-fix');
await desktop.click('[data-node-id="executor"]');
await desktop.click('[data-edge-id="post_review_to_executor_fix_round"]');
await desktop.waitForSelector('[data-test="prompt-source"]');
await assertNoOverflow(desktop, '[data-test="flow-map"]');
await assertNoOverflow(desktop, '[data-test="prompt-panel"]');
await desktop.screenshot({ path: process.argv[2] + '/final-desktop.png', fullPage: true });
await desktop.fill('[name="POST_IMPLEMENTATION_REVIEW_FINDINGS_VERBATIM"]', '');
await desktop.click('[data-test="rerender"]');
await desktop.screenshot({ path: process.argv[2] + '/final-diagnostic.png', fullPage: true });
const mobile = await browser.newPage({ viewport: { width: 390, height: 844 } });
await mobile.goto('http://127.0.0.1:4173/', { waitUntil: 'networkidle' });
await mobile.screenshot({ path: process.argv[2] + '/final-mobile.png', fullPage: true });
await browser.close();
EOF
node "$final_dir/check.mjs" "$final_dir/shots"
kill "$(cat "$final_dir/http.pid")"
```

Expected: the scenario succeeds and produces `final-desktop.png`, `final-diagnostic.png`, and `final-mobile.png`.

**Step 2: Inspect the final screenshots**

Open the three final screenshots and verify:

- the executor fix-round path is obvious and correctly rendered
- markdown blocks, raw source, and diagnostics are all readable
- the mobile layout still feels deliberate and attractive
- nothing in the screenshots suggests stale data, incorrect path selection, or broken provenance labeling

If any of those fail, fix the bug and rerun this task before finishing.

**Step 3: Re-run the core model and boundary probes**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
from orchestrator.trycycle_explorer.extract import load_explorer_model

model = load_explorer_model(Path("."), Path(".trycycle-explorer.toml"))
assert any(node.id == "planner" for node in model.nodes)
assert any(node.id == "executor" for node in model.nodes)
print("final model ok")
PY

tmpdir="$(mktemp -d /tmp/trycycle-explorer-final-boundary-XXXXXX)"
cat >"$tmpdir/bad-sidecar.toml" <<'EOF'
[prompt_variants.executor.bad]
template = "subagents/prompt-executing.md"
binding_order = ["WORKTREE_PATH"]
activate_on_edge_ids = ["missing-edge"]
EOF
! python3 -m orchestrator.trycycle_explorer dump-model --repo . --sidecar "$tmpdir/bad-sidecar.toml" --output "$tmpdir/model.json" 2>"$tmpdir/error.txt"
rg -n "missing-edge" "$tmpdir/error.txt"
rm -rf "$tmpdir"
```

Expected: the model probe prints `final model ok` and the bad-sidecar probe still fails loudly.

**Step 4: Record verification evidence for the implementation report**

Record in `## Verification results`:

- the exact build command
- the Playwright scenario command
- the screenshot filenames reviewed
- the model probe result
- the bad-sidecar failure result
- whether any verification bug fix was needed after screenshot inspection

**Step 5: Commit only if verification required a code fix**

If verification exposed a real bug and you fixed it, commit that fix with an accurate message. If verification passed without code changes, do not create a no-op commit.
