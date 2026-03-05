# Create trycycle repo — implementation plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a public GitHub repo `danshapiro/trycycle` containing the trycycle skill files, a README written with the writing-prose skill, and an MIT license.

**Architecture:** Copy the trycycle skill files into the repo root preserving their directory structure (`SKILL.md` and `agents/openai.yaml`). Write a README using the writing-prose skill (with prose lint pass). Add an MIT LICENSE. Push to GitHub as a public repo.

**Tech Stack:** Git, GitHub CLI (`gh`), Python 3 (for prose lint), Markdown

---

### Task 1: Copy skill files into the repo

**Files:**
- Create: `SKILL.md`
- Create: `agents/openai.yaml`

**Step 1: Create the agents directory**

```bash
mkdir -p /home/user/code/trycycle/.worktrees/create-trycycle-repo/agents
```

**Step 2: Copy SKILL.md**

```bash
cp /home/user/.claude/skills/trycycle/SKILL.md /home/user/code/trycycle/.worktrees/create-trycycle-repo/SKILL.md
```

**Step 3: Copy agents/openai.yaml**

```bash
cp /home/user/.claude/skills/trycycle/agents/openai.yaml /home/user/code/trycycle/.worktrees/create-trycycle-repo/agents/openai.yaml
```

**Step 4: Verify files exist and match originals**

```bash
diff /home/user/.claude/skills/trycycle/SKILL.md /home/user/code/trycycle/.worktrees/create-trycycle-repo/SKILL.md
diff /home/user/.claude/skills/trycycle/agents/openai.yaml /home/user/code/trycycle/.worktrees/create-trycycle-repo/agents/openai.yaml
```

Expected: No output (files are identical).

**Step 5: Commit**

```bash
cd /home/user/code/trycycle/.worktrees/create-trycycle-repo
git add SKILL.md agents/openai.yaml
git commit -m "feat: add trycycle skill files"
```

---

### Task 2: Create MIT LICENSE file

**Files:**
- Create: `LICENSE`

**Step 1: Write the LICENSE file**

Create `LICENSE` with the MIT license text. The author is Dan Shapiro, year 2026.

```text
MIT License

Copyright (c) 2026 Dan Shapiro

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

**Step 2: Verify the file**

```bash
head -3 /home/user/code/trycycle/.worktrees/create-trycycle-repo/LICENSE
```

Expected: First three lines are `MIT License`, blank line, `Copyright (c) 2026 Dan Shapiro`.

**Step 3: Commit**

```bash
cd /home/user/code/trycycle/.worktrees/create-trycycle-repo
git add LICENSE
git commit -m "feat: add MIT license"
```

---

### Task 3: Write README.md using writing-prose skill

**Files:**
- Create: `README.md`

This task requires following the `writing-prose` skill for all prose content. The README must satisfy these constraints from the user:

1. Friendly, approachable tone for someone who is new to Claude Code or Codex CLI — without using words like "novice" or "beginner."
2. Clear installation and usage instructions.
3. Superpowers installation as a prerequisite, with a note that superpowers are useful on their own and may activate outside trycycle.
4. Only the LAST paragraph explains how trycycle works (it is a hill climber that iterates on plans and code through multiple review rounds).
5. Must pass `writing-prose` prose lint (`python3 /home/user/.claude/skills/writing-prose/scripts/prose_lint.py --file <path>`).

**Step 1: Draft the README content**

Write the README to a temp file first. The content structure should be:

- **Title and one-line description** — what trycycle does in plain terms.
- **Prerequisites section** — installing superpowers (with note about general usefulness), with platform-specific install commands for Claude Code, Codex, and Cursor.
- **Installation section** — how to install the trycycle skill itself (copy to `~/.claude/skills/trycycle/` or clone the repo there).
- **Usage section** — how to invoke trycycle (just ask Claude Code / Codex to "use trycycle to [do something]").
- **Final paragraph** — how it works: trycycle is a hill climber that plans, builds, reviews, and iterates.

Key writing-prose rules to follow:
- Sentence case headings (not title case).
- No boldface overuse, no emoji, no "here is a", no promotional language.
- No "serves as", "stands as" — use "is/are/has" instead.
- No "crucial", "enhance", "showcase", "pivotal", "highlight", "delve", "fostering", etc.
- No ritual conclusions ("in summary", "overall").
- No rule-of-three adjective patterns.
- No "not only...but also" constructions.
- All prose must pass the lint script.

Draft to temp file:

```bash
cat > /tmp/trycycle-readme-draft.md << 'DRAFT'
[README content here — see Step 1a below for the actual text]
DRAFT
```

**Step 1a: README content**

The README content (to be written with writing-prose compliance). All code blocks will be wrapped in `<!-- prose-lint: ignore-start -->` / `<!-- prose-lint: ignore-end -->` or fenced code blocks (which are auto-excluded from lint). Headings must be sentence case. No boldface in prose paragraphs.

Structure:

```markdown
# trycycle

