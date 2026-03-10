# Trycycle Explorer Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use trycycle-executing to implement this plan task-by-task.

**Goal:** Build a Python-first static-site generator that derives a navigable trycycle explorer from the real repo flow and prompt templates, lets users pick sample inputs or edit their own bindings in-browser, and shows path-specific rendered prompts, provenance, diagnostics, and before/after simulation changes.

**Architecture:** Keep trycycle itself as the source of truth. Extract gates, prompt templates, and flow metadata from `SKILL.md`, `subagents/*.md`, and `docs/trycycle-information-flow.dot`, then merge only the non-derivable pieces from a small root sidecar at `.trycycle-explorer.toml`. Emit one canonical `explorer-model.json` plus a static `index.html`/`app.js`/`app.css`; the browser handles path traversal, prompt rendering, markdown preview, provenance highlighting, missing-binding diagnostics, and render-to-render diffing with no backend.

**Tech Stack:** Python 3.12 standard library, existing `orchestrator/prompt_builder` logic factored into a shared template AST module, TOML sidecar config, vanilla HTML/CSS/ES modules, vendored browser markdown renderer, disposable `/tmp` probes, `python3 -m http.server`, Playwright CLI

---

### Task 1: Share prompt-template semantics and add the explorer CLI entrypoint

**Files:**
- Create: `orchestrator/prompt_builder/template_ast.py`
- Modify: `orchestrator/prompt_builder/build.py`
- Create: `trycycle_explorer/__init__.py`
- Create: `trycycle_explorer/__main__.py`
- Create: `trycycle_explorer/cli.py`
- Modify: `.gitignore`

**Why this task exists:** The explorer must render the exact same placeholder and conditional semantics that trycycle uses today. Do not build a second prompt language implementation in parallel. Move the current parser/renderer into a shared module, keep `build.py` behavior stable, and make the new explorer CLI consume the same shared AST so the repo has one definition of “how a trycycle template works.”

**Step 1: Write a failing disposable probe**

```bash
tmpdir="$(mktemp -d /tmp/trycycle-explorer-cli-XXXXXX)"
cat >"$tmpdir/probe.py" <<'PY'
from orchestrator.prompt_builder.template_ast import parse_template_text
PY
python3 "$tmpdir/probe.py"
python3 -m trycycle_explorer --help
rm -rf "$tmpdir"
```

Expected: the import fails because `template_ast.py` does not exist yet, and `python3 -m trycycle_explorer --help` fails because the package entrypoint is missing.

**Step 2: Implement the shared AST module and CLI scaffold**

Implement `orchestrator/prompt_builder/template_ast.py` around the current `build.py` logic:

```python
@dataclass(frozen=True)
class TextNode:
    text: str


@dataclass(frozen=True)
class IfNode:
    name: str
    truthy: list["Node"]
    falsy: list["Node"]


Node = TextNode | IfNode
```

Required behaviors:

- Move tokenization, conditional parsing, placeholder substitution, and rendering helpers out of `build.py` into this module.
- Add a JSON-safe serializer for AST nodes so later tasks can ship template structure to the browser without re-parsing markdown there.
- Keep `build.py` as a thin CLI wrapper over the shared module. Its current CLI contract, stderr prefix, and exit codes must stay unchanged.
- Create `trycycle_explorer/__main__.py` and `trycycle_explorer/cli.py` with subcommands `build` and `dump-model`.
- Default the build output directory to `build/trycycle-explorer`.
- Add `build/trycycle-explorer/` to `.gitignore`.

**Step 3: Verify the shared parser and CLI**

Run:

