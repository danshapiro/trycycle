# Trycycle

This repo is a skill for AI coding agents such as Claude Code and Codex CLI. Users install it by cloning into their skills directory. 

## If you are here to install and use trycycle

Follow the instructions in README.md. Use the version you install, and ignore the rest of this document.

## If you are here to work on trycycle

### Structure

- `SKILL.md` + `subskills/` — the skill itself (what users install and run)
- `maintenance/` — maintenance scripts and historical plans (not user-facing)
- `README.md` — human-facing install and usage docs

### Principles

Trycycle turns a user request into verified, delivered software through gated phases and stateless subagents around one persistent builder. These principles organize every prompt, gate, and loop; a change that cannot be traced to them is probably wrong.

- **User instructions outrank everything.** A specific instruction from the user overrides any rule below, any prompt, and any convention — both when running trycycle and when changing it.
- **The user is not part of the machine.** Trycycle is fire-and-forget: once work is underway, assume the user cannot answer questions or make decisions. Talk to the user at the edges: the update offer and open questions at the start, the one combined approval (the testing strategy, presented with its validation approval forecast, skippable by a broad autonomy instruction), and the choice at the end of how to land the finished work. The concrete test plan reconciles against that approved forecast and returns to the user only when it materially deviates — that is a hard wall, not a second routine approval. In between, stop only at a hard wall: the work cannot continue correctly without something only the user can give — a secret, paid access, authority, a resolution to conflicting requirements, or a call where guessing wrong could cause harm. Escalation is never a deliberate choice among workable options.
- **Scope is fixed; everything else is variable.** Recorded user intent is the definition of done. Agents choose how, in what order, and with what evidence — never what is delivered. Cutting or deferring required behavior does not retire risk; it moves the risk outside what the gates measure. Slices are proof and sequencing, not scope reduction. A stub, TODO, or future-work note cannot satisfy a requirement.
- **Prove before you rely.** Nothing downstream may depend on an unproven decision-controlling claim. A plan's claims are proven at plan time — code read, behavior probed, a disposable spike run — because execution depends on them and late falsification is expensive. Code is proven by its tests and acceptance artifacts before review passes it. Fixing a defect by inventing an unproven mechanism relocates the defect downstream.
- **Proof is re-checkable and lives where its consumer needs it.** Written testimony is not proof — a fresh agent must be able to verify it. Tests are committed with the code because they are re-run for the life of the repo. Acceptance artifacts live in the run record because the acceptance reviewer inspects them without rerunning. Plan-time spikes are disposable: their durable residue is a precise claim in the plan that a fresh reviewer can cheaply check against reality. Deliverables carry what their future consumers need — plans carry decisions, code carries its tests.
- **Fresh eyes judge; authors never grade their own work.** Every verdict — review, validation, acceptance — comes from a blank-slate subagent, and judging agents never inherit a prior round's reports. The persistent implementation subagent receives verified findings to fix, but never judges its own fix. Judgment decays with staleness and authorship; empirical evidence does not.
- **The orchestrator dispatches; subagents think.** The orchestrator has two jobs: running the process — dispatching subagents, routing on the verdict lines in their reports, saving reports without reading the rest — and managing the human interface: talking with the user, recording what the user wants, and passing that intent to every subagent that needs it. It never does or judges the work itself; its context belongs to the user. Trust dispatched agents: a long-running subagent is far more likely deep in a hard problem than stuck.
- **Loops converge on truth, not exhaustion.** A loop ends only when a full fresh pass finds nothing blocking — an unchanged plan out of the editor, or acceptance and code review passing the same implementation. Evidence-backed work converges because nothing is left to falsify. The round limits are a debugging aid while trycycle is under development, not intended production behavior: hitting one means trycycle itself is defective, so the run stops and reports to help the user get the work back on track while trycycle gets fixed. The limits will be removed once the loops are proven to converge. A loop never quietly gives up early and never proceeds past a failed gate.
- **Verification means user-visible reality.** Weight goes to checks that exercise the product the way the user consumes it, and to acceptance artifacts a blank-slate reviewer can inspect without rerunning anything. Internal self-consistency is not evidence. Nothing may depend on a human validating.
- **Ask once, durably.** The testing-strategy approval carries a validation approval forecast; approving the strategy pre-authorizes those action categories for the rest of the run, including the concrete test plan. The test plan reconciles its validation approval scope against that forecast and returns to the user only for the delta when it materially deviates — never a routine second approval of ground already covered. Probe permissions covered by the forecast don't re-ask either. Autonomy instructions skip only the strategy approval, never a genuine material-deviation ask.
- **Fit the host; impose nothing.** Work across agents, project types, repo conventions, and operating systems — Claude Code to Codex CLI, brownfield fix to greenfield build, Windows to WSL to Mac to Linux. Follow local constraints instead of bringing your own.
- **Fix the system, not the symptom.** When a run fails or a breaker trips, the defect is in trycycle's process. Repair the process so the failure class dies; do not patch the run and move on. We are not in a hurry.
- **It's a skill, not software.** In the subagent prompts and subskills, succinct, direct prose that educates a capable model beats machinery and micromanagement — say what the job really is, and trust the model with it. The orchestrator's instructions are the one deliberately mechanical layer: exact steps and commands, because the orchestrator follows the process instead of thinking about the work.


### Process

- **All work in a worktree** - create it before changing files and offer to land on local main & clean it up when finished
- **Safe merges to main** — Never merge directly on main. Merge main into the feature branch first, resolve conflicts there, then `git merge --ff-only` on main. This prevents broken state on the working branch.
- **Don't create tests for skill changes**, only code changes. This specific rule supercedes broader policies.

### Subskills
The skills in `subskills/` are maintained directly in this repo — edit them like any other skill file, holding them to the same principles. They were originally adapted from Jesse Vincent's superpowers project (credited in README.md), but the import pipeline has been retired and there is no upstream sync to preserve.

### Versioning

Trycycle uses git tags for version tracking. `check-update.py` runs at the start of every Trycycle session (SKILL.md step 0) and compares the user's local tag against `origin/main` to prompt for updates.

To release a new version:

1. Commit all changes to `main`.
2. Ask the user what version number to use — never pick one yourself.
3. Tag: `git tag v<version>`
4. Push: `git push origin main --tags`
5. Update any local Trycycle installs you control by running `git pull` in each installed clone so your manual checks use the pushed version, not a stale checkout. Check the common skill locations for all supported agents, including:
   - Unix / WSL home directories such as `~/.claude/skills/trycycle`, `~/.codex/skills/trycycle`, and `~/.kimi/skills/trycycle`
   - Windows-side installs visible from WSL, such as `/mnt/c/Users/<user>/.claude/skills/trycycle`, `/mnt/c/Users/<user>/.codex/skills/trycycle`, and `/mnt/c/Users/<user>/.kimi/skills/trycycle`
   - Native PowerShell installs in `C:\Users\<user>\.claude\skills\trycycle`, `C:\Users\<user>\.codex\skills\trycycle`, `C:\Users\<user>\.kimi\skills\trycycle`, and equivalent locations for any other agent-specific skill directories you know about
