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

## Installing trycycle

Claude Code stores skills in `~/.claude/skills/`. Clone this repo there:

```bash
git clone https://github.com/danshapiro/trycycle.git ~/.claude/skills/trycycle
```

Codex CLI stores skills in `~/.codex/skills/`. Clone there instead:

```bash
git clone https://github.com/danshapiro/trycycle.git ~/.codex/skills/trycycle
```

If the skills directory already has other skills in it, that's fine -- the commands above create the `trycycle` subdirectory automatically.

To update later, pull from whichever path you used:

```bash
git -C ~/.claude/skills/trycycle pull
```

## Using trycycle

Once superpowers and trycycle are both installed, you can use trycycle from any Claude Code or Codex CLI session. Just include the word trycycle in your request and describe what you want built. For example:

```
Use trycycle to add a dark mode toggle to the settings page.
```

Trycycle will ask you any questions it needs answered before starting, then handle the rest. It creates a git worktree, writes a plan, reviews the plan, builds the code, and reviews the code -- all without further input from you unless something comes up that needs your judgment.

You can use trycycle for anything from small features to large refactors. It works best when you have a clear goal in mind and a codebase that trycycle can read and test.

## How it works

Trycycle is a hill climber. It writes a plan, sends it to a reviewer, revises the plan based on feedback, and repeats until the reviewer finds no more issues (up to five rounds). Then it builds the code from the finished plan, sends the code to a fresh reviewer, fixes what the reviewer finds, and repeats that loop too (up to eight rounds). Each review round uses a new reviewer with no memory of previous rounds, so stale context never accumulates.
