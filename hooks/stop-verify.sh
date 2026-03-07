#!/usr/bin/env bash
# Trycycle Brake: Stop Gate
#
# Runs when Claude is about to end the conversation. Executes the full
# verification suite one final time. Blocks completion if any check fails.
#
# This is a Claude Code hook (Stop event).

set -euo pipefail

project_dir="${CLAUDE_PROJECT_DIR:-.}"
config="$project_dir/trycycle-brakes.json"

[ ! -f "$config" ] && exit 0

verify_keys=$(jq -r '.verify | keys[]' "$config" 2>/dev/null)
[ -z "$verify_keys" ] && exit 0

# Only run if there are recent changes in this project
has_changes=$(cd "$project_dir" && git diff --name-only HEAD~5..HEAD 2>/dev/null | wc -l || echo "0")
[ "$has_changes" -eq 0 ] && exit 0

failed=()
outputs=()

for key in $verify_keys; do
  cmd=$(jq -r ".verify[\"$key\"]" "$config")
  if ! output=$(cd "$project_dir" && eval "$cmd" 2>&1); then
    failed+=("$key")
    outputs+=("--- $key ---
$output")
  fi
done

if [ ${#failed[@]} -gt 0 ]; then
  echo "BRAKE: Cannot finish. Verification failures: ${failed[*]}" >&2
  echo "" >&2
  for out in "${outputs[@]}"; do
    echo "$out" | tail -20 >&2
    echo "" >&2
  done
  echo "Fix these before declaring the task complete." >&2
  exit 2
fi

exit 0