```bash
python3 -m py_compile \
  orchestrator/prompt_builder/template_ast.py \
  orchestrator/prompt_builder/build.py \
  trycycle_explorer/__init__.py \
  trycycle_explorer/__main__.py \
  trycycle_explorer/cli.py

tmpdir="$(mktemp -d /tmp/trycycle-explorer-cli-XXXXXX)"
cat >"$tmpdir/template.md" <<'EOF'
hello {NAME}
{{#if EXTRA}}extra: {EXTRA}{{else}}no extra{{/if}}
EOF
python3 orchestrator/prompt_builder/build.py \
  --template "$tmpdir/template.md" \
  --set NAME=world \
  --set EXTRA=value
python3 -m trycycle_explorer --help
rm -rf "$tmpdir"
```

Expected:

- `py_compile` succeeds with no stderr.
- The prompt builder still prints `hello world` and `extra: value`.
- The explorer CLI prints usage text with `build` and `dump-model`.

**Step 4: Commit**

```bash
git add .gitignore orchestrator/prompt_builder/template_ast.py orchestrator/prompt_builder/build.py trycycle_explorer/__init__.py trycycle_explorer/__main__.py trycycle_explorer/cli.py
git commit -m "feat: add trycycle explorer cli scaffold"
```

### Task 2: Build the canonical explorer model from repo sources plus a minimal sidecar

**Files:**
- Create: `.trycycle-explorer.toml`
- Create: `trycycle_explorer/model.py`
- Create: `trycycle_explorer/extract.py`
- Create: `trycycle_explorer/simulate.py`
- Create: `trycycle_explorer/samples/simple-feature.json`
- Create: `trycycle_explorer/samples/plan-review-loop.json`
- Create: `trycycle_explorer/samples/post-review-fix.json`
- Modify: `trycycle_explorer/cli.py`

**Why this task exists:** The user explicitly rejected a standalone mock. The model must come from the real trycycle flow and templates so future repo changes flow into the explorer automatically. Use `.trycycle-explorer.toml` only for information the code cannot derive reliably from prose: gate grouping/order, outcome labels, sample scenarios, binding field descriptions, palette categories, and loop edges that live only in human instructions.

**Step 1: Write a failing disposable model-build probe**

Run:

```bash
outdir="$(mktemp -d /tmp/trycycle-explorer-build-XXXXXX)"
python3 -m trycycle_explorer dump-model --repo . --output "$outdir/model.json"
rm -rf "$outdir"
```

Expected: the command fails because the extractor, model types, and sidecar schema do not exist yet.

**Step 2: Implement extraction, sidecar merge, and deterministic simulation data**

Implement these model layers in `trycycle_explorer/model.py`:

```python
@dataclass(frozen=True)
class Gate:
    id: str
    title: str
    group: str
    source_path: str
    prompt_template_path: str | None
    template_ast: list[dict[str, object]] | None
    outcomes: list["Outcome"]


@dataclass(frozen=True)
class Outcome:
    id: str
    label: str
    to_gate_id: str
    provenance: str


@dataclass(frozen=True)
class SampleInput:
    id: str
    label: str
    bindings: dict[str, str]
```

Implement `trycycle_explorer/extract.py` with these responsibilities:

- Parse `SKILL.md` section headings into stable gate ids by slugifying the numbered step titles.
- Extract prompt template references from `SKILL.md` and `subagents/*.md`.
- Parse `docs/trycycle-information-flow.dot` for node ids, human labels, and documented edges.
- Merge `.trycycle-explorer.toml` to add the pieces prose cannot safely encode:
  - gate cluster/group order
  - outcome labels and loop edges
  - binding field labels/help text/widget types
  - provenance palette categories
  - sample scenario manifest
- Load the sample JSON files listed in the TOML sidecar.

Use this TOML structure so maintainers can comment and update it without learning a new schema:

```toml
[display]
title = "Trycycle Explorer"

[bindings.USER_REQUEST_TRANSCRIPT]
label = "Task input transcript JSON"
widget = "textarea"
source_category = "user-input"

[[sample_inputs]]
id = "simple-feature"
label = "Simple feature request"
path = "trycycle_explorer/samples/simple-feature.json"

[[outcomes]]
from = "plan-with-trycycle-planning"
id = "plan-created"
label = "Plan created"
to = "plan-editor-loop"
```

