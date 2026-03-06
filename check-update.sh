#!/usr/bin/env bash
set -euo pipefail
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
git -C "$SKILL_DIR" fetch --tags --quiet 2>/dev/null || exit 0
LOCAL="$(git -C "$SKILL_DIR" tag --sort=-v:refname | head -1)"
REMOTE="$(git -C "$SKILL_DIR" ls-remote --tags --sort=-v:refname origin 2>/dev/null | head -1 | sed 's|.*refs/tags/||')"
if [[ -z "$LOCAL" && -z "$REMOTE" ]]; then
  echo "Trycycle (untagged) — up to date."
elif [[ "$LOCAL" != "$REMOTE" && -n "$REMOTE" ]]; then
  echo "UPDATE AVAILABLE: Trycycle $REMOTE is out (you have ${LOCAL:-untagged})."
  echo "Run: git -C $SKILL_DIR pull --tags"
else
  echo "Trycycle $LOCAL — up to date."
fi
