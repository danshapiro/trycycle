#!/usr/bin/env bash
# Trycycle Brake: Test Integrity Guard
#
# Runs after every Edit/Write to a test file. Detects if assertions or test
# cases were removed without replacement. Feeds a warning back to Claude.
#
# This is a Claude Code hook (PostToolUse on Edit|Write). Advisory, not blocking.

set -euo pipefail

input=$(cat)
tool=$(echo "$input" | jq -r '.tool_name // ""')

file_path=""
if [ "$tool" = "Edit" ] || [ "$tool" = "Write" ]; then
  file_path=$(echo "$input" | jq -r '.tool_input.file_path // ""')
fi

[ -z "$file_path" ] && exit 0

project_dir="${CLAUDE_PROJECT_DIR:-.}"
config="$project_dir/trycycle-brakes.json"
[ ! -f "$config" ] && exit 0

# Check if this file matches test patterns from config
is_test=false
while IFS= read -r pattern; do
  [ -z "$pattern" ] && continue
  if echo "$file_path" | grep -qE '(test|spec|__tests__|_test\.)'; then
    is_test=true
    break
  fi
done < <(jq -r '.testPatterns[]? // empty' "$config" 2>/dev/null)

# Fallback: check common test indicators if no patterns configured
if [ "$is_test" = false ]; then
  if echo "$file_path" | grep -qE '\.(test|spec)\.[^.]+$|__tests__/|_test\.(go|py|rs)$'; then
    is_test=true
  fi
fi

[ "$is_test" = false ] && exit 0

# Check git diff for removed assertions
cd "$project_dir"
diff_output=$(git diff -- "$file_path" 2>/dev/null || true)
[ -z "$diff_output" ] && exit 0

# Count removed vs added assertion-like lines
removed=$(echo "$diff_output" | grep -cE '^\-.*\b(assert|expect|should|test\(|it\(|describe\(|#\[test\]|func Test)' || true)
added=$(echo "$diff_output" | grep -cE '^\+.*\b(assert|expect|should|test\(|it\(|describe\(|#\[test\]|func Test)' || true)

if [ "$removed" -gt "$added" ] && [ "$removed" -gt 0 ]; then
  net=$((removed - added))
  echo "BRAKE WARNING: $file_path lost ~$net assertion/test line(s)." >&2
  echo "Removed $removed, added $added." >&2
  echo "If you weakened tests to make them pass, fix the code instead." >&2
  echo "" >&2
  echo "Removed lines:" >&2
  echo "$diff_output" | grep -E '^\-.*\b(assert|expect|should|test\(|it\(|describe\()' | head -10 >&2
fi

exit 0