Implement `trycycle_explorer/simulate.py` so a scenario produces a canonical render snapshot with:

- selected gate id
- selected outcome id
- rendered prompt markdown
- rendered prompt segments with provenance tags
- rendered HTML-safe markdown source
- missing-binding diagnostics instead of hard crashes
- previous vs current render diff inputs for later UI comparison

Important decision: when a binding is missing in custom input mode, return a diagnostic record and substitute a visible placeholder token such as `<<MISSING:USER_REQUEST_TRANSCRIPT>>` in the raw markdown view. Do not silently drop content and do not throw an uncaught exception in the browser. The point of this explorer is to surface prompt-quality gaps.

**Step 3: Verify the model output**

Run:

```bash
outdir="$(mktemp -d /tmp/trycycle-explorer-model-XXXXXX)"
python3 -m trycycle_explorer dump-model --repo . --output "$outdir/model.json"
python3 - <<'PY' "$outdir/model.json"
import json, sys
model = json.load(open(sys.argv[1], encoding="utf-8"))
gate_ids = {gate["id"] for gate in model["gates"]}
assert "testing-strategy" in gate_ids
assert "plan-with-trycycle-planning" in gate_ids
assert "execute-with-trycycle-executing" in gate_ids
assert len(model["sample_inputs"]) >= 3
assert model["bindings"]["USER_REQUEST_TRANSCRIPT"]["widget"] == "textarea"
assert any(outcome["to_gate_id"] == "plan-editor-loop" for gate in model["gates"] for outcome in gate["outcomes"])
print("model ok")
PY
rm -rf "$outdir"
```

Expected: `dump-model` succeeds, the Python assertion script prints `model ok`, and the model contains real trycycle gates, at least three samples, binding metadata, and at least one loop edge sourced through the sidecar.

**Step 4: Commit**

```bash
git add .trycycle-explorer.toml trycycle_explorer/model.py trycycle_explorer/extract.py trycycle_explorer/simulate.py trycycle_explorer/samples/simple-feature.json trycycle_explorer/samples/plan-review-loop.json trycycle_explorer/samples/post-review-fix.json trycycle_explorer/cli.py
git commit -m "feat: extract a canonical trycycle explorer model"
```

### Task 3: Emit the static site and browser runtime for path traversal and prompt rendering

**Files:**
- Create: `trycycle_explorer/site.py`
- Create: `trycycle_explorer/assets/index.html`
- Create: `trycycle_explorer/assets/app.js`
- Create: `trycycle_explorer/assets/app.css`
- Create: `trycycle_explorer/assets/vendor/marked.min.js`
- Modify: `trycycle_explorer/cli.py`

**Why this task exists:** The product the user asked for is not the JSON model. It is an explorable static page. Keep the output dead-simple and durable: one build command writes a self-contained static directory that can be served by any basic file server.

**Step 1: Write a failing browser probe against the empty site**

Run:

```bash
outdir="$(mktemp -d /tmp/trycycle-explorer-site-XXXXXX)"
python3 -m trycycle_explorer build --repo . --output "$outdir"
server_log="$outdir/http.log"
(cd "$outdir" && python3 -m http.server 4173 >"$server_log" 2>&1 & echo $! >"$outdir/http.pid")
cat >"$outdir/check.mjs" <<'EOF'
import { chromium } from 'playwright';
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });
await page.goto('http://127.0.0.1:4173/', { waitUntil: 'networkidle' });
await page.waitForSelector('[data-test="flow-map"]', { timeout: 3000 });
await browser.close();
EOF
node "$outdir/check.mjs"
kill "$(cat "$outdir/http.pid")"
rm -rf "$outdir"
```

Expected: this fails because the site emitter and required DOM structure do not exist yet.

**Step 2: Implement the site generator and interactive runtime**

Implement `trycycle_explorer/site.py` and the browser assets with these exact responsibilities:

