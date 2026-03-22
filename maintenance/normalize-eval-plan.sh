#!/usr/bin/env bash
# Replace stale absolute eval-temp paths in a plan file with the actual repo clone path.
#
# Usage: normalize-eval-plan.sh <plan-file> <repo-clone-path>
#
# Plans created during eval runs embed absolute paths to the eval temp dir
# (e.g., /tmp/trycycle-eval-results-XXXXXX/case_name/repo). When the plan is
# reused as a baseline in a new eval run with a different temp dir, the reviewer
# sees stale paths and "fixes" them — a false positive REVISED verdict.
#
# Run this after checking out the baseline commit and before the reviewer sees
# the plan. It replaces any /tmp/trycycle-eval-results-*/*/repo prefix with
# the current clone path.

set -euo pipefail

if [ $# -ne 2 ]; then
  echo "Usage: $0 <plan-file> <repo-clone-path>" >&2
  exit 1
fi

plan_file="$1"
repo_path="$2"

if [ ! -f "$plan_file" ]; then
  echo "Error: plan file not found: $plan_file" >&2
  exit 1
fi

if [ ! -d "$repo_path" ]; then
  echo "Error: repo path not found: $repo_path" >&2
  exit 1
fi

# Normalize repo_path to remove trailing slash
repo_path="${repo_path%/}"

# Replace /tmp/trycycle-eval-results-ANYTHING/CASE_NAME/repo with current path
# The pattern covers the standard eval runner temp dir layout.
sed -i -E "s|/tmp/trycycle-eval-results-[^/]+/[^/]+/repo|${repo_path}|g" "$plan_file"

# Count replacements for logging (re-run the match on the original via git diff)
changes=$(git -C "$(dirname "$plan_file")" diff --stat -- "$plan_file" 2>/dev/null | tail -1)
if [ -n "$changes" ]; then
  echo "Normalized paths in $(basename "$plan_file"): $changes"
  # Amend the checkout so the reviewer sees a clean baseline
  git -C "$(dirname "$plan_file")" add "$plan_file"
  git -C "$(dirname "$plan_file")" \
    -c user.name="Eval Runner" -c user.email="eval@trycycle" -c commit.gpgsign=false \
    commit -m "eval: normalize stale temp paths to current clone" --quiet
else
  echo "No stale eval paths found in $(basename "$plan_file")"
fi
