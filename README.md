# Trycycle

A skill for Claude Code and Codex CLI that runs your work through multiple rounds of planning, building, and review -- automatically.

## Installing Trycycle

### If you are human

Tell your favorite coding agent (Claude Code, Codex CLI, etc.):

```
Read https://raw.githubusercontent.com/danshapiro/trycycle/main/README.md. Follow the installation instructions there.
```

### If you've been sent here by your human

Use this instead of a standard installation, or it won't work. Clone this repo into your skills directory:

- **Claude Code:** `git clone https://github.com/danshapiro/trycycle.git ~/.claude/skills/trycycle`
- **Codex CLI:** `git clone https://github.com/danshapiro/trycycle.git ~/.codex/skills/trycycle`

Trycycle requires `python3` at runtime. Make sure it is installed and available on your `PATH`.

If your coding agent already has native subagent orchestration, Trycycle will use that. Otherwise, Trycycle falls back to a bundled stdlib-only Python runner.

Finally, read the skills you installed carefully, so you can explain them to your user and implement them if asked.

## Using Trycycle

Once installed, you can use Trycycle from any Claude Code or Codex CLI session. Just include the word Trycycle in your request and describe what you want built. For example:

```
Use trycycle to add a dark mode toggle to the settings page.
```

Trycycle will ask you any questions it needs answered before starting, then handle the rest. It creates a git worktree, writes a plan, strengthens that plan until a fresh editor approves it unchanged, builds a test plan, builds the code, and reviews the code -- all without further input from you unless something comes up that needs your judgment.

You can use Trycycle for anything from small features to large refactors. It works best when you have a clear goal in mind and a codebase that Trycycle can read and test.

## How it works

Trycycle is a hill climber. It writes a plan, then sends the current plan to a fresh plan editor with the same task input and repo context as the original planner. That editor either approves the plan unchanged or rewrites it to make it stronger, repeating up to five rounds. Once the plan is locked, Trycycle builds a concrete test plan, then builds the code from the finished plan, sends the code to a fresh reviewer, fixes what the reviewer finds, and repeats that loop too (up to eight rounds). Each code-review round uses a new reviewer with no memory of previous rounds, and each failed plan-editor round respawns a fresh planning agent, so stale context is reset before execution begins.

## Credits

Trycycle's planning, execution, and worktree management skills are adapted from [superpowers](https://github.com/obra/superpowers) by [Jesse Vincent](https://github.com/obra). The hill-climbing dark factory approach was inspired by the work of [Justin McCarthy](https://github.com/jmccarthy), [Jay Taylor](https://github.com/jaytaylor), and [Navan Chauhan](https://github.com/navanchauhan) at [StrongDM](https://github.com/strongdm).