- `python3 -m trycycle_explorer build --repo . --output <dir>` writes:
  - `<dir>/index.html`
  - `<dir>/app.js`
  - `<dir>/app.css`
  - `<dir>/explorer-model.json`
  - `<dir>/vendor/marked.min.js`
- `index.html` includes three stable panels with `data-test` hooks:
  - `flow-map`
  - `input-panel`
  - `prompt-panel`
- `app.js` loads `explorer-model.json`, renders the initial sample scenario, and allows:
  - sample selection
  - editing binding fields generated from sidecar metadata
  - clicking a gate
  - clicking an outcome
  - re-running the simulation without a backend
  - showing both rendered markdown HTML and raw markdown source
- Use the AST emitted in Task 2 to render prompts client-side. Do not re-parse the original `.md` templates in the browser.
- Use the vendored markdown library only for markdown-to-HTML conversion. All trycycle template semantics still come from the shared AST, not from the library.
- Surface missing bindings, unresolved edges, or sidecar drift in a visible diagnostics tray instead of hiding them.

**Step 3: Verify the built site renders and responds**

Run:

```bash
outdir="$(mktemp -d /tmp/trycycle-explorer-site-XXXXXX)"
python3 -m trycycle_explorer build --repo . --output "$outdir"
(cd "$outdir" && python3 -m http.server 4173 >"$outdir/http.log" 2>&1 & echo $! >"$outdir/http.pid")
cat >"$outdir/check.mjs" <<'EOF'
import { chromium } from 'playwright';
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });
await page.goto('http://127.0.0.1:4173/', { waitUntil: 'networkidle' });
await page.waitForSelector('[data-test="flow-map"]');
await page.waitForSelector('[data-test="input-panel"]');
await page.waitForSelector('[data-test="prompt-panel"]');
await page.selectOption('[data-test="sample-select"]', 'plan-review-loop');
await page.click('[data-gate-id="plan-with-trycycle-planning"]');
await page.click('[data-outcome-id="plan-created"]');
const promptText = await page.textContent('[data-test="prompt-source"]');
if (!promptText || !promptText.includes('<task_input_json>')) throw new Error('prompt source missing');
await browser.close();
EOF
node "$outdir/check.mjs"
kill "$(cat "$outdir/http.pid")"
rm -rf "$outdir"
```

Expected: the page loads, the three panels render, clicking a gate and outcome updates the prompt panel, and the raw prompt source includes real prompt content from the selected trycycle step.

**Step 4: Commit**

```bash
git add trycycle_explorer/site.py trycycle_explorer/assets/index.html trycycle_explorer/assets/app.js trycycle_explorer/assets/app.css trycycle_explorer/assets/vendor/marked.min.js trycycle_explorer/cli.py
git commit -m "feat: generate the trycycle explorer static site"
```

### Task 4: Add provenance-aware diagnostics, before/after diffing, and visual polish

**Files:**
- Modify: `trycycle_explorer/simulate.py`
- Modify: `trycycle_explorer/assets/app.js`
- Modify: `trycycle_explorer/assets/app.css`
- Modify: `trycycle_explorer/assets/index.html`
- Modify: `.trycycle-explorer.toml`

**Why this task exists:** The user’s actual goal is prompt debugging, not just browsing. The UI must make it obvious what came from the template, what came from user-provided bindings, what was injected by sidecar logic, and what changed between one simulation run and the next.

**Step 1: Write a failing custom-input and diff probe**

Run:

