---
name: trycycle-worktrees
description: "Internal trycycle subskill — do not invoke directly."
---
<!-- trycycle-worktrees: adapted from https://github.com/obra/superpowers using-git-worktrees -->
<!-- base-commit: 363923f -->
<!-- imported: 2026-03-15 -->

# Using Git Worktrees (trycycle)

## Overview

Git worktrees create isolated workspaces sharing the same repository, allowing work on multiple branches simultaneously without switching. Trycycle repos use `.worktrees/` as the standard worktree directory.

## Create the Worktree

### 1. Verify `.worktrees/` is gitignored

```bash
git check-ignore -q .worktrees
```

**If NOT ignored:** Add `.worktrees` to `.gitignore` and commit before proceeding.

### 2. Create worktree with new branch

```bash
git worktree add .worktrees/<branch-name> -b <branch-name>
cd .worktrees/<branch-name>
```

### 3. Run project setup

Auto-detect and run appropriate setup:

```bash
# Node.js
if [ -f package.json ]; then npm install; fi

# Rust
if [ -f Cargo.toml ]; then cargo build; fi

# Python
if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
if [ -f pyproject.toml ]; then poetry install; fi

# Go
if [ -f go.mod ]; then go mod download; fi
```

### 4. Report

```
Worktree ready at <full-path>
Branch: <branch-name>
```
