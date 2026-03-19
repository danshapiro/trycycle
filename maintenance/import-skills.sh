#!/usr/bin/env bash
set -euo pipefail

# Allow running from within a Claude Code session
unset CLAUDECODE 2>/dev/null || true

REPO_URL="https://github.com/obra/superpowers.git"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TRYCYCLE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SKILLS_DIR="$TRYCYCLE_ROOT/subskills"
SUBSKILL_DESCRIPTION="Internal trycycle subskill — do not invoke directly."
TEMP_DIR=""

cleanup() {
  if [[ -n "$TEMP_DIR" && -d "$TEMP_DIR" ]]; then
    rm -rf "$TEMP_DIR"
  fi
}
trap cleanup EXIT

# Map trycycle skill names to superpowers source skill directory names.
# Use a case statement so the script works on macOS's default Bash 3.2.
source_skill_name_for() {
  case "$1" in
    trycycle-worktrees) echo "using-git-worktrees" ;;
    trycycle-planning) echo "writing-plans" ;;
    trycycle-executing) echo "executing-plans" ;;
    trycycle-finishing) echo "finishing-a-development-branch" ;;
    *)
      echo "ERROR: unknown trycycle skill name: $1" >&2
      return 1
      ;;
  esac
}

# Extract base-commit from an existing adapted skill's header.
# Returns empty string if no header found (first import).
parse_base_commit() {
  local skill_file="$1"
  if [[ -f "$skill_file" ]]; then
    grep '<!-- base-commit:' "$skill_file" | sed 's/.*base-commit: *\([a-f0-9]*\).*/\1/' | head -1
  fi
}

# Generate the diff of the upstream source skill between base-commit and current HEAD.
# This shows what Jesse changed since we last imported.
generate_source_diff() {
  local superpowers_repo="$1"
  local source_name="$2"
  local base_commit="$3"
  local skill_path="skills/$source_name/SKILL.md"

  if [[ -n "$base_commit" ]]; then
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
      local base_source
      base_source="$(git -C "$superpowers_repo" show "$full_hash:$skill_path" 2>/dev/null || true)"
      if [[ -n "$base_source" ]]; then
        diff -u <(echo "$base_source") "$trycycle_skill_file" || true
      fi
    fi
  fi
}

# Build the full prompt for claude -p by substituting placeholders in the template.
build_prompt() {
  local trycycle_name="$1"
  local source_name="$2"
  local upstream_head="$3"
  local upstream_source="$4"
  local source_diff="$5"
  local adaptation_diff="$6"
  local existing_adaptation="$7"
  local skill_description="$8"
  local skill_instructions="$9"
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

  # Use python for safe template substitution to avoid bash string replacement issues
  python3 -c "
import sys
template = sys.stdin.read()
replacements = {
    '{{TRYCYCLE_ROOT}}': sys.argv[1],
    '{{SOURCE_NAME}}': sys.argv[2],
    '{{TRYCYCLE_NAME}}': sys.argv[3],
    '{{UPSTREAM_HEAD}}': sys.argv[4],
    '{{TODAY}}': sys.argv[5],
    '{{UPSTREAM_SOURCE}}': sys.argv[6],
    '{{SOURCE_DIFF_SECTION}}': sys.argv[7],
    '{{ADAPTATION_DIFF_SECTION}}': sys.argv[8],
    '{{EXISTING_ADAPTATION_SECTION}}': sys.argv[9],
    '{{TRYCYCLE_DESCRIPTION}}': sys.argv[10],
    '{{SKILL_SPECIFIC_INSTRUCTIONS}}': sys.argv[11],
}
for key, val in replacements.items():
    template = template.replace(key, val)
print(template)
" "$TRYCYCLE_ROOT" "$source_name" "$trycycle_name" "$upstream_head" "$today" \
  "$upstream_source" "$source_diff_section" "$adaptation_diff_section" \
  "$existing_adaptation_section" "$skill_description" "$skill_instructions" <<< "$template"
}

validate_adapted_skill_frontmatter() {
  local expected_name="$1"
  local expected_description="$2"
  local output="$3"

  python3 - "$expected_name" "$expected_description" "$output" <<'PY'
import sys

expected_name, expected_description, output = sys.argv[1:4]
lines = output.splitlines()

if not lines or lines[0] != "---":
    raise SystemExit("adapted skill must start with YAML frontmatter")

try:
    closing_idx = lines.index("---", 1)
except ValueError as exc:
    raise SystemExit("adapted skill is missing the closing frontmatter delimiter") from exc

if closing_idx < 2:
    raise SystemExit("adapted skill frontmatter is empty or malformed")

values = {}
for line in lines[1:closing_idx]:
    if ":" not in line:
        continue
    key, value = line.split(":", 1)
    values[key.strip()] = value.strip().strip('"').strip("'")

actual_name = values.get("name")
actual_description = values.get("description")

if actual_name != expected_name:
    raise SystemExit(
        f"expected frontmatter name {expected_name!r}, got {actual_name!r}"
    )

if actual_description != expected_description:
    raise SystemExit(
        "expected frontmatter description "
        f"{expected_description!r}, got {actual_description!r}"
    )

comment_idx = closing_idx + 1
if comment_idx >= len(lines) or not lines[comment_idx].startswith("<!-- "):
    raise SystemExit("adapted skill must put attribution comments immediately after frontmatter")
PY
}

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

  # 4. Read skill-specific instructions
  local skill_instructions
  skill_instructions="$(cat "$SCRIPT_DIR/skill-instructions/$trycycle_name.txt")"

  # 5. Build prompt
  local prompt
  prompt="$(build_prompt "$trycycle_name" "$source_name" "$upstream_head" \
    "$upstream_source" "$source_diff" "$adaptation_diff" "$existing_adaptation" \
    "$SUBSKILL_DESCRIPTION" "$skill_instructions")"

  # 6. Run claude -p
  echo "  Running claude -p for adaptation..."
  local raw_output
  raw_output="$(echo "$prompt" | claude -p \
    --model claude-sonnet-4-6 \
    --dangerously-skip-permissions \
    --add-dir "$TRYCYCLE_ROOT" 2>/dev/null)"

  # 7. Extract content from <adapted-skill> tags
  local output
  output="$(echo "$raw_output" | sed -n '/<adapted-skill>/,/<\/adapted-skill>/{ /<adapted-skill>/d; /<\/adapted-skill>/d; p; }')"

  if [[ -z "$output" ]]; then
    echo "  ERROR: no <adapted-skill> tags found in claude output"
    echo "  Raw output (first 10 lines):"
    echo "$raw_output" | head -10 | sed 's/^/    /'
    return 1
  fi

  # 8. Check for ABORT
  if [[ "$output" == ABORT* ]]; then
    echo "  ABORTED — adaptation not possible:"
    echo "$output" | sed 's/^/    /'
    return 1
  fi

  if ! validate_adapted_skill_frontmatter "$trycycle_name" "$SUBSKILL_DESCRIPTION" "$output"; then
    echo "  ERROR: adapted skill frontmatter validation failed for $trycycle_name"
    return 1
  fi

  # 9. Write output
  mkdir -p "$SKILLS_DIR/$trycycle_name"
  printf '%s\n' "$output" > "$trycycle_skill_file"
  echo "  Written to $trycycle_skill_file"
  return 0
}

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

  for trycycle_name in trycycle-worktrees trycycle-planning trycycle-executing trycycle-finishing; do
    local source_name
    source_name="$(source_skill_name_for "$trycycle_name")"
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
