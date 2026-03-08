#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run_git(skill_dir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(skill_dir), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def latest_local_tag(skill_dir: Path) -> str:
    result = run_git(skill_dir, "tag", "--sort=-v:refname")
    if result.returncode != 0:
        return ""
    return next((line.strip() for line in result.stdout.splitlines() if line.strip()), "")


def latest_remote_tag(skill_dir: Path) -> str:
    result = run_git(skill_dir, "ls-remote", "--tags", "--sort=-v:refname", "origin")
    if result.returncode != 0:
        return ""

    first_line = next((line.strip() for line in result.stdout.splitlines() if line.strip()), "")
    if not first_line or "refs/tags/" not in first_line:
        return ""
    return first_line.split("refs/tags/", 1)[1]


def main() -> int:
    skill_dir = Path(__file__).resolve().parent

    fetch_result = run_git(skill_dir, "fetch", "--tags", "--quiet")
    if fetch_result.returncode != 0:
        return 0

    local = latest_local_tag(skill_dir)
    remote = latest_remote_tag(skill_dir)

    if not local and not remote:
        print("Trycycle (untagged) — up to date.")
    elif remote and local != remote:
        print(f"UPDATE AVAILABLE: Trycycle {remote} is out (you have {local or 'untagged'}).")
        print(f"Run: git -C {skill_dir} pull --tags")
    else:
        print(f"Trycycle {local} — up to date.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
