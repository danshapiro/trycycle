# World-Class GitHub Page — Test Plan

## Harness requirements

### GitHub Markdown rendering harness

- **What it does:** Renders `README.md` to HTML via `gh api /markdown`, rewrites relative asset paths to absolute `file://` URIs so local images resolve, wraps the result in a minimal GitHub-flavored CSS page.
- **What it exposes:** A self-contained HTML file at `/tmp/trycycle-readme-wrapper.html` (light) and `/tmp/trycycle-readme-dark.html` (dark) that Playwright can screenshot.
- **Estimated complexity:** Low — shell pipeline, already specified in the implementation plan (Task 5 steps 1–2).
- **Tests that depend on it:** T1 (rendered README screenshot), T2 (dark-mode legibility), T5 (banner visible in rendered output).

### Screenshot capture harness

- **What it does:** Uses `npx playwright screenshot --full-page` to capture the rendered HTML to PNG.
- **What it exposes:** Full-page PNG screenshots at known paths for visual inspection.
- **Estimated complexity:** Trivial — single CLI call.
- **Tests that depend on it:** T1, T2.

---

## Test plan

### T1 — Rendered README looks correct in light mode

- **Type:** scenario
- **Disposition:** new
- **Harness:** GitHub Markdown rendering harness + Screenshot capture harness
- **Preconditions:** All implementation tasks (1–4) are complete. `README.md`, `assets/trycycle-banner.png`, and `assets/social-preview.png` exist and are committed. Working directory is the worktree root.
- **Actions:**
  1. Render README to HTML: `gh api /markdown -f text="$(cat README.md)" -f mode=gfm -f context=danshapiro/trycycle > /tmp/trycycle-readme-rendered.html`
  2. Rewrite relative asset paths to absolute `file://` URIs using the worktree's absolute path.
  3. Wrap rendered HTML in a light-mode GitHub-flavored CSS shell at `/tmp/trycycle-readme-wrapper.html`.
  4. Screenshot: `npx playwright screenshot --full-page /tmp/trycycle-readme-wrapper.html /tmp/trycycle-readme-screenshot.png`
  5. Visually inspect the screenshot (the implementation subagent reads the PNG).
- **Expected outcome:**
  - Banner image is visible at the top, centered, at a compact height (not dominating the viewport). *Source of truth: user direction ("small image next to the text, so it makes a banner - not super tall") and plan design decision (height="120").*
  - One-liner tagline is visible below the banner, centered and italic. *Source of truth: plan README structure.*
  - Five badges are visible on one line below the tagline: MIT, release, PRs welcome, Built for Claude Code, Works with Codex CLI. *Source of truth: user-approved badge set.*
  - Section headings appear in order: Installing Trycycle, Using Trycycle, How it works, Credits. *Source of truth: plan README structure.*
  - No broken image icons, no rendering artifacts, no raw HTML visible. *Source of truth: basic rendering correctness.*
- **Interactions:** Depends on `gh api /markdown` (GitHub API) and Playwright (headless Chromium). The GitHub API call requires authentication via `gh auth`.

### T2 — Banner is legible in dark mode

