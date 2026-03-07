---
name: trycycle-brakes
description: "Internal trycycle subskill — do not invoke directly."
---

# Trycycle Brakes Setup

## Overview

Detect the project's stack and set up external verification hooks ("brakes")
that the agent cannot bypass. Brakes run real commands (build, test, lint,
typecheck) and block commits or session completion if they fail.

## Step 1: Check for existing config

Look for `trycycle-brakes.json` in the project root (the worktree root, not
the trycycle skill directory).

If it exists, read it and verify the commands are still valid:
- For each command in `verify`, check that the underlying tool exists
  (e.g., if `npm test` is configured, confirm `package.json` has a `test` script)
- Report any stale commands and offer to fix them
- If everything looks good, return the config and stop here

## Step 2: Detect project stack

If no config exists, detect what's available:

### Node.js / TypeScript
- `package.json` exists?
  - Read `scripts` — look for `test`, `build`, `lint`, `typecheck`
  - Map each found script to `npm run <name>`
- `tsconfig.json` exists? Add `npx tsc --noEmit` as `typecheck` (if no script already)
- `eslint.config.*` or `.eslintrc*` exists? Add `npx eslint .` as `lint` (if no script already)

### Rust
- `Cargo.toml` exists?
  - `cargo build` for build
  - `cargo test` for test
  - `cargo clippy -- -D warnings` for lint

### Python
- `pyproject.toml` or `setup.py` exists?
  - `pytest` for test (if pytest in dependencies)
  - `mypy .` for typecheck (if mypy in dependencies)
  - `ruff check .` for lint (if ruff in dependencies)

### Go
- `go.mod` exists?
  - `go build ./...` for build
  - `go test ./...` for test
  - `go vet ./...` for lint

### Test patterns
Set `testPatterns` based on detected stack:
- Node: `["**/*.test.*", "**/*.spec.*", "**/__tests__/**"]`
- Rust: `["**/tests/**", "**/*_test.rs"]`
- Python: `["**/test_*.py", "**/*_test.py", "tests/**"]`
- Go: `["**/*_test.go"]`

### Plan glob
Always: `"docs/plans/*.md"`

## Step 3: Propose config to user

Present the detected config clearly:

```
I'd like to set up brakes for this project. These are external verification
checks that run automatically before commits and when the cycle finishes.
The agent cannot bypass them.

Based on your project:

  build:     npm run build
  test:      npm test
  typecheck: npx tsc --noEmit

Want me to create trycycle-brakes.json with these? You can edit it anytime.
```

Wait for confirmation. If the user wants changes, adjust accordingly.

## Step 4: Write config

Write `trycycle-brakes.json` to the project root:

```json
{
  "verify": {
    "build": "npm run build",
    "test": "npm test",
    "typecheck": "npx tsc --noEmit"
  },
  "testPatterns": ["**/*.test.*", "**/*.spec.*"],
  "planGlob": "docs/plans/*.md",
  "strictScope": false
}
```

## Step 5: Wire hooks

Check if `.claude/settings.json` exists in the project root. If not, create it.

Determine the trycycle hooks directory path. This is the `hooks/` directory
inside the trycycle skill installation (sibling to this skill file's parent).

Add or merge the following into `.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "bash <TRYCYCLE_HOOKS_DIR>/pre-commit-verify.sh"
          },
          {
            "type": "command",
            "command": "bash <TRYCYCLE_HOOKS_DIR>/scope-guard.sh"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "bash <TRYCYCLE_HOOKS_DIR>/test-integrity.sh"
          }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "bash <TRYCYCLE_HOOKS_DIR>/stop-verify.sh"
          }
        ]
      }
    ]
  }
}
```

Replace `<TRYCYCLE_HOOKS_DIR>` with the actual absolute path to the hooks directory.

If `.claude/settings.json` already has a `hooks` key, merge carefully — do not
overwrite existing hooks. Append trycycle hooks to existing arrays.

## Step 6: Confirm

Report what was set up:

```
Brakes installed:
- trycycle-brakes.json: verification commands for this project
- .claude/settings.json: hooks that enforce verification before commits and at session end

Brakes active:
  Pre-commit:     build, test, typecheck (blocks commit on failure)
  Test integrity:  warns if test assertions are removed
  Scope guard:     warns if files outside the plan are changed
  Stop gate:       blocks session completion if verification fails

You can edit trycycle-brakes.json anytime to add, remove, or change checks.
Set "strictScope": true to block (not just warn) on out-of-plan file changes.
```
