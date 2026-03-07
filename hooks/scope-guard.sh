#!/usr/bin/env bash
# Trycycle Brake: Scope Guard
#
# Runs before git commits. Compares staged files against the plan's declared
# file list. Warns (or blocks in strict mode) if files were changed that
# aren't in the plan.
#
# This is a Claude Code hook (PreToolUse on Bash).

set -euo pipefail

input=$(cat)
command=$(echo "$input" | jq -r '.tool_input.command // ""')

if ! echo "$command" | grep -qE '\bgit\b.*\bcommit\b'; then
  exit 0
fi

project_dir="${CLAUDE_PROJECT_DIR:-.}"
config="$project_dir/trycycle-brakes.json"
[ ! -f "$config" ] && exit 0

plan_glob=$(jq -r '.planGlob // ""' "$config" 2>/dev/null)
[ -z "$plan_glob" ] && exit 0

# Find the most recent plan file
plan_file=$(find "$project_dir" -path "$project_dir/$plan_glob" -type f 2>/dev/null \
  | xargs ls -t 2>/dev/null | head -1)
[ -z "$plan_file" ] && exit 0

# Extract declared files from plan (Create/Modify/Test/Edit/Update/Delete/Add: `path`)
declared_files=$(grep -oE '(Create|Modify|Test|Edit|Update|Delete|Add):\s*`[^`]+`' "$plan_file" 2>/dev/null \
  | sed 's/.*`\(.*\)`.*/\1/' \
  | sed 's/:.*//' \
  | sort -u)

[ -z "$declared_files" ] && exit 0

# Get staged files
changed_files=$(cd "$project_dir" && git diff --cached --name-only 2>/dev/null | sort -u)
[ -z "$changed_files" ] && exit 0

# Find files changed but not declared in plan
# Exclude plan files themselves and common generated files
unexpected=$(comm -23 <(echo "$changed_files") <(echo "$declared_files") \
  | grep -vE '^(docs/plans/|\.gitignore$|package-lock\.json$|yarn\.lock$|Cargo\.lock$|poetry\.lock$|trycycle-brakes\.json$)' \
  || true)

if [ -n "$unexpected" ]; then
  echo "BRAKE: Files changed that aren't declared in the plan:" >&2
  echo "$unexpected" | sed 's/^/  - /' >&2
  echo "" >&2
  echo "If intentional, update the plan's Files section first." >&2

  strict=$(jq -r '.strictScope // false' "$config" 2>/dev/null)
  if [ "$strict" = "true" ]; then
    echo "Strict scope mode is on. Commit blocked." >&2
    exit 2
  fi
fi

exit 0
