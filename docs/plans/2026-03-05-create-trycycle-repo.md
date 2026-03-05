# Create trycycle repo -- implementation plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a public GitHub repo `danshapiro/trycycle` containing the trycycle skill files, a README written with the writing-prose skill, and an MIT license.

**Architecture:** Copy the trycycle skill files into the repo root preserving their directory structure (`SKILL.md` and `agents/openai.yaml`). Write a README using the writing-prose skill (with prose lint pass). Add an MIT LICENSE. Create the GitHub repo, merge the feature branch to main, then push.

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

Create `LICENSE` with the following exact content:

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

REQUIRED SUB-SKILL: Use `writing-prose` for all prose content in this task.

**Files:**
- Create: `README.md`

This task produces a README that satisfies these constraints:

1. Friendly, approachable tone for someone who is new to Claude Code or Codex CLI -- without using words like "novice" or "beginner."
2. Clear installation and usage instructions.
3. Superpowers installation as a prerequisite, with a note that superpowers are useful on their own and may activate outside trycycle.
4. Only the LAST paragraph explains how trycycle works (it is a hill climber that iterates on plans and code through multiple review rounds).
5. Must pass the `writing-prose` prose lint script.
6. All URLs and link-like text must be inside fenced code blocks or inline code spans to avoid triggering lint bracket patterns.

**Step 1: Write the README draft to a temp file**

Write the following exact content to `/tmp/trycycle-readme-draft.md`:

````markdown
# trycycle

A skill for Claude Code and Codex CLI that runs your work through multiple rounds of planning, building, and review -- automatically.

## Prerequisites

Trycycle depends on superpowers, a plugin that gives Claude Code and Codex CLI the ability to spawn subagents, manage worktrees, and run structured development loops. Superpowers is useful on its own, and once installed, it may activate for tasks beyond trycycle.

Install superpowers for your platform:

Claude Code -- run these two commands in the Claude Code prompt:

```
/plugin marketplace add obra/superpowers-marketplace
/plugin install superpowers@superpowers-marketplace
```

Codex CLI -- tell Codex to fetch and follow the install instructions:

```
Fetch and follow instructions from https://raw.githubusercontent.com/obra/superpowers/refs/heads/main/.codex/INSTALL.md
```

Cursor -- run this command in the Cursor prompt:

```
/plugin-add superpowers
```

## Installing trycycle

Clone this repo into your Claude Code skills directory:

```bash
git clone https://github.com/danshapiro/trycycle.git ~/.claude/skills/trycycle
```

If you already have other skills in that directory, just clone into it directly -- the path above will create the `trycycle` subdirectory for you.

To update later, pull the latest:

```bash
git -C ~/.claude/skills/trycycle pull
```

## Using trycycle

Once superpowers and trycycle are both installed, you can use trycycle from any Claude Code or Codex CLI session. Just tell Claude what you want and include the word trycycle in your request. For example:

```
Use trycycle to add a dark mode toggle to the settings page.
```

Trycycle will ask you any questions it needs answered before starting, then handle the rest. It creates a git worktree, writes a plan, reviews the plan, builds the code, and reviews the code -- all without further input from you unless something comes up that needs your judgment.

You can use trycycle for anything from small features to large refactors. It works best when you have a clear goal in mind and a codebase that trycycle can read and test.

## How it works

Trycycle is a hill climber. It writes a plan, sends it to a reviewer, revises the plan based on feedback, and repeats until the reviewer finds no more issues (up to five rounds). Then it builds the code from the finished plan, sends the code to a fresh reviewer, fixes what the reviewer finds, and repeats that loop too (up to eight rounds). Each review round uses a new reviewer with no memory of previous rounds, so stale context never accumulates.
````

**Step 2: Run prose lint**

```bash
python3 /home/user/.claude/skills/writing-prose/scripts/prose_lint.py --file /tmp/trycycle-readme-draft.md
```

Expected: `OK: no lint violations` (exit code 0).

If lint fails, revise the prose in the temp file to fix the specific violations, then re-lint. Repeat until clean. Do not change content inside fenced code blocks -- those are excluded from lint automatically.

**Step 3: Copy final draft to repo**

```bash
cp /tmp/trycycle-readme-draft.md /home/user/code/trycycle/.worktrees/create-trycycle-repo/README.md
```

**Step 4: Verify final README is in place**

```bash
wc -l /home/user/code/trycycle/.worktrees/create-trycycle-repo/README.md
```

Expected: approximately 61 lines.

**Step 5: Commit**

```bash
cd /home/user/code/trycycle/.worktrees/create-trycycle-repo
git add README.md
git commit -m "feat: add README with installation and usage instructions"
```

---

### Task 4: Create public GitHub repo and push

**Step 1: Verify all files are committed in worktree**

```bash
cd /home/user/code/trycycle/.worktrees/create-trycycle-repo
git status --short
git log --oneline
```

Expected: Clean status. Commits for skill files, LICENSE, and README visible.

**Step 2: Merge feature branch into main**

From the main repo directory, fast-forward main to include all feature branch commits:

```bash
cd /home/user/code/trycycle
git merge --ff-only create-trycycle-repo
```

Expected: Fast-forward succeeds. If it fails, rebase the feature branch in the worktree first, then retry.

**Step 3: Check if remote already exists**

```bash
cd /home/user/code/trycycle
git remote -v
```

**Step 4: Create the GitHub repo (without pushing)**

If no remote exists:

```bash
cd /home/user/code/trycycle
gh repo create danshapiro/trycycle --public --source=.
```

This creates the remote repo and adds the `origin` remote, but does not push.

If a remote named `origin` already exists and points to `danshapiro/trycycle`, skip this step.

**Step 5: Push main to GitHub**

```bash
cd /home/user/code/trycycle
git push -u origin main
```

**Step 6: Verify on GitHub**

```bash
gh repo view danshapiro/trycycle --json name,visibility,url
```

Expected: Repo is public, URL is `https://github.com/danshapiro/trycycle`.

---

### Task 5: Clean up

**Step 1: Remove the worktree**

This must happen before deleting the branch.

```bash
cd /home/user/code/trycycle
git worktree remove .worktrees/create-trycycle-repo
```

**Step 2: Delete the feature branch**

Only after the worktree has been removed:

```bash
cd /home/user/code/trycycle
git branch -d create-trycycle-repo
```

**Step 3: Clean up temp file**

```bash
rm -f /tmp/trycycle-readme-draft.md
```

**Step 4: Final verification**

```bash
cd /home/user/code/trycycle
git log --oneline -5
ls -la
```

Expected: Main branch has all commits. Files present: `.gitignore`, `SKILL.md`, `agents/openai.yaml`, `LICENSE`, `README.md`, `docs/`.
