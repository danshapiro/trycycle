# World-Class GitHub Page Implementation Plan

> **For agentic workers:** REQUIRED: Use trycycle-executing to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the trycycle GitHub repo page from a plain text README into a polished, visually compelling presence that signals craft, confidence, and credibility -- matching the aesthetic of top indie developer tool repos.

**Architecture:** Copy the user-supplied `trycycle.png` banner into the repo at `assets/trycycle-banner.png`, create a 1280x640 social preview derived from it, rewrite `README.md` with banner image, shield badges, tightened prose, and the same charming human/agent install framing. Add repo metadata guidance (description, topics) as comments in the README header so the maintainer can set them in GitHub settings. Testing uses `gh api /markdown` to render the README to HTML, then Playwright to screenshot it for visual verification.

**Tech Stack:** GitHub-flavored Markdown, HTML `<picture>` element, shields.io badges, Python (Pillow) for social preview generation, Playwright for screenshot testing

---

## Design decisions (with justification)

### Banner placement
The banner image (`trycycle.png`, 778x237, black line drawing on white) goes at the very top of README.md as a centered `<p align="center"><img>` block. The image is a compact horizontal lockup (illustration left, "Trycycle" text right) and should not be stretched beyond its natural size. We set `height="120"` to keep the banner compact -- tall enough to be clear, short enough not to dominate the viewport.

**Justification:** The user explicitly chose layout A (illustration left, text right, classic) and asked for "a small image next to the text, so it makes a banner - not super tall." The PNG already contains both illustration and text as one unit, so we render it as a single `<img>` element.

### Badge selection and order
Five badges, in this order:
1. **MIT License** -- `https://img.shields.io/badge/license-MIT-blue`
2. **Latest release** -- `https://img.shields.io/github/v/tag/danshapiro/trycycle?label=release&color=green`
3. **PRs Welcome** -- `https://img.shields.io/badge/PRs-welcome-brightgreen`
4. **Built for Claude Code** -- custom shield with Anthropic logo
5. **Works with Codex CLI** -- custom shield with OpenAI logo

**Justification:** The user approved this badge set. License and release signal project health. PRs Welcome signals openness. The "Built for" and "Works with" badges signal ecosystem membership, which the user specifically requested.

