#!/usr/bin/env bash
# Trycycle Brake: Pre-Commit Verification Gate
#
# Runs before every git commit. Executes all verification commands declared
# in trycycle-brakes.json. Blocks the commit (exit 2) if any check fails.
#
# This is a Claude Code hook (PreToolUse on Bash). The agent cannot bypass it.

set -euo pipefail

input=$(cat)
command=$(echo "$input" | jq -r '.tool_input.command // ""')

# Only gate git commits
if ! echo "$command" | grep -qE '\bgit\b.*\bcommit\b'; then
  exit 0
fi

project_dir="${CLAUDE_PROJECT_DIR:-.}"
config="$project_dir/trycycle-brakes.json"

if [ ! -f "$config" ]; then
  exit 0
fi

verify_keys=$(jq -r '.verify | keys[]' "$config" 2>/dev/null)
if [ -z "$verify_keys" ]; then
  exit 0
fi

failed=()
outputs=()

for key in $verify_keys; do
  cmd=$(jq -r ".verify[\"$key\"]" "$config")
  if ! output=$(cd "$project_dir" && eval "$cmd" 2>&1); then
    failed+=("$key")
    outputs+=("--- $key failed ---
$output")
  fi
done

if [ ${#failed[@]} -gt 0 ]; then
  echo "BRAKE: Commit blocked. Failing checks: ${failed[*]}" >&2
  echo "" >&2
  for out in "${outputs[@]}"; do
    echo "$out" | tail -30 >&2
    echo "" >&2
  done
  echo "Fix these verification failures before committing." >&2
  exit 2
fi

exit 0
