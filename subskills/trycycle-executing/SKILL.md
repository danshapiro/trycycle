---
name: trycycle-executing
description: Internal trycycle subskill — do not invoke directly.
---
<!-- trycycle-executing: adapted from https://github.com/obra/superpowers executing-plans -->
<!-- base-commit: 8ea3981 -->
<!-- imported: 2026-03-21 -->

# Executing Plans

## Overview

Load the plan, create TodoWrite entries for all tasks, then execute every task sequentially without pausing.

**Core principle:** Execute all tasks continuously. The plan has already been reviewed. Your job is to implement it precisely.

## Step 1: Load Plan

1. Read the implementation plan file and the test plan file
2. Create a TodoWrite entry for every task in the plan

## Step 2: Execute All Tasks

For each task, in order:

1. Mark as `in_progress`
2. Follow each step exactly — the plan has bite-sized steps
3. Work through red/green/refactor cycles until the task is genuinely complete:
   - Run the failing check (red)
   - Make it pass (green)
   - Refactor and tighten the implementation and tests, then re-run all relevant automated checks
4. Continue until all required automated checks named or implied by the plan are passing — including any broader regression suite or full project suite the repo requires before completion
5. Mark as `completed`

Repeat until all tasks are done, then commit your changes.

**Execution is not complete** merely because one targeted check turned green. Keep working until all required automated checks pass for legitimate reasons.

**Test quality is non-negotiable.** Do not weaken, delete, or dilute a valid automated test to obtain a passing result. If a test is wrong, obsolete, or lower-fidelity than a better replacement, you may correct or replace it — but do not manufacture green by making good tests less demanding.

## Blockers

There are two states: **execute** or **stop for a blocker**.

A blocker is something where the agent cannot use its best judgment because there is no path forward, or because being wrong could cause harm — a missing dependency that cannot be worked around, a test environment that is down, a suddenly dirty file in the repo that, if handled incorrectly, could cause data loss.

"I have concerns about the approach" is not a blocker. The plan is already reviewed. Red tests and review findings are inputs to keep iterating — not blockers — unless the environment itself is broken.

**If you hit a blocker:** stop and report your findings. Do not guess your way through something that could produce silently broken output or cause harm.

**Everything else:** proceed.

## Remember

- Follow plan steps exactly
- Don't skip verifications
- Work red/green/refactor cycles — don't stop at the first green
- All required automated checks must pass legitimately before execution is complete
- Never weaken or delete a valid test to achieve green
- Reference skills when the plan says to
- Stop only for genuine blockers — not concerns, not uncertainty, not preference
- Never implement on main/master branch without explicit user consent
