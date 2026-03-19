# Fix Python Environment Detection Implementation Plan

> **For agentic workers:** REQUIRED: Use trycycle-executing to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the naive Python setup heuristic in the worktree subskill with a lock-file-first detection cascade that correctly distinguishes Poetry, uv, and generic pip projects.

**Architecture:** Edit the skill-specific instructions in `maintenance/skill-instructions/trycycle-worktrees.txt` to describe the improved Python detection cascade, then re-run `maintenance/import-skills.sh` to regenerate `subskills/trycycle-worktrees/SKILL.md`. The upstream superpowers source has the same naive heuristic, so the skill-specific instructions must explicitly tell the import process to replace the Python section. No other files change.

**Tech Stack:** Bash (import script), Markdown/prose (skill instructions and generated skill)

---

## Design decisions

### Why lock files take priority over pyproject.toml inspection

A lock file is an unambiguous signal that a specific tool manages the project. `poetry.lock` means Poetry. `uv.lock` means uv. Inspecting `pyproject.toml` sections like `[tool.poetry]` is a useful fallback but is less definitive -- a project could have `[tool.poetry]` metadata left over from a migration while actually using uv day-to-day. Lock files reflect what the project actually uses.

### Why the cascade is mutually exclusive

The current code runs both the `requirements.txt` and `pyproject.toml` branches independently, which means both `pip install -r requirements.txt` and `poetry install` can fire for the same project. The fix makes these mutually exclusive: the first match wins, and no further setup commands run. This matches how real Python projects work -- they use one tool.

### Why this is prose, not a bash script

Trycycle's design principle is "it's a skill, not software." The agent reading this skill is capable of running detection commands and making judgment calls. A clear priority list in prose is more robust and generalizable than a brittle bash cascade, especially across platforms. The code block in the skill should show the pattern but the prose should describe the logic.

### Why only Poetry, uv, and pip

These three cover the vast majority of Python projects an agent will encounter. Poetry and uv are the two dominant modern Python project managers. Plain pip (with either `requirements.txt` or `pip install -e .`) covers everything else. Adding pdm, hatch, flit, etc. would add complexity for tools that represent a small fraction of real-world usage. The generic `pyproject.toml` fallback (`pip install -e .`) already handles projects that use any PEP 517-compliant build backend, which includes pdm, hatch, and flit projects.

### Why the instructions don't check whether the tool is installed

The worktree setup is best-effort. If `poetry` or `uv` is not installed, the command will fail and the agent will see the error. The agent can then fall back to `pip install -e .` or `pip install -r requirements.txt` on its own. Adding "check if poetry is on PATH first" to the skill instructions adds complexity without value -- the agent handles errors naturally.

## File structure

- Modify: `maintenance/skill-instructions/trycycle-worktrees.txt`
  - Add an explicit instruction telling the import process to replace the upstream Python setup heuristic with a lock-file-first detection cascade.
- Regenerate: `subskills/trycycle-worktrees/SKILL.md`
  - Re-running `maintenance/import-skills.sh` produces the updated skill. This file is never hand-edited.

## Strategy gate

- **Is this the right problem?** Yes. The post-mortem documented a real failure: `poetry install` ran on a project that does not use Poetry, because the only signal checked was `pyproject.toml` existence. The fix is narrow and well-scoped.
- **Is the architecture right?** Yes. The AGENTS.md pipeline (edit instructions, re-run import) is the only correct path. Hand-editing the generated skill would be overwritten on the next import.
- **Could we do less?** We could just add "check for `poetry.lock` before running `poetry install`" but that leaves uv unsupported and does not establish the right mental model (lock-file-first cascade). The slightly larger change is the clean steady-state answer.
- **Could we do more?** We could add pdm, hatch, conda, etc. But per YAGNI and the "think of everybody" principle, the generic `pip install -e .` fallback already handles PEP 517 projects regardless of their build backend. Adding niche tool detection without evidence of need would bloat the skill.

---

### Task 1: Update the skill-specific instructions to specify the Python detection cascade

**Files:**
- Modify: `maintenance/skill-instructions/trycycle-worktrees.txt`

- [ ] **Step 1: Read the current instructions file**

Read `maintenance/skill-instructions/trycycle-worktrees.txt` to confirm the current content. The file currently says:

> 5. **Keep:** The `.gitignore` safety verification -- that's valuable. Keep the project setup auto-detection (npm install, cargo build, etc.) -- the subagent needs that. Keep the `git worktree add` mechanics.

This "keep" instruction passes through the upstream Python heuristic unchanged. The fix adds an explicit replacement instruction.

