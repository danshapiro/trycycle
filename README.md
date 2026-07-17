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

## Tips

Trycycle assumes you know what you want and errs on the side of 'make a decision and keep going'.

It works best when:
- You have a vague project and don't care about the details, like "Make solitaire"
- You have an easy-to-define task ("Fix issue 123")
- You have a detailed spec you created outside trycycle (I recommend Superpowers brainstorming, for example, or a good chat with your favorite AI)

It works worst when you care about the details, but they're not specified. It will likely just yolo them for you.

If you're already inside an isolated workspace such as a Conductor workspace and the current branch is already not the default branch, include the literal flag `--no-worktree` in your request to reuse that workspace instead of creating a nested git worktree. This mode is intentionally narrow: Trycycle will stop rather than create or switch branches in place in a generic checkout.

## How it works

Trycycle is a hill climber. It first extracts the relevant user intent verbatim, agrees on a testing strategy with you (or continues on its own if you've told it not to wait), and writes a plan from that intent artifact. Before polishing anything, it pressure-tests the plan's load-bearing assumptions -- the claims the whole approach rests on -- by sending validators out for evidence and revising the plan if an assumption fails. Then the plan is hardened: each round, a fresh agent carves the plan into territories, a team of fresh reviewers digs into every territory in parallel, and a fresh plan editor verifies their findings and either approves the plan unchanged or improves it, repeating up to five rounds.

Approving the testing strategy is the one durable checkpoint: alongside the strategy itself, it carries a validation approval forecast authorizing anything testing may need that changes state or costs money, like running the test suite or launching services. Next comes a concrete test plan that reconciles its validation approval scope against that forecast; if it stays within what you already approved, Trycycle proceeds without asking again, and only comes back to you for a delta when the test plan needs something the forecast didn't cover. If you told Trycycle not to wait at the strategy gate, that one checkpoint moves to the test plan instead — autonomy relocates the approval, it never removes it.

Then Trycycle builds the code and enters the verification loop (up to eight rounds by default). Each round re-checks load-bearing assumptions against what was actually built, then reviews the produced evidence against your request, and once those pass runs a territory code review: a fresh agent carves the change into territories, parallel reviewers go deep on each, and a merger verifies and combines their findings into a structured observation packet. Whatever that packet shows gets fixed, and the loop repeats. If blockers persist, Trycycle reconsiders the plan after the 4th review round and every 2 rounds after that, plus once before it ever gives up. Every reviewer, planner, and validator is a fresh agent with no memory of previous rounds, so stale judgment never accumulates; only the implementation subagent persists to carry the work forward.

## Credits

Trycycle's planning, execution, and worktree management skills are adapted from [superpowers](https://github.com/obra/superpowers) by [Jesse Vincent](https://github.com/obra). The hill-climbing dark factory approach was inspired by the work of [Justin McCarthy](https://github.com/jmccarthy), [Jay Taylor](https://github.com/jaytaylor), and [Navan Chauhan](https://github.com/navanchauhan) at [StrongDM](https://github.com/strongdm).
