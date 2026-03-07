---
name: trycycle-executing
description: Use when you have a written implementation plan to execute — reads the plan, creates todos, and executes all tasks continuously without pausing for review
---
<!-- trycycle-executing: adapted from https://github.com/obra/superpowers executing-plans -->
<!-- base-commit: e4a2375 -->
<!-- imported: 2026-03-06 -->

# Executing Plans

## Overview

Load the plan, create TodoWrite entries for all tasks, then execute every task sequentially without pausing.

**Core principle:** Execute all tasks continuously. The plan has already been reviewed. Your job is to implement it precisely.

## Step 1: Load Plan

1. Read the plan file
2. Create a TodoWrite entry for every task in the plan

## Step 2: Execute All Tasks

For each task, in order:

1. Mark as `in_progress`
2. Follow each step exactly — the plan has bite-sized steps
3. Run verifications as specified
4. Mark as `completed`

Repeat until all tasks are done, then commit your changes.

## Blockers

There are two states: **execute** or **stop for a blocker**.

A blocker is something where the agent cannot use its best judgment because there is no path forward, or because being wrong could cause harm — a missing dependency that cannot be worked around, a test environment that is down, a suddenly dirty file in the repo that, if handled incorrectly, could cause data loss.

"I have concerns about the approach" is not a blocker. The plan is already reviewed.

**If you hit a blocker:** stop and report your findings. Do not guess your way through something that could produce silently broken output or cause harm.

**Everything else:** proceed.

## Remember

- Follow plan steps exactly
- Don't skip verifications
- Reference skills when the plan says to
- Stop only for genuine blockers — not concerns, not uncertainty, not preference
- Never implement on main/master branch without explicit user consent