- [ ] **Step 2: Add the Python detection replacement instruction**

Add a new numbered item to the "What to strip" section (after item 5) that tells the import process to replace the upstream Python setup with a lock-file-first cascade. The new instruction should read:

```markdown
6. **Replace the Python setup heuristic.** The upstream Python detection is too coarse — it runs `poetry install` for any `pyproject.toml` and runs both the `requirements.txt` and `pyproject.toml` branches independently. Replace the Python section of the setup block with a mutually exclusive, lock-file-first cascade:

   - If `poetry.lock` exists: `poetry install`
   - Else if `uv.lock` exists: `uv sync`
   - Else if `pyproject.toml` exists: `pip install -e .`
   - Else if `requirements.txt` exists: `pip install -r requirements.txt`

   The first match wins. Only one Python setup command runs. This correctly handles Poetry projects (detected by lock file, not pyproject.toml alone), uv projects, and generic PEP 517 projects.
```

- [ ] **Step 3: Commit**

```bash
git add maintenance/skill-instructions/trycycle-worktrees.txt
git commit -m "fix: specify lock-file-first Python detection in worktree skill instructions"
```

### Task 2: Re-run the import script to regenerate the worktree subskill

**Files:**
- Regenerate: `subskills/trycycle-worktrees/SKILL.md`

- [ ] **Step 1: Run the import script**

```bash
cd /home/user/code/trycycle/.worktrees/fix-python-env-detection
bash maintenance/import-skills.sh
```

This will clone the upstream superpowers repo, read the updated skill-specific instructions, and use `claude -p` to produce a new adapted skill. The script regenerates ALL four subskills, not just the worktree one.

Expected: The script completes without ABORT errors. The output should say "All skills adapted."

- [ ] **Step 2: Verify the regenerated worktree skill has the correct Python detection**

Read `subskills/trycycle-worktrees/SKILL.md` and verify:

1. The Python setup section uses a mutually exclusive cascade (not two independent `if` blocks)
2. `poetry.lock` is checked before assuming Poetry
3. `uv.lock` or `uv sync` appears as a supported path
4. `pyproject.toml` without a lock file falls back to `pip install -e .` (not `poetry install`)
5. `requirements.txt` is the last resort (only when no `pyproject.toml` exists)
6. The other subskills (trycycle-planning, trycycle-executing, trycycle-finishing) were not broken by the re-import

If the generated output does not match these criteria, the skill-specific instructions need refinement. Adjust the instructions in Task 1 and re-run.

- [ ] **Step 3: Verify the other regenerated subskills are not degraded**

Diff each regenerated subskill against the version on main:

```bash
git diff main -- subskills/trycycle-planning/SKILL.md
git diff main -- subskills/trycycle-executing/SKILL.md
git diff main -- subskills/trycycle-finishing/SKILL.md
```

The diffs should be limited to attribution header changes (updated `base-commit` and `imported` date). If there are substantive content changes in skills other than trycycle-worktrees, investigate whether the upstream source changed or the import introduced drift. Minor wording changes from re-adaptation are acceptable; structural or semantic changes are not.

- [ ] **Step 4: Commit**

```bash
git add subskills/
git commit -m "fix: regenerate subskills with improved Python env detection"
```

## Final verification checklist

- `maintenance/skill-instructions/trycycle-worktrees.txt` contains the lock-file-first cascade instruction
- `subskills/trycycle-worktrees/SKILL.md` shows mutually exclusive Python detection with lock file priority
- `subskills/trycycle-worktrees/SKILL.md` does NOT contain `if [ -f pyproject.toml ]; then poetry install; fi` as an unconditional check
- The other three subskills have not suffered substantive content changes
- No hand-edits exist in any `subskills/*/SKILL.md` file

## Notes for the implementation subagent

- The import script requires network access to clone `github.com/obra/superpowers.git` and uses `claude -p` with `claude-sonnet-4-6`. Ensure both are available.
- The import script regenerates ALL four subskills, not just the worktree one. This is by design. Inspect all four outputs.
- If the import script's Claude invocation produces a skill that does not meet the verification criteria, iterate on the skill-specific instructions text, not on the generated output.
- Do not hand-edit `subskills/trycycle-worktrees/SKILL.md`. The import script is the only valid path.

## Remember

- Exact file paths always
- The change pipeline is: edit `maintenance/skill-instructions/trycycle-worktrees.txt` -> run `maintenance/import-skills.sh` -> verify `subskills/trycycle-worktrees/SKILL.md`
- No tests in this repo per AGENTS.md
- The skill is prose for an intelligent agent, not a bash script for a machine