```bash
outdir="$(mktemp -d /tmp/trycycle-explorer-diff-XXXXXX)"
python3 -m trycycle_explorer build --repo . --output "$outdir"
(cd "$outdir" && python3 -m http.server 4173 >"$outdir/http.log" 2>&1 & echo $! >"$outdir/http.pid")
cat >"$outdir/check.mjs" <<'EOF'
import { chromium } from 'playwright';
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });
await page.goto('http://127.0.0.1:4173/', { waitUntil: 'networkidle' });
await page.fill('[name="USER_REQUEST_TRANSCRIPT"]', '');
await page.click('[data-test="rerender"]');
await page.waitForSelector('[data-test="diagnostics"] [data-severity="missing-binding"]', { timeout: 3000 });
await page.fill('[name="USER_REQUEST_TRANSCRIPT"]', '[{\"role\":\"user\",\"text\":\"rewrite the plan\"}]');
await page.click('[data-test="rerender"]');
await page.waitForSelector('[data-test="diff-panel"] .diff-added', { timeout: 3000 });
await browser.close();
EOF
node "$outdir/check.mjs"
kill "$(cat "$outdir/http.pid")"
rm -rf "$outdir"
```

Expected: this fails because the diagnostics tray, rerender flow, and diff panel do not exist yet.

**Step 2: Implement diagnostics, provenance, and diff-oriented UI**

Implement these product behaviors:

- Raw markdown view shows inline provenance spans with stable categories such as:
  - `template-text`
  - `user-input`
  - `derived-path`
  - `sidecar-overlay`
  - `missing-binding`
- Add a visible legend that maps those categories to colors.
- Add a diagnostics tray summarizing missing bindings, unresolved edges, and sidecar mismatches.
- Preserve the previous render snapshot in browser state and compute a line-oriented diff against the current render after each rerender.
- Show a “before / after” summary card so the user can see whether a prompt improved after editing inputs.
- Use an intentional visual system instead of default styling:
  - warm paper background, dark ink surfaces, teal/rust/gold accents
  - CSS custom properties at the top of `app.css`
  - responsive two-column desktop layout that collapses cleanly to one column on mobile
  - readable code/pre blocks and sticky path inspector
- Keep all user-visible text legible at narrow widths. No clipped chips, no horizontal scroll in the main panels, and no color-only state indication without labels.

**Step 3: Verify diagnostics, screenshots, and responsive layout**

Run:

```bash
outdir="$(mktemp -d /tmp/trycycle-explorer-ui-XXXXXX)"
shots="$outdir/shots"
mkdir -p "$shots"
python3 -m trycycle_explorer build --repo . --output "$outdir/site"
(cd "$outdir/site" && python3 -m http.server 4173 >"$outdir/http.log" 2>&1 & echo $! >"$outdir/http.pid")
cat >"$outdir/check.mjs" <<'EOF'
import { chromium } from 'playwright';

async function assertNoHorizontalOverflow(page, selector) {
  const ok = await page.$eval(selector, (el) => el.scrollWidth <= el.clientWidth + 1);
  if (!ok) throw new Error(`horizontal overflow in ${selector}`);
}

const browser = await chromium.launch({ headless: true });
const desktop = await browser.newPage({ viewport: { width: 1440, height: 960 } });
await desktop.goto('http://127.0.0.1:4173/', { waitUntil: 'networkidle' });
await desktop.screenshot({ path: process.argv[2] + '/overview.png', fullPage: true });
await desktop.click('[data-gate-id="plan-with-trycycle-planning"]');
await desktop.click('[data-outcome-id="plan-created"]');
await desktop.screenshot({ path: process.argv[2] + '/selected-path.png', fullPage: true });
await desktop.fill('[name="USER_REQUEST_TRANSCRIPT"]', '');
await desktop.click('[data-test="rerender"]');
await desktop.screenshot({ path: process.argv[2] + '/custom-input-diagnostic.png', fullPage: true });
await assertNoHorizontalOverflow(desktop, '[data-test="flow-map"]');
await assertNoHorizontalOverflow(desktop, '[data-test="prompt-panel"]');
const mobile = await browser.newPage({ viewport: { width: 390, height: 844 } });
await mobile.goto('http://127.0.0.1:4173/', { waitUntil: 'networkidle' });
await mobile.screenshot({ path: process.argv[2] + '/mobile.png', fullPage: true });
await assertNoHorizontalOverflow(mobile, '[data-test="input-panel"]');
await browser.close();
EOF
node "$outdir/check.mjs" "$shots"
kill "$(cat "$outdir/http.pid")"
python3 - <<'PY' "$shots"
from pathlib import Path
import sys
shots = Path(sys.argv[1])
expected = {"overview.png", "selected-path.png", "custom-input-diagnostic.png", "mobile.png"}
found = {p.name for p in shots.iterdir()}
missing = expected - found
assert not missing, missing
print("screenshots ok")
PY
rm -rf "$outdir"
```

