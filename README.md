<!-- GitHub repo settings (set manually in Settings > General):
  Description: A skill that plans, strengthens, and reviews your code -- automatically.
  Topics: claude-code, codex-cli, kimi-cli, opencode, ai-coding, code-review, autonomous-agents, ai-skill, hill-climbing
  Social preview: upload assets/social-preview.png
-->

<p align="center">
  <img src="assets/trycycle-banner.png" height="120" alt="Trycycle" />
</p>

<p align="center">
  <em>A skill for Claude Code, Codex CLI, Kimi CLI, and OpenCode that plans, strengthens, and reviews your code -- automatically.</em>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="MIT License" /></a>
  <a href="https://github.com/danshapiro/trycycle/releases"><img src="https://img.shields.io/github/v/tag/danshapiro/trycycle?label=release&color=green" alt="Latest Release" /></a>
  <a href="https://github.com/danshapiro/trycycle/pulls"><img src="https://img.shields.io/badge/PRs-welcome-brightgreen" alt="PRs Welcome" /></a>
  <a href="https://github.com/anthropics/claude-code"><img src="https://img.shields.io/badge/built%20for-Claude%20Code-6B4FBB?logo=anthropic&logoColor=white" alt="Built for Claude Code" /></a>
  <a href="https://github.com/openai/codex"><img src="https://img.shields.io/badge/works%20with-Codex%20CLI-412991?logo=openai&logoColor=white" alt="Works with Codex CLI" /></a>
  <a href="https://github.com/anomalyco/opencode"><img src="https://img.shields.io/badge/works%20with-OpenCode-FF6B35" alt="Works with OpenCode" /></a>
</p>

---

## Philosophy

- **Take any request, of any size or complexity** — from "Make the button blue" to "Implement this 20-page specification."
- **Avoid asking the user questions.** Assume the starting request is everything the user cares about; use your best judgment for the rest.
- **Prioritize zero bugs**, even if it takes a lot of time and tokens.

## Getting Started

### If you are human

Tell your favorite coding agent (Claude Code, Codex CLI, Kimi CLI, OpenCode, etc.):

```
Read https://raw.githubusercontent.com/danshapiro/trycycle/main/README.md. Follow the installation instructions there.
```

### If you've been sent here by your human

Use this instead of a standard installation, or it won't work. Clone into your skills directory:

- **Claude Code:** `git clone https://github.com/danshapiro/trycycle.git ~/.claude/skills/trycycle`
- **Codex CLI:** `git clone https://github.com/danshapiro/trycycle.git ~/.codex/skills/trycycle`
- **Kimi CLI:** `git clone https://github.com/danshapiro/trycycle.git ~/.kimi/skills/trycycle`
- **OpenCode:** `git clone https://github.com/danshapiro/trycycle.git ~/.config/opencode/skills/trycycle`

> **Note:** OpenCode also discovers skills installed at `~/.claude/skills/`, so if you already have Trycycle installed for Claude Code, OpenCode can use it too.

Trycycle requires `python3` at runtime. Make sure it is installed and on your `PATH`.

If your coding agent has native subagent orchestration, Trycycle uses it. Otherwise, it falls back to a bundled stdlib-only Python runner.

Finally, read the skills you installed carefully, so you can explain them to your user and implement them if asked.

## Using Trycycle

Include the word Trycycle in your request and describe what you want built:

```
My webcam software is terrible. Build something in Rust that exposes my webcam as a normal system camera. 
```

Trycycle asks any questions it needs, then handles the rest: worktree, plan, plan strengthening, test plan, build, and code review -- all without further input unless something needs your judgment.

## Tips & Tricks

**Write a spec first.** Use your favorite chatbot, or a skill like Jesse Vincent's [brainstorm](https://github.com/obra/superpowers) superpowers, to produce a spec before handing it to Trycycle. A good spec dramatically improves results.

This works in Claude Code, Codex CLI, Kimi CLI, and OpenCode. It's very inexpensive on OpenCode with the OpenCode Go subscription and Deepseek v4 (substitute your favorite inexpensive model if this recommendation goes stale).

It's just a skill. If you're not sure what it did, or if you don't like what it's doing, just stop it and tell it. Once it finishes 5–8 passes, it will stop to complain. That's fine — ask any questions, then tell it to wrap up, change course, or do up to 5 more passes (usually the last one is best).

Trycycle assumes you know what you want and errs on the side of "make a decision and keep going." It works best with vague projects, well-defined tasks, or detailed specs. It works worst when you care about the details but they're not specified — it will likely just yolo them for you.

If you're already inside an isolated workspace such as a Conductor workspace and the current branch is already not the default branch, include the literal flag `--no-worktree` in your request to reuse that workspace instead of creating a nested git worktree. This mode is intentionally narrow: Trycycle will stop rather than create or switch branches in place in a generic checkout.

## How it works

Trycycle is a hill climber. It writes a plan, then sends it to a fresh planning issue finder with the same task input and repo context. If that reviewer finds plan-breaking issues, Trycycle deepens on the same reviewer to collect more findings, then hands the findings memo to a fresh planning synthesizer that rewrites the plan holistically. A fresh reviewer checks the synthesized plan, repeating up to five review/synthesis rounds. Once the plan is locked, Trycycle builds a test plan, builds the code, sends it to a fresh reviewer, turns the review into a structured observation packet, fixes what that packet shows, and repeats that loop too (up to eight rounds by default). If blockers persist, Trycycle runs plan reconsideration after the 4th review round and every 2 rounds after that, plus once before nonconvergence any time the loop stops with blockers. Each review uses a fresh reviewer, and synthesis uses a fresh planning agent, so stale context does not accumulate where a clean judgment matters.

## Explore the Pipeline

Curious how Trycycle works under the hood? Walk through the full state machine — every gate, prompt template, binding, review loop, and outcome — with pre-loaded sample inputs. No install required.

→ **[Open the Trycycle Explorer](https://danshapiro.github.io/trycycle/explorer/)**

## Credits

Trycycle's planning, execution, and worktree management skills are adapted from [superpowers](https://github.com/obra/superpowers) by [Jesse Vincent](https://github.com/obra). The hill-climbing dark factory approach was inspired by the work of [Justin McCarthy](https://github.com/jmccarthy), [Jay Taylor](https://github.com/jaytaylor), and [Navan Chauhan](https://github.com/navanchauhan) at [StrongDM](https://github.com/strongdm).