- **Type:** scenario
- **Disposition:** new
- **Harness:** GitHub Markdown rendering harness (dark variant) + Screenshot capture harness
- **Preconditions:** T1's rendered HTML (`/tmp/trycycle-readme-rendered.html`) already exists with rewritten asset paths.
- **Actions:**
  1. Wrap the same rendered HTML in a dark-mode CSS shell at `/tmp/trycycle-readme-dark.html` (background: #0d1117, text: #e6edf3).
  2. Screenshot: `npx playwright screenshot --full-page /tmp/trycycle-readme-dark.html /tmp/trycycle-readme-dark-screenshot.png`
  3. Visually inspect the dark-mode screenshot.
- **Expected outcome:**
  - The banner is visible and legible — the black line drawing on its white/RGB background appears as a white rectangle on the dark page. This is acceptable per the plan's design decision. *Source of truth: plan Task 5 step 5 note on dark mode.*
  - Text content and badges remain readable against the dark background. *Source of truth: basic accessibility/contrast.*
  - No broken images or rendering artifacts.
- **Interactions:** Same as T1 minus the `gh api` call.

### T3 — README contains all required content elements

- **Type:** invariant
- **Disposition:** new
- **Harness:** Direct file read + Python assertions
- **Preconditions:** `README.md` has been rewritten.
- **Actions:**
  1. Read `README.md` content.
  2. Assert each required element is present:
     - Banner image reference: `trycycle-banner.png`
     - Shields.io badge URLs: `img.shields.io`
     - Claude Code badge: `Claude Code`
     - Codex CLI badge: `Codex CLI`
     - Hill climber section: `hill climber`
     - Credits section: `Credits`
     - Human install framing: `If you are human`
     - Agent install framing: `sent here by your human`
     - Repo metadata HTML comment: `GitHub repo settings`
     - Social preview mention in comment: `social-preview.png`
- **Expected outcome:** All assertions pass. *Source of truth: user-approved design (banner, badges, charming framing) and plan README structure (metadata comment, all sections).*
- **Interactions:** None — pure file content check.

### T4 — All local file references in README resolve

- **Type:** invariant
- **Disposition:** new
- **Harness:** Python regex extraction + `os.path.exists`
- **Preconditions:** All implementation tasks complete. Banner and social preview exist in `assets/`.
- **Actions:**
  1. Extract all `src="..."` and `](...)` references from `README.md`.
  2. Filter to local (non-HTTP) references.
  3. Assert each local path resolves to an existing file relative to the worktree root.
- **Expected outcome:** Every local reference (at minimum `assets/trycycle-banner.png` and `LICENSE`) resolves. *Source of truth: the README references files that must ship with the repo.*
- **Interactions:** None — pure filesystem check.

### T5 — Banner image has correct dimensions and format

- **Type:** boundary
- **Disposition:** new
- **Harness:** Python Pillow
- **Preconditions:** `assets/trycycle-banner.png` has been copied from the source.
- **Actions:**
  1. Open `assets/trycycle-banner.png` with Pillow.
  2. Assert dimensions are 778x237.
  3. Assert mode is RGB.
- **Expected outcome:** `778x237 RGB`. *Source of truth: plan Task 1 step 2, verified by plan editor round 2 which confirmed the source image dimensions.*
- **Interactions:** None — pure image metadata check.

### T6 — Social preview image has correct dimensions

- **Type:** boundary
- **Disposition:** new
- **Harness:** Python Pillow
- **Preconditions:** `scripts/generate-social-preview.py` has been run and `assets/social-preview.png` exists.
- **Actions:**
  1. Open `assets/social-preview.png` with Pillow.
  2. Assert dimensions are 1280x640.
- **Expected outcome:** `1280x640`. *Source of truth: GitHub social preview spec (1280x640) and plan Task 2.*
- **Interactions:** None — pure image metadata check.

### T7 — New files are not gitignored

- **Type:** invariant
- **Disposition:** new
- **Harness:** `git check-ignore`
- **Preconditions:** All files created and committed.
- **Actions:**
  1. Run `git check-ignore assets/trycycle-banner.png assets/social-preview.png scripts/generate-social-preview.py README.md`.
- **Expected outcome:** No output (exit code 1) — none of the new/modified files are ignored. *Source of truth: plan Task 4 — these files must be tracked.*
- **Interactions:** Depends on `.gitignore` content.

### T8 — Changed file list matches plan expectations

- **Type:** invariant
- **Disposition:** new
- **Harness:** `git diff --name-only`
- **Preconditions:** All implementation tasks complete and committed.
- **Actions:**
  1. Run `git diff --name-only main...HEAD`.
  2. Assert the list contains exactly:
     - `README.md`
     - `assets/social-preview.png`
     - `assets/trycycle-banner.png`
     - `docs/plans/2026-03-16-world-class-github-page.md` (the plan itself)
     - `docs/plans/2026-03-16-world-class-github-page-test-plan.md` (this test plan)
     - `scripts/generate-social-preview.py`
  3. Assert no unexpected files are changed.
- **Expected outcome:** Only the expected files appear. *Source of truth: plan file structure table, plus the plan and test plan docs committed during this session.*
- **Interactions:** Depends on git history.

### T9 — Content preservation: no sections lost from original README

- **Type:** regression
- **Disposition:** new
- **Harness:** Python string search
- **Preconditions:** `README.md` has been rewritten.
- **Actions:**
  1. Extract section headings from the new README.
  2. Verify these key sections are present: "Installing Trycycle", "If you are human", "If you've been sent here by your human", "Using Trycycle", "How it works", "Credits".
  3. Verify key content phrases survived: "hill climber", "superpowers", "Jesse Vincent", "StrongDM", "git clone", "~/.claude/skills/trycycle", "~/.codex/skills/trycycle".
- **Expected outcome:** All sections and key phrases present. *Source of truth: user direction to keep the charming framing and all sections; plan prose-tightening rules ("do not remove any section").*
- **Interactions:** None — pure content check.

---

## Coverage summary

### Covered

| Area | Tests | Notes |
|------|-------|-------|
| Visual rendering (light) | T1 | Full-page screenshot of rendered README |
| Visual rendering (dark) | T2 | Dark-mode legibility of banner |
| Content completeness | T3, T9 | All required elements and sections present |
| Asset integrity | T5, T6 | Banner and social preview dimensions/format |
| Link/reference validity | T4 | All local file references resolve |
| Git hygiene | T7, T8 | No files gitignored, changed-file list matches plan |

### Explicitly excluded (per agreed strategy)

| Area | Reason | Risk |
|------|--------|------|
| External URL validation (shields.io, GitHub links) | HTTP HEAD checks against third-party services are flaky in CI and not part of the agreed strategy. | Low — these are well-known static URLs. If shields.io is down, badges degrade gracefully (show alt text). |
| Pixel-perfect rendering fidelity vs. actual GitHub | The `gh api /markdown` rendering is high-fidelity but not pixel-identical to the GitHub web UI. Agreed as acceptable in the strategy. | Low — content and structure are accurate; minor CSS differences do not affect the user's goals. |
| Social preview upload verification | Requires manual upload to GitHub Settings; cannot be automated. | None — the plan already includes a post-implementation reminder for the user. |
| Repo description and topics | Set via GitHub Settings UI, not automatable through file changes. | None — documented in README HTML comment and post-implementation checklist. |