Expected: the DOM assertions pass, the screenshot set is complete, and the images are ready for the executor to inspect during the run for legibility, attractiveness, and correctness before committing. The pass/fail gate is still explicit: no horizontal overflow in key panels, diagnostics visible for missing input, and screenshots successfully captured for all required states.

**Step 4: Commit**

```bash
git add .trycycle-explorer.toml trycycle_explorer/simulate.py trycycle_explorer/assets/index.html trycycle_explorer/assets/app.js trycycle_explorer/assets/app.css
git commit -m "feat: add explorer diagnostics and visual polish"
```

### Task 5: Harden build outputs, failure reporting, and verification surfaces

**Files:**
- Modify: `trycycle_explorer/extract.py`
- Modify: `trycycle_explorer/simulate.py`
- Modify: `trycycle_explorer/site.py`
- Modify: `trycycle_explorer/cli.py`

**Why this task exists:** The approved strategy emphasized reproducible artifacts over silent failure. This task turns the explorer into a dependable tool instead of a demo by making drift and bad inputs obvious and by exposing enough machine-readable output to verify behavior without adding repo tests.

**Step 1: Write failing boundary probes**

Run:

```bash
tmpdir="$(mktemp -d /tmp/trycycle-explorer-boundary-XXXXXX)"
cat >"$tmpdir/bad-sidecar.toml" <<'EOF'
[[outcomes]]
from = "non-existent-gate"
id = "bad-edge"
label = "Broken"
to = "also-missing"
EOF
! python3 -m trycycle_explorer dump-model --repo . --sidecar "$tmpdir/bad-sidecar.toml" --output "$tmpdir/model.json"
! python3 -m trycycle_explorer build --repo . --sample does-not-exist --output "$tmpdir/site"
rm -rf "$tmpdir"
```

Expected: both commands fail, but today they will not fail with precise explorer-specific messages because the validation/reporting layer does not exist yet.

**Step 2: Implement explicit validation and machine-readable outputs**

Add these behaviors:

- `dump-model` validates that every sidecar edge points to a known gate and every sample id exists.
- `build` exits non-zero with clear stderr for sidecar drift, unknown samples, unreadable sample files, or impossible render states.
- `explorer-model.json` includes:
  - `generated_at`
  - `repo_root`
  - `gates`
  - `bindings`
  - `sample_inputs`
  - `diagnostics`
  - `provenance_palette`
- `app.js` renders fatal build diagnostics if the model contains validation failures instead of crashing silently.
- `dump-model` supports `--sample <id>` so verification can pin one scenario when needed.

**Step 3: Verify failure reporting and catastrophic-regression performance**

Run:

```bash
tmpdir="$(mktemp -d /tmp/trycycle-explorer-boundary-XXXXXX)"
cat >"$tmpdir/bad-sidecar.toml" <<'EOF'
[[outcomes]]
from = "non-existent-gate"
id = "bad-edge"
label = "Broken"
to = "also-missing"
EOF
! python3 -m trycycle_explorer dump-model --repo . --sidecar "$tmpdir/bad-sidecar.toml" --output "$tmpdir/model.json" 2>"$tmpdir/error.txt"
rg -n "non-existent-gate|also-missing|sidecar" "$tmpdir/error.txt"
/usr/bin/time -f '%e' python3 -m trycycle_explorer build --repo . --output "$tmpdir/site" >/dev/null
rm -rf "$tmpdir"
```

