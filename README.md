# trycycle

A skill for Claude Code and Codex CLI that runs your work through multiple rounds of planning, building, and review -- automatically.

## Credits

Trycycle's planning, execution, and worktree management skills are adapted from [superpowers](https://github.com/obra/superpowers) by Jesse Vincent. They are included directly in this repo so you don't need to install superpowers separately.

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

Once installed, you can use trycycle from any Claude Code or Codex CLI session. Just include the word trycycle in your request and describe what you want built. For example:

```
Use trycycle to add a dark mode toggle to the settings page.
```

Trycycle will ask you any questions it needs answered before starting, then handle the rest. It creates a git worktree, writes a plan, reviews the plan, builds the code, and reviews the code -- all without further input from you unless something comes up that needs your judgment.

You can use trycycle for anything from small features to large refactors. It works best when you have a clear goal in mind and a codebase that trycycle can read and test.

## How it works

Trycycle is a hill climber. It writes a plan, sends it to a reviewer, revises the plan based on feedback, and repeats until the reviewer finds no more issues (up to five rounds). Then it builds the code from the finished plan, sends the code to a fresh reviewer, fixes what the reviewer finds, and repeats that loop too (up to eight rounds). Each review round uses a new reviewer with no memory of previous rounds, so stale context never accumulates.
