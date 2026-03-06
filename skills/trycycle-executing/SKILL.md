<!-- trycycle-executing: adapted from obra/superpowers executing-plans -->
<!-- source: https://github.com/obra/superpowers -->
<!-- author: Jesse Vincent -->
<!-- base-commit: e4a2375 -->
<!-- imported: 2026-03-06 -->

---
name: trycycle-executing
description: Use when you have a written implementation plan to execute continuously without pausing for review
---

# Executing Plans

## Overview

Load plan, review critically, execute all tasks sequentially without pausing.

**Core principle:** Continuous execution — implement everything, commit, and return a summary.

## Step 1: Load and Review Plan

1. Read the plan file
2. Review critically — identify any questions or concerns about the plan
3. If there are concerns that would prevent starting or cause harm: stop and document them
4. If no concerns: create TodoWrite entries for all tasks and proceed

## Step 2: Execute All Tasks

For each task in order:

1. Mark as `in_progress`
2. Follow each step exactly as written (the plan has bite-sized steps)
3. Run verifications as specified
4. Mark as `completed`

Execute all tasks sequentially. Do not pause between tasks.

## Blocker Handling

If you hit a blocker:
- Document it clearly (in a comment, commit message, or notes file)
- Use your best judgment to work around it and continue
- Only stop if you cannot find any way to continue without causing harm

## Remember

- Review plan critically before starting
- Follow plan steps exactly — do not improvise
- Do not skip verifications
- Track progress with TodoWrite (in_progress → completed per task)
- Commit your changes when done
- Never start implementation on main/master branch without explicit user consent