Expected:

- The bad-sidecar command exits non-zero and stderr names the bad gates explicitly.
- The timing command finishes comfortably under 10 seconds on this machine. Anything slower signals a broken extraction/render loop.

**Step 4: Commit**

```bash
git add trycycle_explorer/extract.py trycycle_explorer/simulate.py trycycle_explorer/site.py trycycle_explorer/cli.py
git commit -m "feat: harden explorer validation and artifacts"
```

### Task 6: Document usage and maintainer update paths

**Files:**
- Modify: `README.md`
- Create: `docs/trycycle-explorer.md`

**Why this task exists:** The app is only useful if maintainers know how it stays synced with the repo and users know how to run it. The sidecar is intentionally small but manual; it needs explicit ownership and update instructions.

**Step 1: Write a failing documentation probe**

Run:

```bash
rg -n "trycycle explorer|\\.trycycle-explorer\\.toml|python3 -m trycycle_explorer" README.md docs/trycycle-explorer.md
```

Expected: no matches, because the explorer documentation does not exist yet.

**Step 2: Document build, serve, and sidecar maintenance**

Update `README.md` with a short “Trycycle Explorer” section that covers:

- build command: `python3 -m trycycle_explorer build --repo . --output /tmp/trycycle-explorer`
- local serve command: `python3 -m http.server 4173 --directory /tmp/trycycle-explorer`
- what the explorer is for: inspecting gates, outcomes, prompts, provenance, and rerender diffs

Create `docs/trycycle-explorer.md` with:

- the source-of-truth hierarchy:
  - `SKILL.md`
  - `subagents/*.md`
  - `docs/trycycle-information-flow.dot`
  - `.trycycle-explorer.toml`
- when the sidecar must be updated
- sample input file format
- output artifact list
- the disposable verification commands from Tasks 3 through 5

**Step 3: Verify the docs match the product**

Run:

```bash
python3 -m trycycle_explorer build --repo . --output /tmp/trycycle-explorer-doc-check
rg -n "python3 -m trycycle_explorer build|\\.trycycle-explorer\\.toml|explorer-model\\.json" README.md docs/trycycle-explorer.md
rm -rf /tmp/trycycle-explorer-doc-check
```

Expected: the build command succeeds and the docs contain the commands and artifacts the implementation now actually ships.

**Step 4: Commit**

```bash
git add README.md docs/trycycle-explorer.md
git commit -m "docs: add trycycle explorer usage and maintenance guide"
```

### Task 7: Final end-to-end verification in the worktree

**Files:**
- Modify: none

**Why this task exists:** This repo forbids committed tests, so the final quality bar must come from production-surface verification in this worktree. Run the full build, scenario interactions, screenshots, and failure probes one last time after all commits land.

**Step 1: Build the final static site**

Run:

```bash
final_dir="$(mktemp -d /tmp/trycycle-explorer-final-XXXXXX)"
python3 -m trycycle_explorer build --repo . --output "$final_dir/site"
```

Expected: the final site build succeeds with no stderr.

**Step 2: Run the final browser scenario and screenshot capture**

Repeat the Task 4 Playwright script against `"$final_dir/site"` and keep the four screenshots.

Expected: all assertions pass and the four screenshots exist.

**Step 3: Run the final model and boundary probes**

Repeat the Task 2 model assertions and the Task 5 bad-sidecar failure probe.

Expected: the model assertions pass and the bad-sidecar probe still fails loudly and specifically.

**Step 4: Record the verification summary for the implementation report**

Capture the exact commands and outcomes from Steps 1 through 3 so the implementation subagent can paste them into `## Verification results`.

**Step 5: Commit if needed**

If the verification steps required any last-minute non-behavioral fix, commit it with an accurate message. If verification passes cleanly with no code changes, do not create a no-op commit.
