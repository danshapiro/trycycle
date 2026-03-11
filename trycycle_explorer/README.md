# Trycycle Explorer

`trycycle_explorer` builds a static web app for inspecting the real trycycle flow.

It reads:

- `SKILL.md` for the numbered gates and orchestration text
- `subagents/*.md` and `subskills/*.md` for prompt sources
- `docs/trycycle-information-flow.dot` for the documented flow graph
- `trycycle_explorer/explorer.toml` for the small amount of metadata the code cannot derive reliably, such as outcome labels, grouping, palette metadata, and bundled samples

The output is a static site. There is no backend.

## Build

Run from the repo root:

```bash
python3 -m trycycle_explorer build --repo . --output /tmp/trycycle-explorer
```

That writes:

- `/tmp/trycycle-explorer/index.html`
- `/tmp/trycycle-explorer/app.js`
- `/tmp/trycycle-explorer/app.css`
- `/tmp/trycycle-explorer/explorer-model.json`
- `/tmp/trycycle-explorer/vendor/markdown-lite.js`

## Serve

Serve the generated site with any static file server. For local use:

```bash
python3 -m http.server 4173 --directory /tmp/trycycle-explorer
```

Then open `http://127.0.0.1:4173/`.

## Use

The app is built around three main actions:

1. Pick a bundled sample from the sample selector.
2. Click a gate in the flow map, then click one of its outcomes.
3. Edit any binding field and press `Rerender`.

What you should see:

- The left panel shows the trycycle gates and the currently selected path.
- The flow panel also includes `Intro` and `Outro` blocks. `Intro` is all copy from `SKILL.md` before step 1. `Outro` is any copy after the numbered flow; if there is none, the app says so explicitly.
- The middle panel shows the current sample/custom bindings.
- The right panel shows the selected prompt source, builder-interface pills for the current prompt, a markdown preview, the raw markdown, active diagnostics, and a before/after diff after rerenders.
- Every large text box has an `Expand` button. For input fields it opens a large editable modal that syncs back to the inline field. For rendered/read-only panels it opens a large read-only modal. Use `Close` or click outside the modal to dismiss it.

The builder-interface pills come from the real prompt-dispatch lines in `SKILL.md`. They expose caller-visible constraints such as:

- `Requires <task_input_json>` when the builder is told to enforce a non-empty tag.
- `Ignore placeholders in <task_input_json>` when the builder is told to ignore placeholder-like text inside that tag during rendered-prompt scanning.

## Before / After

The `Before / after` panel compares two prompt renders:

- `Before` is the previous rendered prompt markdown snapshot.
- `After` is the current rendered prompt markdown snapshot.

The snapshot is replaced every time you press `Rerender` or switch to a different gate or outcome. Changing the selected sample resets the comparison, because the app clears the previous snapshot when a new sample is loaded.

What the panel shows:

- The summary line counts how many lines were added and removed.
- `+` means a line exists only in the current render.
- `−` means a line existed in the previous render but not in the current one.
- `·` means the line is unchanged context.

What it is for:

- See whether editing a binding actually changed the prompt you care about.
- Spot accidental prompt regressions when a line disappears.
- Confirm that changing a path or outcome switched the injected prompt content you expected.

What it is not:

- It is not a semantic diff or a quality score.
- It does not compare rendered HTML.
- It does not decide whether the new prompt is better; it only shows the line-by-line markdown delta.

The raw markdown source is color-coded by provenance:

- `template-text`
- `user-input`
- `derived-path`
- `sidecar-overlay`
- `missing-binding`

If you clear a required field, the explorer should show a visible diagnostic instead of silently dropping the content:

- `missing-binding` when a placeholder value is absent
- `missing-required-tag` when the rendered prompt does not contain a required tag at all
- `empty-required-tag` when the rendered prompt contains the tag but its body is blank after trimming whitespace

Missing placeholder values still render as `<<MISSING:...>>` in the raw prompt so you can see exactly where the render broke.

## Samples And Custom Input

Bundled samples live in `samples/`:

- `simple-feature`
- `plan-review-loop`
- `post-review-fix`

You can start from a sample, then edit the fields directly in the browser to simulate a custom input set.

## CLI

The module exposes two subcommands:

Build the site:

```bash
python3 -m trycycle_explorer build --repo . --output /tmp/trycycle-explorer
```

Dump the extracted model without building the site:

```bash
python3 -m trycycle_explorer dump-model --repo . --output /tmp/trycycle-explorer-model.json
```

Useful flags:

- `--sample <id>` limits the build or dumped model to a single bundled sample.
- `--sidecar <path>` overlays a TOML config on top of `trycycle_explorer/explorer.toml`.

Example:

```bash
python3 -m trycycle_explorer dump-model --repo . --sample simple-feature --output /tmp/simple-feature-model.json
```

## Updating It

If the trycycle flow changes and the explorer looks wrong, update in this order:

1. Fix extraction if the new information is already present in repo sources.
2. Update `explorer.toml` only for metadata the extractor still cannot derive.
3. Update or add bundled sample JSON under `samples/` if you need new walkthrough scenarios.

## Quick Checks

Build smoke check:

```bash
python3 -m trycycle_explorer build --repo . --output /tmp/trycycle-explorer-check
```

Unknown sample should fail:

```bash
python3 -m trycycle_explorer build --repo . --sample does-not-exist --output /tmp/trycycle-explorer-check
```

Minimal mobile screenshot capture with the local server running:

```bash
npx playwright screenshot --channel chrome --viewport-size 390,844 http://127.0.0.1:4173/ /tmp/trycycle-explorer-mobile.png
```
