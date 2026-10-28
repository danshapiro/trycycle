# Empty Task Result Repair Plan

> **For Claude:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When OpenCode's native `task` tool returns empty `<task_result>` (because the subagent's final message has no text parts), deterministically extract the subagent's actual output from the OpenCode session database.

**Architecture:** A Python script that queries the OpenCode SQLite database (`~/.local/share/opencode/opencode.db`), reads the `part` table for a given session ID, walks backward from the last `step-finish` to the previous one to find the final assistant message boundary, collects tool call outputs and reasoning from that message's parts, and formats them as text.

**Tech Stack:** Python 3 (stdlib only — `sqlite3`, `json`, `argparse`)

---

### Task 1: Write the repair script

**Files:**
- Create: `orchestrator/repair_empty_result.py`
- Test: none (per AGENTS.md: "Don't create tests for skill changes")

- [ ] **Step 1: Write the extraction script**

```python
#!/usr/bin/env python3
"""
Deterministic repair for OpenCode task tool empty results.

When OpenCode's native task tool returns empty <task_result> because the
subagent's final assistant message has no text parts, this script reads
the session database and extracts tool outputs + reasoning as text.

Database schema (from opencode.db):
  session(id, parent_id, ...)
  message(id, session_id, data)
  part(id, message_id, session_id, data)

The `part.data` column holds JSON. Part types include:
  - "step-start" / "step-finish" — message boundaries
  - "text" — visible text (what findLast looks for)
  - "tool" — tool call with state.output containing the result
  - "reasoning" — model reasoning
"""

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any


def resolve_db_path() -> Path:
    """Find the OpenCode database path."""
    # XDG data directory
    data_home = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
    db_path = Path(data_home) / "opencode" / "opencode.db"
    if db_path.exists():
        return db_path
    # Windows paths via WSL
    for base in ["/mnt/c/Users"]:
        for user_dir in Path(base).iterdir():
            if user_dir.is_dir():
                p = user_dir / ".local" / "share" / "opencode" / "opencode.db"
                if p.exists():
                    return p
    raise FileNotFoundError("Cannot find opencode.db. Set OPENCODE_DB_PATH.")


def get_parts(db_path: Path, session_id: str) -> list[dict[str, Any]]:
    """Return all parts for a session, ordered by time_created."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT data FROM part WHERE session_id = ? ORDER BY time_created",
        (session_id,),
    ).fetchall()
    conn.close()
    return [json.loads(row["data"]) for row in rows]


def find_last_message_parts(parts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Walk backwards from the last step-finish to find the final assistant message."""
    # Find the last step-finish
    finish_idx = None
    for i in range(len(parts) - 1, -1, -1):
        if parts[i].get("type") == "step-finish":
            finish_idx = i
            break

    if finish_idx is None:
        return parts  # Fallback: return everything

    # Walk backwards from the finish to the previous step-finish/step-start
    start_idx = 0
    for i in range(finish_idx - 1, -1, -1):
        if parts[i].get("type") in ("step-finish", "step-start"):
            start_idx = i + 1
            break

    return parts[start_idx : finish_idx + 1]


def format_parts(parts: list[dict[str, Any]]) -> str:
    """Format message parts into readable text."""
    lines: list[str] = []

    for part in parts:
        ptype = part.get("type", "")

        if ptype == "tool":
            tool_name = part.get("tool", "unknown")
            state = part.get("state", {})
            tool_input = state.get("input", {})
            tool_output = state.get("output", "")
            status = state.get("status", "unknown")

            lines.append(f"## Tool: {tool_name} (status: {status})")
            if tool_input:
                lines.append(f"  Input: {json.dumps(tool_input)}")
            if tool_output:
                # Truncate very long outputs
                if len(tool_output) > 5000:
                    tool_output = tool_output[:5000] + "\n... (truncated)"
                lines.append(f"  Output:\n{tool_output}")
            lines.append("")

        elif ptype == "reasoning":
            reasoning_text = part.get("text", "")
            if reasoning_text.strip():
                lines.append(f"## Reasoning")
                lines.append(reasoning_text)
                lines.append("")

        elif ptype == "text":
            text = part.get("text", "")
            # Skip XML close tags and whitespace-only
            if text.strip() and not text.strip().startswith("</"):
                lines.append(text)
                lines.append("")

    result = "\n".join(lines).strip()
    if not result:
        result = "(no extractable content found in subagent session parts)"

    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract subagent output from OpenCode session database"
    )
    parser.add_argument(
        "--session-id", required=True, help="Subagent session ID (e.g. ses_1efec896fffe...)"
    )
    parser.add_argument(
        "--db-path",
        default=None,
        help="Path to opencode.db (default: auto-detect)",
    )
    args = parser.parse_args()

    try:
        db_path = Path(args.db_path) if args.db_path else resolve_db_path()
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 1

    parts = get_parts(db_path, args.session_id)
    if not parts:
        print(f"No parts found for session {args.session_id}", file=sys.stderr)
        return 1

    message_parts = find_last_message_parts(parts)
    output = format_parts(message_parts)
    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Test against the known good repro session**

```bash
python3 /home/user/code/trycycle/orchestrator/repair_empty_result.py \
  --session-id ses_1efec896fffedtihFaWbx3ElpD
```
Expected: Output containing the README.md contents that the subagent read.

- [ ] **Step 3: Test with a session that has no tool calls (edge case)**

```bash
python3 /home/user/code/trycycle/orchestrator/repair_empty_result.py \
  --session-id <a-session-with-only-text>
```
Expected: Returns the text content, or "(no extractable content)" for reasoning-only.

- [ ] **Step 4: Commit**

```bash
git add orchestrator/repair_empty_result.py
git commit -m "feat: add deterministic repair for empty task results"
```

---

### Task 2: Wire into SKILL.md orchestrator instructions

**Files:**
- Modify: `SKILL.md` (add empty-result gate to native-mode dispatch instructions)

- [ ] **Step 5: Add empty-result detection and repair to SKILL.md**

Add a new section in the Subagent Defaults or Phase wrapper helper section:

```markdown
## Empty Task Result Repair (OpenCode native mode)

OpenCode's native `task` tool can return empty `<task_result>` when a subagent's
final assistant message contains no text parts (only tool calls or reasoning).

When using OpenCode in native mode: after dispatching any subagent, check the
result. If the raw task tool output is empty (only whitespace inside
`<task_result>` tags), repair it:

```bash
python3 <skill-directory>/orchestrator/repair_empty_result.py --session-id <task-id>
```

Read the script's stdout and treat it as the subagent's actual result. This is
deterministic — it reads structured part data from the subagent's session
database, no AI re-prompting needed.
```

This section should go after the Subagent Defaults section (after line 111 in SKILL.md).

- [ ] **Step 6: Commit**

```bash
git add SKILL.md
git commit -m "docs: add empty task result repair instructions for OpenCode"
```

---

### Verification

After implementation, verify with the repro session from the bug investigation:

1. Simulate the repair:
```bash
python3 orchestrator/repair_empty_result.py --session-id ses_1efec896fffedtihFaWbx3ElpD
```
Confirm it outputs the README.md contents the subagent read.

2. Manual end-to-end test: dispatch a subagent via task, confirm it ends on a tool call, verify empty result, run repair script, confirm extracted output is correct.
