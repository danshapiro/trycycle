#!/usr/bin/env bash
set -euo pipefail
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
git -C "$SKILL_DIR" fetch --tags --quiet 2>/dev/null || exit 0
LOCAL="$(git -C "$SKILL_DIR" describe --tags --abbrev=0 HEAD 2>/dev/null || echo "none")"
REMOTE="$(git -C "$SKILL_DIR" describe --tags --abbrev=0 origin/main 2>/dev/null || echo "none")"
if [[ "$LOCAL" != "$REMOTE" && "$REMOTE" != "none" ]]; then
  echo "UPDATE AVAILABLE: Trycycle $REMOTE is out (you have $LOCAL)."
  echo "Run: git -C $SKILL_DIR pull"
else
  echo "Trycycle $LOCAL — up to date."
fi
