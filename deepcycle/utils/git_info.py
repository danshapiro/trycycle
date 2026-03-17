from __future__ import annotations

import subprocess
from pathlib import Path


def try_get_git_sha(repo_dir: Path) -> str | None:
    try:
        out = subprocess.check_output(["git", "-C", str(repo_dir), "rev-parse", "HEAD"], stderr=subprocess.DEVNULL)
        return out.decode("utf-8").strip()
    except Exception:
        return None
