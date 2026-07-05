---
name: trycycle-finishing
description: "Internal trycycle subskill — do not invoke directly."
---
<!-- trycycle-finishing: adapted from https://github.com/obra/superpowers finishing-a-development-branch -->
<!-- base-commit: 7e51643 -->
<!-- imported: 2026-03-18 -->

# Finishing a Development Branch

## Overview

Guide completion of development work by presenting clear options and handling chosen workflow.

**Core principle:** Confirm verification → Present options → Execute choice → Clean up.

## The Process

### Step 1: Confirm Verification

Trycycle invokes this skill only after the acceptance-artifact and post-implementation review loop has passed for the current `HEAD`, and the orchestrator has already run the final workspace hygiene checks. That passing result is the evidence — do not rerun the test suite here. Rerun tests only on states the verification loop never saw, such as the merged result in Option 1.

If the verification loop has not passed for the current `HEAD`, stop: this skill was invoked too early.

### Step 2: Determine Base Branch

Use `{BASE_BRANCH}` recorded during workspace preparation. If it is unset, detect it: prefer `CONDUCTOR_DEFAULT_BRANCH` when set and non-empty, otherwise the repo's configured remote default branch, then `main`, then `master`. Do not ask the user.

### Step 3: Present Options

Present exactly these 4 options:

```
Implementation complete. What would you like to do?

1. Merge back to <base-branch> locally
2. Push and create a Pull Request
3. Keep the workspace as-is (I'll handle it later)
4. Discard this work

Which option?
```

**Don't add explanation** - keep options concise.

### Step 4: Execute Choice

#### Option 1: Merge Locally

```bash
# Switch to base branch
git checkout <base-branch>

# Pull latest
git pull

# Merge feature branch
git merge <feature-branch>

# Verify tests on merged result
<test command>

# If tests pass
git branch -d <feature-branch>
```

Then: Cleanup workspace (Step 5)

#### Option 2: Push and Create PR

```bash
# Push branch
git push -u origin <feature-branch>

# Create PR
gh pr create --title "<title>" --body "$(cat <<'EOF'
## Summary
<paste the latest `## Implementation summary` returned by the implementation subagent here>

## Test Plan
<paste the latest `## Verification results` returned by the implementation subagent here>

## Residual Issues
<if the reviewer reported any residual issues, list them here; otherwise omit this section>
EOF
)"
```

Then: Cleanup workspace (Step 5)

#### Option 3: Keep As-Is

Report: "Keeping branch <name>. Workspace preserved at <path>."

**Don't cleanup workspace.**

#### Option 4: Discard

**Confirm first:**
```
This will permanently delete:
- Branch <name>
- All commits: <commit-list>
- Workspace at <path>

Type 'discard' to confirm.
```

Wait for exact confirmation.

If confirmed:
```bash
git checkout <base-branch>
git branch -D <feature-branch>
```

Then: Cleanup workspace (Step 5)

### Step 5: Cleanup Workspace

**For Options 1, 2, 4:**

**Default mode** (dedicated git worktree was created):

Check if in worktree:
```bash
git worktree list | grep $(git branch --show-current)
```

If yes:
```bash
git worktree remove <worktree-path>
```

**`--no-worktree` mode** (current workspace was reused):

Do not attempt to remove the current workspace. Only perform the branch actions relevant to the chosen option (e.g. delete the feature branch for Options 1 and 4). Leave the workspace directory untouched.

**For Option 3:** Keep workspace in either mode.

## Quick Reference

| Option | Merge | Push | Keep Workspace | Cleanup Branch |
|--------|-------|------|----------------|----------------|
| 1. Merge locally | ✓ | - | - | ✓ |
| 2. Create PR | - | ✓ | ✓ | - |
| 3. Keep as-is | - | - | ✓ | - |
| 4. Discard | - | - | - | ✓ (force) |

## Common Mistakes

**Rerunning the full test suite here**
- **Problem:** Duplicates the verification loop's finished work and can drift from the reviewed `HEAD`
- **Fix:** Trust the passed verification loop; run tests only on states it never saw, like the merged result in Option 1

**No confirmation for discard**
- **Problem:** Accidentally delete work
- **Fix:** Require typed "discard" confirmation

## Red Flags

**Never:**
- Proceed with failing tests
- Merge without verifying tests on result
- Delete work without confirmation
- Force-push without explicit request
- Remove the current workspace in `--no-worktree` mode

**Always:**
- Confirm the verification loop passed for the current `HEAD` before offering options
- Present exactly 4 options
- Get typed confirmation for Option 4
- Clean up worktree for Options 1 & 4 only (default mode)