A skill for Claude Code and Codex CLI that runs your work through multiple rounds of planning, building, and review — automatically.

## Prerequisites

Trycycle depends on superpowers, a plugin that gives Claude Code and Codex CLI the ability to spawn subagents, manage worktrees, and run structured development loops. Superpowers is generally useful beyond trycycle, and once installed, it may activate for other tasks too.

Install superpowers for your platform:

[code block with Claude Code install command]
[code block with Codex install command]
[code block with Cursor install command]

## Installing trycycle

Clone this repo into your Claude skills directory:

[code block with clone command]

If you already have a skills directory with other skills in it, just clone into it:

[code block]

## Using trycycle

[2-3 short paragraphs on how to invoke it]

## How it works

[Single paragraph: hill climber, iterates plans through review, builds code, iterates code through review]
```

**Step 2: Write the draft to temp file**

Write the actual README text to `/tmp/trycycle-readme-draft.md`.

**Step 3: Run prose lint**

```bash
python3 /home/user/.claude/skills/writing-prose/scripts/prose_lint.py --file /tmp/trycycle-readme-draft.md
```

Expected: `OK: no lint violations` (exit code 0).

If lint fails, revise the prose in the temp file and re-lint. Repeat until clean.

**Step 4: Copy final draft to repo**

```bash
cp /tmp/trycycle-readme-draft.md /home/user/code/trycycle/.worktrees/create-trycycle-repo/README.md
```

**Step 5: Verify final README is in place**

```bash
cat /home/user/code/trycycle/.worktrees/create-trycycle-repo/README.md
```

**Step 6: Commit**

```bash
cd /home/user/code/trycycle/.worktrees/create-trycycle-repo
git add README.md
git commit -m "feat: add README with installation and usage instructions"
```

---

### Task 4: Create public GitHub repo and push

**Step 1: Verify all files are committed**

```bash
cd /home/user/code/trycycle/.worktrees/create-trycycle-repo
git status --short
git log --oneline
```

Expected: Clean status, commits for skill files, LICENSE, and README.

**Step 2: Check if remote already exists**

```bash
cd /home/user/code/trycycle
git remote -v
```

If no remote named `origin` exists, or it points elsewhere, set it up in Step 3.

**Step 3: Create the GitHub repo**

```bash
cd /home/user/code/trycycle
gh repo create danshapiro/trycycle --public --source=. --push
```

If the remote already exists, just push:

```bash
cd /home/user/code/trycycle/.worktrees/create-trycycle-repo
git push origin create-trycycle-repo
```

**Step 4: Merge to main and push**

First, merge the feature branch into main within the worktree workflow:

```bash
cd /home/user/code/trycycle
git merge --ff-only create-trycycle-repo
git push origin main
```

**Step 5: Verify on GitHub**

```bash
gh repo view danshapiro/trycycle --web
```

Or verify with:

```bash
gh repo view danshapiro/trycycle --json name,visibility,url
```

Expected: Repo is public, URL is `https://github.com/danshapiro/trycycle`.

---

### Task 5: Clean up

**Step 1: Remove the worktree**

```bash
cd /home/user/code/trycycle
git worktree remove .worktrees/create-trycycle-repo
```

**Step 2: Delete the branch**

```bash
cd /home/user/code/trycycle
git branch -d create-trycycle-repo
```

**Step 3: Final verification**

```bash
cd /home/user/code/trycycle
git log --oneline -5
ls -la
```

Expected: Main branch has all commits. Files present: `.gitignore`, `SKILL.md`, `agents/openai.yaml`, `LICENSE`, `README.md`.
