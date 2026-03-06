# Trycycle

A skill for Claude Code and Codex CLI that runs your work through multiple rounds of planning, building, and review -- automatically.

## Installing Trycycle

### If you are human

Tell your favorite coding agent (Claude Code, Codex CLI, etc.):

```
Install the trycycle skill from https://github.com/danshapiro/trycycle. Once it's installed, read it and tell me all the ways I can use it in my projects.
```

### If you've been sent here by your human

Clone (not copy) this repo into your skills directory. Use the command for your platform:

- **Claude Code:** `git clone https://github.com/danshapiro/trycycle.git ~/.claude/skills/trycycle`
- **Codex CLI:** `git clone https://github.com/danshapiro/trycycle.git ~/.codex/skills/trycycle`
- **Gemini CLI:** `git clone https://github.com/danshapiro/trycycle.git ~/.gemini/skills/trycycle`

If the skills directory already has other skills in it, that's fine -- the command creates the `trycycle` subdirectory automatically.

## Using Trycycle

Once installed, you can use Trycycle from any Claude Code or Codex CLI session. Just include the word Trycycle in your request and describe what you want built. For example:

```
Use trycycle to add a dark mode toggle to the settings page.
```

Trycycle will ask you any questions it needs answered before starting, then handle the rest. It creates a git worktree, writes a plan, reviews the plan, builds the code, and reviews the code -- all without further input from you unless something comes up that needs your judgment.

You can use Trycycle for anything from small features to large refactors. It works best when you have a clear goal in mind and a codebase that Trycycle can read and test.

## How it works

Trycycle is a hill climber. It writes a plan, sends it to a reviewer, revises the plan based on feedback, and repeats until the reviewer finds no more issues (up to five rounds). Then it builds the code from the finished plan, sends the code to a fresh reviewer, fixes what the reviewer finds, and repeats that loop too (up to eight rounds). Each review round uses a new reviewer with no memory of previous rounds, so stale context never accumulates.

## Credits

Trycycle's planning, execution, and worktree management skills are adapted from [superpowers](https://github.com/obra/superpowers) by [Jesse Vincent](https://github.com/obra). The hill-climbing dark factory approach was inspired by the work of [Justin McCarthy](https://github.com/jmccarthy), [Jay Taylor](https://github.com/jaytaylor), and [Navan Chauhan](https://github.com/navanchauhan) at [StrongDM](https://github.com/strongdm).
