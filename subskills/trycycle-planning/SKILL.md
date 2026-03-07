---
name: trycycle-planning
description: "Internal trycycle subskill — do not invoke directly."
---
<!-- trycycle-planning: adapted from https://github.com/obra/superpowers writing-plans -->
<!-- base-commit: e4a2375 -->
<!-- imported: 2026-03-07 -->

# Writing Plans

## Overview

Write comprehensive implementation plans assuming the engineer has zero context for our codebase and questionable taste. Document everything they need to know: which files to touch for each task, code, testing, docs they might need to check, how to test it. Give them the whole plan as bite-sized tasks. DRY. YAGNI. TDD. Frequent commits.

Assume they are a skilled developer, but know almost nothing about our toolset or problem domain. Assume they don't know good test design very well.

**Context:** This should be run in a dedicated worktree.

**Save plans to:** `docs/plans/YYYY-MM-DD-<feature-name>.md`

## Strategy Gate (before task breakdown)

Before writing any tasks, step back and challenge your current framing:

- Is this the right problem to solve, or is there a simpler or more direct path to the user's actual goal?
- Is the proposed architecture the right one, or would a different approach eliminate complexity?
- Are there assumptions baked into the current direction that haven't been validated?

**Low bar for changing direction.** Big rewrites, architecture resets, and fresh replans are always acceptable when they produce a better answer. Do not preserve earlier decisions just because they already exist. If a better path is visible, take it.

**High bar for stopping to ask the user.** Use best judgment and keep going unless there is genuinely no safe path forward without a user decision. The only valid reasons to stop are: a fundamental conflict between user requirements, a fundamental conflict between the requirements and reality, or a real risk of doing harm if you guess. For everything else, make a decision and document it in the plan.

Once the architectural direction is stable and you are confident you are solving the right problem in the right way, proceed to detailed task decomposition.

## Bite-Sized Task Granularity

**Each step is one action (2-5 minutes):**
- "Write the failing test" - step
- "Run it to make sure it fails" - step
- "Implement the minimal code to make the test pass" - step
- "Run the tests and make sure they pass" - step
- "Commit" - step

## Plan Document Header

**Every plan MUST start with this header:**

```markdown
# [Feature Name] Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use trycycle-executing to implement this plan task-by-task.

**Goal:** [One sentence describing what this builds]

**Architecture:** [2-3 sentences about approach]

**Tech Stack:** [Key technologies/libraries]

---
```

## Task Structure

````markdown
### Task N: [Component Name]

**Files:**
- Create: `exact/path/to/file.py`
- Modify: `exact/path/to/existing.py:123-145`
- Test: `tests/exact/path/to/test.py`

**Step 1: Write the failing test**

```python
def test_specific_behavior():
    result = function(input)
    assert result == expected
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/path/test.py::test_name -v`
Expected: FAIL with "function not defined"

**Step 3: Write minimal implementation**

```python
def function(input):
    return expected
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/path/test.py::test_name -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/path/test.py src/path/file.py
git commit -m "feat: add specific feature"
```
````

## Remember
- Exact file paths always
- Complete code in plan (not "add validation")
- Exact commands with expected output
- Reference relevant skills with @ syntax
- DRY, YAGNI, TDD, frequent commits
