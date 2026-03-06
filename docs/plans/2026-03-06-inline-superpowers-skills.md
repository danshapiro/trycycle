# Inline Superpowers Skills Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use trycycle-executing to implement this plan task-by-task.

**Goal:** Eliminate the superpowers dependency by inlining its 4 skills as adapted trycycle subskills, with an import script that uses `claude -p` to dynamically adapt them from upstream.

**Architecture:** A bash import script (`scripts/import-skills.sh`) clones obra/superpowers, diffs each skill against its last-imported base commit (stored in the adapted skill's header), and pipes the source + diff + existing adaptation into `claude -p` for intelligent re-adaptation. The adapted skills live in `skills/trycycle-*/SKILL.md` and are referenced by the orchestrator `SKILL.md` using trycycle-prefixed names.

**Tech Stack:** Bash, git, `claude -p` (Claude Code CLI in print mode)

---

### Task 1: Create the import script skeleton

**Files:**
- Create: `scripts/import-skills.sh`

**Step 1: Write the script with the skill map and argument parsing**

```bash
#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/obra/superpowers.git"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TRYCYCLE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SKILLS_DIR="$TRYCYCLE_ROOT/skills"
TEMP_DIR=""

cleanup() {
  if [[ -n "$TEMP_DIR" && -d "$TEMP_DIR" ]]; then
    rm -rf "$TEMP_DIR"
  fi
}
trap cleanup EXIT

# Map trycycle skill names to superpowers source skill directory names
declare -A SKILL_MAP=(
  [trycycle-worktrees]="using-git-worktrees"
  [trycycle-planning]="writing-plans"
  [trycycle-executing]="executing-plans"
  [trycycle-finishing]="finishing-a-development-branch"
)

main() {
  echo "=== Trycycle Skill Import ==="

  # Clone superpowers into temp dir
  TEMP_DIR="$(mktemp -d)"
  echo "Cloning obra/superpowers..."
  git clone --quiet "$REPO_URL" "$TEMP_DIR/superpowers"
  local upstream_head
  upstream_head="$(git -C "$TEMP_DIR/superpowers" rev-parse --short HEAD)"
  echo "Upstream HEAD: $upstream_head"

  local any_aborted=false

  for trycycle_name in "${!SKILL_MAP[@]}"; do
    local source_name="${SKILL_MAP[$trycycle_name]}"
    echo ""
    echo "--- Importing $source_name -> $trycycle_name ---"

    if ! import_skill "$trycycle_name" "$source_name" "$upstream_head"; then
      echo "ABORTED: $trycycle_name (see above)"
      any_aborted=true
    fi
  done

  echo ""
  if [[ "$any_aborted" == "true" ]]; then
    echo "=== Import complete with aborts. Review aborted skills above. ==="
    exit 1
  else
    echo "=== Import complete. All skills adapted. ==="
  fi
}

main "$@"
```

**Step 2: Verify the script is syntactically valid**

Run: `bash -n scripts/import-skills.sh`
Expected: No output (clean parse). It will fail because `import_skill` is not yet defined — that's expected at this stage. We just need the parse to succeed for the parts that exist.

Actually, `bash -n` will fail on the undefined function call. Instead:

Run: `head -20 scripts/import-skills.sh`
Expected: Confirms the file was written correctly.

**Step 3: Commit**

```bash
git -C .worktrees/inline-superpowers-skills add scripts/import-skills.sh
git -C .worktrees/inline-superpowers-skills commit -m "feat: add import script skeleton with skill map and cleanup"
```

---

### Task 2: Add the base-commit parser

**Files:**
- Modify: `scripts/import-skills.sh`

**Step 1: Write the `parse_base_commit` function**

Add this function before `main()`:

```bash
# Extract base-commit from an existing adapted skill's header.
# Returns empty string if no header found (first import).
parse_base_commit() {
  local skill_file="$1"
  if [[ -f "$skill_file" ]]; then
    grep '<!-- base-commit:' "$skill_file" | sed 's/.*base-commit: *\([a-f0-9]*\).*/\1/' | head -1
  fi
}
```

**Step 2: Write a quick test — create a temp file with a header and parse it**

Run:
```bash
source scripts/import-skills.sh 2>/dev/null; \
  echo '<!-- base-commit: abc1234f -->' > /tmp/test-header.md; \
  result=$(parse_base_commit /tmp/test-header.md); \
  echo "parsed: '$result'"; \
  rm /tmp/test-header.md
```
Expected: `parsed: 'abc1234f'`

Note: The `source` will fail at `main` invocation due to missing `import_skill`. To test in isolation, extract just the function to a temp file:

Run:
```bash
cat > /tmp/test-parse.sh << 'TESTEOF'
parse_base_commit() {
  local skill_file="$1"
  if [[ -f "$skill_file" ]]; then
    grep '<!-- base-commit:' "$skill_file" | sed 's/.*base-commit: *\([a-f0-9]*\).*/\1/' | head -1
  fi
}
echo '<!-- base-commit: abc1234f -->' > /tmp/test-header.md
result=$(parse_base_commit /tmp/test-header.md)
echo "parsed: '$result'"
[[ "$result" == "abc1234f" ]] && echo "PASS" || echo "FAIL"
rm /tmp/test-header.md
TESTEOF
bash /tmp/test-parse.sh
```
Expected: `parsed: 'abc1234f'` then `PASS`

**Step 3: Also test the empty case (first import)**

Run:
```bash
cat > /tmp/test-parse-empty.sh << 'TESTEOF'
parse_base_commit() {
  local skill_file="$1"
  if [[ -f "$skill_file" ]]; then
    grep '<!-- base-commit:' "$skill_file" | sed 's/.*base-commit: *\([a-f0-9]*\).*/\1/' | head -1
  fi
}
result=$(parse_base_commit /tmp/nonexistent-file.md)
echo "parsed: '$result'"
[[ -z "$result" ]] && echo "PASS" || echo "FAIL"
TESTEOF
bash /tmp/test-parse-empty.sh
```
Expected: `parsed: ''` then `PASS`

**Step 4: Commit**

```bash
git -C .worktrees/inline-superpowers-skills add scripts/import-skills.sh
git -C .worktrees/inline-superpowers-skills commit -m "feat: add base-commit parser for skill headers"
```

---

### Task 3: Add the diff generators

**Files:**
- Modify: `scripts/import-skills.sh`

**Step 1: Write `generate_source_diff` and `generate_adaptation_diff` functions**

Add before `main()`:

```bash
# Generate the diff of the upstream source skill between base-commit and current HEAD.
# This shows what Jesse changed since we last imported.
# Returns empty string if no base-commit (first import).
generate_source_diff() {
  local superpowers_repo="$1"
  local source_name="$2"
  local base_commit="$3"
  local skill_path="skills/$source_name/SKILL.md"

  if [[ -n "$base_commit" ]]; then
    # Resolve short hash to full hash in the cloned repo
    local full_hash
    full_hash="$(git -C "$superpowers_repo" rev-parse "$base_commit" 2>/dev/null || true)"
    if [[ -n "$full_hash" ]]; then
      git -C "$superpowers_repo" diff "$full_hash"..HEAD -- "$skill_path" 2>/dev/null || true
    fi
  fi
}

# Generate the diff between the upstream source at base-commit and our current adaptation.
# This shows what we changed during adaptation — used as influence for the next adaptation.
generate_adaptation_diff() {
  local superpowers_repo="$1"
  local source_name="$2"
  local base_commit="$3"
  local trycycle_skill_file="$4"
  local skill_path="skills/$source_name/SKILL.md"

  if [[ -n "$base_commit" && -f "$trycycle_skill_file" ]]; then
    local full_hash
    full_hash="$(git -C "$superpowers_repo" rev-parse "$base_commit" 2>/dev/null || true)"
    if [[ -n "$full_hash" ]]; then
      # Show the source at base-commit to a temp file, then diff against our adaptation
      local base_source
      base_source="$(git -C "$superpowers_repo" show "$full_hash:$skill_path" 2>/dev/null || true)"
      if [[ -n "$base_source" ]]; then
        diff -u <(echo "$base_source") "$trycycle_skill_file" || true
      fi
    fi
  fi
}
```

**Step 2: Verify both functions exist in the script**

Run: `grep -c 'generate_source_diff\|generate_adaptation_diff' .worktrees/inline-superpowers-skills/scripts/import-skills.sh`
Expected: At least 2 (the function definitions)

**Step 3: Commit**

```bash
git -C .worktrees/inline-superpowers-skills add scripts/import-skills.sh
git -C .worktrees/inline-superpowers-skills commit -m "feat: add source diff and adaptation diff generators"
```

---

### Task 4: Build the prompt template

**Files:**
- Create: `scripts/prompt-template.txt`

This is the prompt sent to `claude -p` for each skill adaptation. It uses placeholder tokens that the script substitutes.

**Step 1: Write the prompt template**

```text
You are adapting a skill from the superpowers project (by Jesse Vincent, https://github.com/obra/superpowers) for use as an inlined subskill in the trycycle project.

## Your task

Read the trycycle repository to understand what trycycle is, how it works, and how this skill fits into the overall orchestration. Then adapt the upstream source skill into a trycycle subskill.

## Context files to read

Read these files from the trycycle repo at {{TRYCYCLE_ROOT}} to build context:
- SKILL.md (the trycycle orchestrator — shows how this subskill is invoked)
- README.md (explains what trycycle is)

## Skill being adapted

- Upstream skill name: {{SOURCE_NAME}}
- Trycycle skill name: {{TRYCYCLE_NAME}}

## Current upstream source (at commit {{UPSTREAM_HEAD}})

<upstream-source>
{{UPSTREAM_SOURCE}}
</upstream-source>

{{SOURCE_DIFF_SECTION}}

{{ADAPTATION_DIFF_SECTION}}

{{EXISTING_ADAPTATION_SECTION}}

## Adaptation instructions

Transform the upstream source into a trycycle subskill. Be aggressive — strip everything that trycycle's orchestrator already handles or overrides:

1. **Rename references:** All `superpowers:X` skill references become `trycycle-X`. The skill's own name in the YAML frontmatter becomes `{{TRYCYCLE_NAME}}`.

2. **Remove sections trycycle overrides at runtime:**
   - writing-plans: Remove the entire "Execution Handoff" section. Remove any brainstorming preconditions.
   - executing-plans: Remove the batch-pause-and-wait-for-feedback flow (Steps 3-4 about "Report" and "Continue"). Remove "When to Stop and Ask for Help" (trycycle tells the subagent to use best judgment). Remove Step 5 about finishing (trycycle handles that).
   - using-git-worktrees: Remove the "Ask User" fallback for directory selection (trycycle mandates .worktrees). Remove baseline test verification (trycycle doesn't need it — the worktree is created from a known-good main).
   - finishing-a-development-branch: Keep mostly intact. Remove references to skills we don't ship (subagent-driven-development, brainstorming).

3. **Remove stale integration sections:** Remove "Called by" / "Pairs with" / "Integration" sections that reference skills we don't ship (brainstorming, subagent-driven-development). Replace with a brief note that this skill is part of trycycle.

4. **Simplify:** If a section exists solely to handle a case that trycycle's orchestrator already handles, remove it rather than leaving dead instructions.

5. **Preserve the core:** Keep all operational content the subagent actually needs to do its job. When in doubt, keep it.

6. **Attribution header:** The output MUST start with exactly this header (before the YAML frontmatter):

```
<!-- {{TRYCYCLE_NAME}}: adapted from obra/superpowers {{SOURCE_NAME}} -->
<!-- source: https://github.com/obra/superpowers -->
<!-- author: Jesse Vincent -->
<!-- base-commit: {{UPSTREAM_HEAD}} -->
<!-- imported: {{TODAY}} -->
```

Then the YAML frontmatter, then the skill content.

## Output format

Output ONLY the complete adapted SKILL.md file content. No commentary, no explanation, no markdown code fences wrapping the whole thing. Just the file.

If the upstream source has changed in ways that make confident adaptation impossible (major restructuring, new concepts, semantic changes you can't safely adapt), output exactly:
ABORT: <one-line reason>
```

**Step 2: Verify the template was written**

Run: `wc -l .worktrees/inline-superpowers-skills/scripts/prompt-template.txt`
Expected: Approximately 70-80 lines

**Step 3: Commit**

```bash
git -C .worktrees/inline-superpowers-skills add scripts/prompt-template.txt
git -C .worktrees/inline-superpowers-skills commit -m "feat: add claude -p prompt template for skill adaptation"
```

---

### Task 5: Write the `build_prompt` function

**Files:**
- Modify: `scripts/import-skills.sh`

**Step 1: Write the function that assembles the prompt from the template and computed values**

Add before `main()`:

```bash
# Build the full prompt for claude -p by substituting placeholders in the template.
build_prompt() {
  local trycycle_name="$1"
  local source_name="$2"
  local upstream_head="$3"
  local upstream_source="$4"
  local source_diff="$5"
  local adaptation_diff="$6"
  local existing_adaptation="$7"
  local today
  today="$(date +%Y-%m-%d)"

  local template
  template="$(cat "$SCRIPT_DIR/prompt-template.txt")"

  # Build conditional sections
  local source_diff_section=""
  if [[ -n "$source_diff" ]]; then
    source_diff_section="## Upstream changes since last import

This diff shows what changed in the upstream source since our last import (base-commit). Use this to understand what Jesse changed — if anything here is a major restructuring or semantic shift that you can't confidently adapt, ABORT.

<upstream-diff>
$source_diff
</upstream-diff>"
  fi

  local adaptation_diff_section=""
  if [[ -n "$adaptation_diff" ]]; then
    adaptation_diff_section="## Previous adaptation diff

This diff shows how the upstream source was transformed into the current trycycle adaptation last time. Use this as a STRONG INFLUENCE on how to adapt — it shows the patterns and decisions made previously. Do NOT apply this diff mechanically; use it to understand the intent and make similar choices for the new version.

<adaptation-diff>
$adaptation_diff
</adaptation-diff>"
  fi

  local existing_adaptation_section=""
  if [[ -n "$existing_adaptation" ]]; then
    existing_adaptation_section="## Existing trycycle adaptation (current version)

For reference, here is the current adapted version. The new adaptation should follow similar patterns but be based on the new upstream source.

<existing-adaptation>
$existing_adaptation
</existing-adaptation>"
  fi

  # Substitute placeholders
  template="${template//\{\{TRYCYCLE_ROOT\}\}/$TRYCYCLE_ROOT}"
  template="${template//\{\{SOURCE_NAME\}\}/$source_name}"
  template="${template//\{\{TRYCYCLE_NAME\}\}/$trycycle_name}"
  template="${template//\{\{UPSTREAM_HEAD\}\}/$upstream_head}"
  template="${template//\{\{TODAY\}\}/$today}"
  template="${template//\{\{UPSTREAM_SOURCE\}\}/$upstream_source}"
  template="${template//\{\{SOURCE_DIFF_SECTION\}\}/$source_diff_section}"
  template="${template//\{\{ADAPTATION_DIFF_SECTION\}\}/$adaptation_diff_section}"
  template="${template//\{\{EXISTING_ADAPTATION_SECTION\}\}/$existing_adaptation_section}"

  echo "$template"
}
```

**Step 2: Verify the function exists in the script**

Run: `grep -c 'build_prompt' .worktrees/inline-superpowers-skills/scripts/import-skills.sh`
Expected: At least 1

**Step 3: Commit**

```bash
git -C .worktrees/inline-superpowers-skills add scripts/import-skills.sh
git -C .worktrees/inline-superpowers-skills commit -m "feat: add prompt builder with template substitution"
```

---

### Task 6: Write the `import_skill` function

**Files:**
- Modify: `scripts/import-skills.sh`

**Step 1: Write the core import function that ties everything together**

Add before `main()`:

```bash
import_skill() {
  local trycycle_name="$1"
  local source_name="$2"
  local upstream_head="$3"
  local superpowers_repo="$TEMP_DIR/superpowers"
  local trycycle_skill_file="$SKILLS_DIR/$trycycle_name/SKILL.md"
  local source_skill_path="skills/$source_name/SKILL.md"

  # 1. Read upstream source at HEAD
  local upstream_source
  upstream_source="$(cat "$superpowers_repo/$source_skill_path")"
  if [[ -z "$upstream_source" ]]; then
    echo "ERROR: Could not read upstream source at $source_skill_path"
    return 1
  fi

  # 2. Parse base-commit from existing adaptation
  local base_commit
  base_commit="$(parse_base_commit "$trycycle_skill_file")"
  if [[ -n "$base_commit" ]]; then
    echo "  Previous base-commit: $base_commit"
  else
    echo "  First import (no previous base-commit)"
  fi

  # 3. Generate diffs
  local source_diff=""
  local adaptation_diff=""
  local existing_adaptation=""

  if [[ -n "$base_commit" ]]; then
    source_diff="$(generate_source_diff "$superpowers_repo" "$source_name" "$base_commit")"
    adaptation_diff="$(generate_adaptation_diff "$superpowers_repo" "$source_name" "$base_commit" "$trycycle_skill_file")"
    existing_adaptation="$(cat "$trycycle_skill_file")"

    if [[ -n "$source_diff" ]]; then
      echo "  Upstream changed since last import"
    else
      echo "  No upstream changes since last import"
    fi
  fi

  # 4. Build prompt
  local prompt
  prompt="$(build_prompt "$trycycle_name" "$source_name" "$upstream_head" "$upstream_source" "$source_diff" "$adaptation_diff" "$existing_adaptation")"

  # 5. Run claude -p
  echo "  Running claude -p for adaptation..."
  local output
  output="$(echo "$prompt" | claude -p --model claude-sonnet-4-6 --dangerously-skip-permissions --add-dir "$TRYCYCLE_ROOT" 2>/dev/null)"

  # 6. Check for ABORT
  if [[ "$output" == ABORT:* ]]; then
    echo "  $output"
    return 1
  fi

  # 7. Write output
  mkdir -p "$SKILLS_DIR/$trycycle_name"
  echo "$output" > "$trycycle_skill_file"
  echo "  Written to $trycycle_skill_file"
  return 0
}
```

**Step 2: Verify all functions are now present**

Run: `grep -E '^[a-z_]+\(\)' .worktrees/inline-superpowers-skills/scripts/import-skills.sh`
Expected: `cleanup()`, `parse_base_commit()`, `generate_source_diff()`, `generate_adaptation_diff()`, `build_prompt()`, `import_skill()`, `main()`

**Step 3: Verify script parses cleanly**

Run: `bash -n .worktrees/inline-superpowers-skills/scripts/import-skills.sh`
Expected: No output (clean parse)

**Step 4: Commit**

```bash
git -C .worktrees/inline-superpowers-skills add scripts/import-skills.sh
git -C .worktrees/inline-superpowers-skills commit -m "feat: add import_skill function tying together diff, prompt, and claude -p"
```

---

### Task 7: Make the script executable and do a dry-run test

**Files:**
- Modify: `scripts/import-skills.sh` (permissions only)

**Step 1: Make executable**

Run: `chmod +x .worktrees/inline-superpowers-skills/scripts/import-skills.sh`

**Step 2: Test a dry run by adding a `--dry-run` flag**

Add to the top of `main()`, after the echo line:

```bash
  local dry_run=false
  if [[ "${1:-}" == "--dry-run" ]]; then
    dry_run=true
    echo "(dry run — will show prompts but not call claude)"
  fi
```

And in `import_skill`, pass `dry_run` through. Add a parameter and check:

Actually, this adds complexity. Instead, just run the script and let it work. If `claude` isn't available or the clone fails, we'll see the error.

**Step 2 (revised): Run the script and observe**

Run: `cd .worktrees/inline-superpowers-skills && bash scripts/import-skills.sh`

Expected: The script clones superpowers, runs `claude -p` 4 times, and writes 4 files into `skills/`. This will take a few minutes due to the Claude calls.

If it works, verify the outputs:

Run: `ls -la .worktrees/inline-superpowers-skills/skills/*/SKILL.md`
Expected: 4 files, each non-empty

Run: `head -6 .worktrees/inline-superpowers-skills/skills/trycycle-planning/SKILL.md`
Expected: Attribution header with `<!-- base-commit: ... -->`

**Step 3: Commit the generated skills**

```bash
git -C .worktrees/inline-superpowers-skills add scripts/import-skills.sh skills/
git -C .worktrees/inline-superpowers-skills commit -m "feat: import and adapt 4 superpowers skills as trycycle subskills"
```

---

### Task 8: Update the trycycle orchestrator SKILL.md

**Files:**
- Modify: `SKILL.md`

**Step 1: Read current SKILL.md**

Read `SKILL.md` to confirm current skill references.

**Step 2: Replace all superpowers skill references with trycycle-prefixed names**

Make these replacements throughout `SKILL.md`:

| Find | Replace |
|------|---------|
| `` `using-git-worktrees` skill `` | `` `trycycle-worktrees` skill `` |
| `` `writing-plans` skill `` | `` `trycycle-planning` skill `` |
| `` `executing-plans` skill `` | `` `trycycle-executing` skill `` |
| `` `finishing-a-development-branch` skill `` | `` `trycycle-finishing` skill `` |
| `superpowers:executing-plans` | `trycycle-executing` |
| `superpowers:finishing-a-development-branch` | `trycycle-finishing` |

Specifically, these lines change:

- Line 33: `Use the \`using-git-worktrees\` skill` → `Use the \`trycycle-worktrees\` skill`
- Line 72: `Use the \`writing-plans\` skill` → `Use the \`trycycle-planning\` skill`
- Line 73: `The \`writing-plans\` skill may reference` → `The \`trycycle-planning\` skill may reference`
- Line 99: `Ensure that it aligns completely with the \`writing-plans\` skill` → `Ensure that it aligns completely with the \`trycycle-planning\` skill`
- Line 144: `Use the executing-plans skill` → `Use the trycycle-executing skill`
- Line 217: `use the \`finishing-a-development-branch\` skill` → `use the \`trycycle-finishing\` skill`

**Step 3: Verify no superpowers references remain**

Run: `grep -i 'superpowers\|using-git-worktrees\|writing-plans\|executing-plans\|finishing-a-development-branch' .worktrees/inline-superpowers-skills/SKILL.md`
Expected: No output (all references replaced)

**Step 4: Commit**

```bash
git -C .worktrees/inline-superpowers-skills add SKILL.md
git -C .worktrees/inline-superpowers-skills commit -m "feat: update orchestrator to reference inlined trycycle subskills"
```

---

### Task 9: Update the README

**Files:**
- Modify: `README.md`

**Step 1: Read current README.md**

Read `README.md` to see the current install instructions.

**Step 2: Remove the superpowers prerequisite section**

Remove the entire "Prerequisites" section (lines 7-22 approximately) that instructs users to install superpowers.

**Step 3: Replace with a brief note about origins**

Add after the opening description:

```markdown
## Credits

Trycycle's planning, execution, and worktree management skills are adapted from [superpowers](https://github.com/obra/superpowers) by Jesse Vincent. They are included directly in this repo so you don't need to install superpowers separately.
```

**Step 4: Simplify "Installing trycycle" section**

The install instructions should remain the same (just clone trycycle), but remove any mention of installing superpowers as a prerequisite.

**Step 5: Verify no superpowers install instructions remain**

Run: `grep -i 'superpowers\|plugin.*marketplace\|plugin.*install' .worktrees/inline-superpowers-skills/README.md`
Expected: Only the Credits section reference to superpowers, no install instructions.

**Step 6: Commit**

```bash
git -C .worktrees/inline-superpowers-skills add README.md
git -C .worktrees/inline-superpowers-skills commit -m "docs: remove superpowers prerequisite, add credits section"
```

---

### Task 10: Verify the complete result

**Files:** (none modified — verification only)

**Step 1: Verify directory structure**

Run: `find .worktrees/inline-superpowers-skills -not -path '*/.git/*' -not -path '*/.git' -not -path '*/node_modules/*' | sort`

Expected:
```
.worktrees/inline-superpowers-skills
.worktrees/inline-superpowers-skills/.claude
.worktrees/inline-superpowers-skills/.claude/worktrees
.worktrees/inline-superpowers-skills/.gitignore
.worktrees/inline-superpowers-skills/LICENSE
.worktrees/inline-superpowers-skills/README.md
.worktrees/inline-superpowers-skills/SKILL.md
.worktrees/inline-superpowers-skills/docs
.worktrees/inline-superpowers-skills/docs/plans
.worktrees/inline-superpowers-skills/docs/plans/2026-03-06-inline-superpowers-skills.md
.worktrees/inline-superpowers-skills/scripts
.worktrees/inline-superpowers-skills/scripts/import-skills.sh
.worktrees/inline-superpowers-skills/scripts/prompt-template.txt
.worktrees/inline-superpowers-skills/skills
.worktrees/inline-superpowers-skills/skills/trycycle-executing
.worktrees/inline-superpowers-skills/skills/trycycle-executing/SKILL.md
.worktrees/inline-superpowers-skills/skills/trycycle-finishing
.worktrees/inline-superpowers-skills/skills/trycycle-finishing/SKILL.md
.worktrees/inline-superpowers-skills/skills/trycycle-planning
.worktrees/inline-superpowers-skills/skills/trycycle-planning/SKILL.md
.worktrees/inline-superpowers-skills/skills/trycycle-worktrees
.worktrees/inline-superpowers-skills/skills/trycycle-worktrees/SKILL.md
```

**Step 2: Verify all adapted skills have the attribution header**

Run: `for f in .worktrees/inline-superpowers-skills/skills/*/SKILL.md; do echo "=== $f ==="; head -5 "$f"; done`
Expected: Each file starts with `<!-- trycycle-*: adapted from obra/superpowers ... -->` header

**Step 3: Verify no superpowers references in orchestrator**

Run: `grep -r 'superpowers' .worktrees/inline-superpowers-skills/SKILL.md .worktrees/inline-superpowers-skills/README.md`
Expected: Only the credits line in README.md

**Step 4: Verify the adapted skills reference trycycle, not superpowers**

Run: `grep -r 'superpowers:' .worktrees/inline-superpowers-skills/skills/`
Expected: No output (all `superpowers:X` references replaced with `trycycle-X`)

**Step 5: Show the full diff for review**

Run: `git -C .worktrees/inline-superpowers-skills diff --stat main...HEAD`
Expected: Shows all files changed across all commits