### Social preview image (1280x640)
Generated via a Python script (`scripts/generate-social-preview.py`) that centers the banner illustration on a warm off-white (#FAFAF8) background at the social preview dimensions (1280x640). This is the image that appears when the repo URL is shared on Twitter/Slack/Discord.

**Justification:** GitHub's social preview is the single highest-design-freedom surface. Every top repo has one. The off-white background matches the line-drawing aesthetic and avoids stark white, which looks washed out in dark-mode social feeds.

### README structure
```
1. Banner image (centered)
2. One-liner (centered, italic)
3. Badges (centered)
4. --- divider
5. Installing Trycycle (human/agent split, tightened)
6. Using Trycycle (trimmed)
7. How it works (the hill-climber paragraph -- the hook)
8. Credits
```

**Justification:** The user approved this structure. Key changes from current README: visual identity at top, badges, tighter prose. The human/agent install framing stays because the user called it charming. "How it works" stays in the same relative position (it was already after install/usage) because the hill-climber concept is the differentiation.

### Prose tightening rules
- Same content, fewer words
- Remove redundant phrases ("for example", "in other words")
- Keep the personality and voice
- Do not add new content or features not discussed
- Do not remove any section

### Files NOT created
- No `.github/` directory (user said no FUNDING.yml, and issue templates / CONTRIBUTING are premature)
- No `.gitattributes` (language bar reclassification was not requested)
- No flow diagram (banner communicates the concept)
- No terminal recording (tool is invoked by typing one word)

### Repo metadata (not file changes)
The README will include an HTML comment at the top documenting the recommended repo description and topics for the maintainer to set in GitHub Settings > General. These are:
- **Description:** `A skill that plans, strengthens, and reviews your code -- automatically.`
- **Topics:** `claude-code`, `codex-cli`, `ai-coding`, `code-review`, `autonomous-agents`, `ai-skill`, `hill-climbing`

---

## File structure

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `assets/trycycle-banner.png` | Copy of user's `trycycle.png` at original resolution |
| Create | `assets/social-preview.png` | 1280x640 social preview derived from banner |
| Create | `scripts/generate-social-preview.py` | One-shot script to generate social preview from banner |
| Modify | `README.md` | Complete rewrite with banner, badges, tightened prose |
| Verify | `.gitignore` | Confirm `assets/` and `scripts/` are not ignored (modify only if needed) |

---

### Task 1: Add banner image to repo

**Files:**
- Create: `assets/trycycle-banner.png`

- [ ] **Step 1: Create assets directory and copy banner**

```bash
mkdir -p assets
cp "/mnt/d/Users/Dan/Downloads/trycycle.png" assets/trycycle-banner.png
```

- [ ] **Step 2: Verify the image is valid and has expected dimensions**

```bash
python3 -c "
from PIL import Image
img = Image.open('assets/trycycle-banner.png')
assert img.size == (778, 237), f'Unexpected size: {img.size}'
assert img.mode == 'RGB', f'Unexpected mode: {img.mode}'
print(f'OK: {img.size[0]}x{img.size[1]} {img.mode}')
"
```

Expected: `OK: 778x237 RGB`

- [ ] **Step 3: Commit**

```bash
git add assets/trycycle-banner.png
git commit -m "feat: add trycycle banner image"
```

---

### Task 2: Generate social preview image

**Files:**
- Create: `scripts/generate-social-preview.py`
- Create: `assets/social-preview.png`

- [ ] **Step 1: Write the social preview generation script**

Create `scripts/generate-social-preview.py`:

```python
#!/usr/bin/env python3
"""Generate a 1280x640 social preview image for GitHub.

Centers the trycycle banner on a warm off-white background.
"""

import os
from PIL import Image

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
BANNER_PATH = os.path.join(REPO_ROOT, "assets", "trycycle-banner.png")
OUTPUT_PATH = os.path.join(REPO_ROOT, "assets", "social-preview.png")

PREVIEW_WIDTH = 1280
PREVIEW_HEIGHT = 640
BG_COLOR = (250, 250, 248)  # warm off-white #FAFAF8

def main():
    banner = Image.open(BANNER_PATH).convert("RGBA")

    # Scale banner to fit comfortably within preview (60% of width, maintain aspect)
    target_width = int(PREVIEW_WIDTH * 0.6)
    scale = target_width / banner.width
    target_height = int(banner.height * scale)

    # Don't upscale beyond 2x to avoid blurriness
    if scale > 2.0:
        scale = 2.0
        target_width = int(banner.width * scale)
        target_height = int(banner.height * scale)

    banner_resized = banner.resize((target_width, target_height), Image.LANCZOS)

    # Create background and paste centered
    preview = Image.new("RGB", (PREVIEW_WIDTH, PREVIEW_HEIGHT), BG_COLOR)
    x = (PREVIEW_WIDTH - target_width) // 2
    y = (PREVIEW_HEIGHT - target_height) // 2
    preview.paste(banner_resized, (x, y), banner_resized if banner_resized.mode == "RGBA" else None)

    preview.save(OUTPUT_PATH, "PNG", optimize=True)
    print(f"Social preview saved to {OUTPUT_PATH} ({PREVIEW_WIDTH}x{PREVIEW_HEIGHT})")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the script and verify output**

```bash
python3 scripts/generate-social-preview.py
```

Expected: `Social preview saved to .../assets/social-preview.png (1280x640)`

```bash
python3 -c "
from PIL import Image
img = Image.open('assets/social-preview.png')
assert img.size == (1280, 640), f'Unexpected size: {img.size}'
print(f'OK: {img.size[0]}x{img.size[1]}')
"
```

Expected: `OK: 1280x640`

- [ ] **Step 3: Commit**

```bash
git add scripts/generate-social-preview.py assets/social-preview.png
git commit -m "feat: add social preview image and generation script"
```

---

### Task 3: Rewrite README.md

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Write the new README**

Replace the entire contents of `README.md` with the following:

```markdown
<!-- GitHub repo settings (set manually in Settings > General):
  Description: A skill that plans, strengthens, and reviews your code -- automatically.
  Topics: claude-code, codex-cli, ai-coding, code-review, autonomous-agents, ai-skill, hill-climbing
  Social preview: upload assets/social-preview.png
-->

<p align="center">
  <img src="assets/trycycle-banner.png" height="120" alt="Trycycle" />
</p>

<p align="center">
  <em>A skill for Claude Code and Codex CLI that plans, strengthens, and reviews your code -- automatically.</em>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="MIT License" /></a>
  <a href="https://github.com/danshapiro/trycycle/releases"><img src="https://img.shields.io/github/v/tag/danshapiro/trycycle?label=release&color=green" alt="Latest Release" /></a>
  <a href="https://github.com/danshapiro/trycycle/pulls"><img src="https://img.shields.io/badge/PRs-welcome-brightgreen" alt="PRs Welcome" /></a>
  <a href="https://github.com/anthropics/claude-code"><img src="https://img.shields.io/badge/built%20for-Claude%20Code-6B4FBB" alt="Built for Claude Code" /></a>
  <a href="https://github.com/openai/codex"><img src="https://img.shields.io/badge/works%20with-Codex%20CLI-412991" alt="Works with Codex CLI" /></a>
</p>

---

## Installing Trycycle

### If you are human

Tell your favorite coding agent (Claude Code, Codex CLI, etc.):

```
Read https://raw.githubusercontent.com/danshapiro/trycycle/main/README.md. Follow the installation instructions there.
```

### If you've been sent here by your human

Use this instead of a standard installation, or it won't work. Clone into your skills directory:

- **Claude Code:** `git clone https://github.com/danshapiro/trycycle.git ~/.claude/skills/trycycle`
- **Codex CLI:** `git clone https://github.com/danshapiro/trycycle.git ~/.codex/skills/trycycle`

Trycycle requires `python3` at runtime. Make sure it is installed and on your `PATH`.

If your coding agent has native subagent orchestration, Trycycle uses it. Otherwise, it falls back to a bundled stdlib-only Python runner.

Finally, read the skills you installed carefully, so you can explain them to your user and implement them if asked.

## Using Trycycle

Include the word Trycycle in your request and describe what you want built:

```
Use trycycle to add a dark mode toggle to the settings page.
```

Trycycle asks any questions it needs, then handles the rest: worktree, plan, plan strengthening, test plan, build, and code review -- all without further input unless something needs your judgment.

Works for anything from small features to large refactors, best when you have a clear goal and a codebase Trycycle can read and test.

## How it works

Trycycle is a hill climber. It writes a plan, then sends it to a fresh plan editor with the same task input and repo context. That editor either approves the plan unchanged or rewrites it, repeating up to five rounds. Once the plan is locked, Trycycle builds a test plan, builds the code, sends it to a fresh reviewer, fixes what the reviewer finds, and repeats that loop too (up to eight rounds). Each review uses a new reviewer with no memory of previous rounds, and each planning round spawns a fresh agent, so stale context never accumulates.

## Credits

Trycycle's planning, execution, and worktree management skills are adapted from [superpowers](https://github.com/obra/superpowers) by [Jesse Vincent](https://github.com/obra). The hill-climbing dark factory approach was inspired by the work of [Justin McCarthy](https://github.com/jmccarthy), [Jay Taylor](https://github.com/jaytaylor), and [Navan Chauhan](https://github.com/navanchauhan) at [StrongDM](https://github.com/strongdm).
```

- [ ] **Step 2: Verify the README renders valid markdown**

```bash
python3 -c "
content = open('README.md').read()
# Check required elements exist
assert 'trycycle-banner.png' in content, 'Missing banner image'
assert 'shields.io' in content or 'img.shields.io' in content, 'Missing badges'
assert 'Claude Code' in content, 'Missing Claude Code badge'
assert 'Codex CLI' in content, 'Missing Codex CLI badge'
assert 'hill climber' in content, 'Missing hill climber section'
assert 'Credits' in content, 'Missing credits'
assert 'If you are human' in content, 'Missing human install section'
assert 'sent here by your human' in content, 'Missing agent install section'
print('All required elements present')
"
```

Expected: `All required elements present`

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "feat: rewrite README with banner, badges, and tightened prose"
```

---

### Task 4: Verify .gitignore does not exclude new files

**Files:**
- Verify: `.gitignore`

- [ ] **Step 1: Check that assets/ and scripts/ are not gitignored**

```bash
git check-ignore assets/trycycle-banner.png assets/social-preview.png scripts/generate-social-preview.py
```

Expected: No output (none are ignored). If any are ignored, modify `.gitignore` to un-ignore them.

- [ ] **Step 2: Verify all new files are tracked**

```bash
git status --short
```

Expected: Clean working tree (everything committed in prior tasks).

---

### Task 5: Visual verification via rendered screenshot

**Files:**
- No files created; this is a verification-only task

- [ ] **Step 1: Render README to HTML using GitHub API**

```bash
gh api /markdown -f text="$(cat README.md)" -f mode=gfm -f context=danshapiro/trycycle > /tmp/trycycle-readme-rendered.html
```

- [ ] **Step 1b: Fix relative image paths for local rendering**

The GitHub API renders `src="assets/trycycle-banner.png"` as a relative path. When opened from `/tmp/`, Playwright cannot resolve it. Rewrite local asset references to absolute `file://` paths so the banner actually appears in the screenshot:

```bash
WORKTREE_ABS=$(cd . && pwd)
sed -i "s|src=\"assets/|src=\"file://${WORKTREE_ABS}/assets/|g" /tmp/trycycle-readme-rendered.html
```

Verify the rewrite worked:

```bash
grep -o 'src="file://[^"]*"' /tmp/trycycle-readme-rendered.html
```

Expected: `src="file:///home/user/code/trycycle/.worktrees/world-class-github-page/assets/trycycle-banner.png"`

- [ ] **Step 2: Wrap rendered HTML with GitHub-flavored CSS and capture screenshot**

Create a temporary HTML wrapper and use Playwright to screenshot it:

```bash
cat > /tmp/trycycle-readme-wrapper.html << 'HTMLEOF'
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    max-width: 896px;
    margin: 40px auto;
    padding: 0 20px;
    line-height: 1.5;
    color: #1f2328;
    background: #ffffff;
  }
  img { max-width: 100%; }
  a { color: #0969da; text-decoration: none; }
  h1, h2, h3 { border-bottom: 1px solid #d1d9e0; padding-bottom: 0.3em; }
  code { background: #f6f8fa; padding: 0.2em 0.4em; border-radius: 6px; font-size: 85%; }
  pre { background: #f6f8fa; padding: 16px; border-radius: 6px; overflow-x: auto; }
  pre code { background: none; padding: 0; }
  hr { border: none; border-top: 1px solid #d1d9e0; margin: 24px 0; }
  p { text-align: left; }
  p[align="center"] { text-align: center; }
</style>
</head>
<body>
HTMLEOF
cat /tmp/trycycle-readme-rendered.html >> /tmp/trycycle-readme-wrapper.html
echo "</body></html>" >> /tmp/trycycle-readme-wrapper.html
```

Then screenshot with Playwright:

```bash
npx playwright screenshot --full-page /tmp/trycycle-readme-wrapper.html /tmp/trycycle-readme-screenshot.png
```

- [ ] **Step 3: Examine the screenshot**

Open and visually inspect `/tmp/trycycle-readme-screenshot.png` to verify:
- Banner image is visible and properly centered at the top
- One-liner is visible below the banner
- Five badges are visible and properly centered
- Section structure matches the design (Install, Usage, How it works, Credits)
- Prose reads cleanly
- No broken images or rendering artifacts

- [ ] **Step 4: Check all links and image references resolve**

```bash
python3 -c "
import re, os

content = open('README.md').read()

# Check local file references
local_refs = re.findall(r'src=\"([^\"]+)\"', content)
local_refs += re.findall(r'\]\(([^)]+)\)', content)
local_files = [r for r in local_refs if not r.startswith('http')]

for path in local_files:
    if os.path.exists(path):
        print(f'  OK: {path}')
    else:
        print(f'  MISSING: {path}')
        raise FileNotFoundError(f'Referenced file not found: {path}')

print(f'All {len(local_files)} local references valid')
"
```

Expected: All local references valid.

- [ ] **Step 5: Dark mode check (optional but recommended)**

```bash
cat > /tmp/trycycle-readme-dark.html << 'HTMLEOF'
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    max-width: 896px;
    margin: 40px auto;
    padding: 0 20px;
    line-height: 1.5;
    color: #e6edf3;
    background: #0d1117;
  }
  img { max-width: 100%; }
  a { color: #4493f8; text-decoration: none; }
  h1, h2, h3 { border-bottom: 1px solid #3d444d; padding-bottom: 0.3em; color: #e6edf3; }
  code { background: #161b22; padding: 0.2em 0.4em; border-radius: 6px; font-size: 85%; }
  pre { background: #161b22; padding: 16px; border-radius: 6px; overflow-x: auto; }
  pre code { background: none; padding: 0; }
  hr { border: none; border-top: 1px solid #3d444d; margin: 24px 0; }
  p { text-align: left; }
  p[align="center"] { text-align: center; }
</style>
</head>
<body>
HTMLEOF
cat /tmp/trycycle-readme-rendered.html >> /tmp/trycycle-readme-dark.html
echo "</body></html>" >> /tmp/trycycle-readme-dark.html
npx playwright screenshot --full-page /tmp/trycycle-readme-dark.html /tmp/trycycle-readme-dark-screenshot.png
```

Examine `/tmp/trycycle-readme-dark-screenshot.png` to verify the black line-drawing banner is legible against a dark background. Since the PNG has a white/RGB background (not transparent), the banner will appear as a white rectangle on dark mode. This is acceptable -- it is how most repos handle it. If the user later wants a transparent PNG or an SVG with dark-mode support via `<picture>`, that is a separate enhancement.

---

## Post-implementation checklist

After all tasks are complete:

1. Run `git diff --name-only main...HEAD` and verify the changed files list is:
   - `README.md`
   - `assets/trycycle-banner.png`
   - `assets/social-preview.png`
   - `scripts/generate-social-preview.py`

2. Remind the user of manual GitHub settings to complete after merge:
   - **Settings > General > Social preview:** Upload `assets/social-preview.png`
   - **Settings > General > Description:** `A skill that plans, strengthens, and reviews your code -- automatically.`
   - **Settings > General > Topics:** `claude-code`, `codex-cli`, `ai-coding`, `code-review`, `autonomous-agents`, `ai-skill`, `hill-climbing`
