---
name: trycycle-planning
description: "Internal trycycle subskill — do not invoke directly."
---
<!-- trycycle-planning: adapted from https://github.com/obra/superpowers writing-plans -->
<!-- base-commit: 8ea3981 -->
<!-- imported: 2026-03-21 -->

# Writing Plans

## Overview

Write comprehensive implementation plans assuming the engineer has zero context for our codebase and questionable taste. Document everything they need to know: which files to touch for each task, code, testing, docs they might need to check, how to test it. Give them the whole plan as bite-sized tasks. DRY. YAGNI. TDD. Frequent commits.

Assume they are a skilled developer, but know almost nothing about our toolset or problem domain. Assume they don't know good test design very well.

**Context:** This should be run in an isolated implementation workspace.

**Save plans to:** `docs/plans/YYYY-MM-DD-<feature-name>.md`
- (User preferences for plan location override this default)

## Scope Check

If the spec covers multiple independent subsystems, it should have been broken into sub-project specs during brainstorming. If it wasn't, suggest breaking this into separate plans — one per subsystem. Each plan should produce working, testable software on its own.

## File Structure

Before defining tasks, map out which files will be created or modified and what each one is responsible for. This is where decomposition decisions get locked in.

- Design units with clear boundaries and well-defined interfaces. Each file should have one clear responsibility.
- You reason best about code you can hold in context at once, and your edits are more reliable when files are focused. Prefer smaller, focused files over large ones that do too much.
- Files that change together should live together. Split by responsibility, not by technical layer.
- In existing codebases, follow established patterns. If the codebase uses large files, don't unilaterally restructure - but if a file you're modifying has grown unwieldy, including a split in the plan is reasonable.

This structure informs the task decomposition. Each task should produce self-contained changes that make sense independently.

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
- "Identify or write the failing test" - step: run a high-value existing check that should be red, extend an existing test, or write a new failing test when coverage is missing
- "Run it to make sure it fails" - step
- "Implement the minimal code to make the test pass" - step
- "Run the tests and make sure they pass" - step
- "Refactor" - step: tighten the implementation and tests, then re-run the relevant checks and broader required suite
- "Commit" - step

## Completion Standard

A task is not done when one targeted test passes. Execution is complete only when:

- The targeted test passes for legitimate reasons (the code is correct, not the test weakened)
- All required automated checks for the work pass — including any broader regression suite or full project suite that the repo convention requires before completion
- No valid test has been weakened, deleted, or diluted merely to obtain a green result

Test changes are allowed when a test is wrong, obsolete, or can be replaced by a stronger or more faithful check. "Make the test easier so it passes" is never acceptable. If a check reveals a real defect, fix the defect. If checks are still failing, keep improving the code and tests — failed checks mean continue, not stop and declare done.

## Plan Document Header

**Every plan MUST start with this header:**

```markdown
# [Feature Name] Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use trycycle-executing to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

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

- [ ] **Step 1: Identify or write the failing test**

Prefer high-value existing checks: run them first to confirm they are currently red, then make them green in Step 3. If no existing check covers this behavior, extend or write a new failing test.

```python
# Option A: run existing test that should be red
# pytest tests/path/test.py::test_existing_behavior -v

# Option B: new failing test when coverage is missing
def test_specific_behavior():
    result = function(input)
    assert result == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/path/test.py::test_name -v`
Expected: FAIL with "function not defined"

- [ ] **Step 3: Write minimal implementation**

```python
def function(input):
    return expected
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/path/test.py::test_name -v`
Expected: PASS

- [ ] **Step 5: Refactor and verify**

Tighten the implementation and tests. Remove duplication, improve clarity, and strengthen assertions where possible. Then re-run the targeted test and the broader required suite to confirm nothing regressed.

Run: `pytest tests/path/test.py::test_name -v`
Run: `<full project suite command>`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add tests/path/test.py src/path/file.py
git commit -m "feat: add specific feature"
```
````

## Remember
- Exact file paths always
- Complete code in plan (not "add validation")
- Exact commands with expected output
- If the problem statement names automated checks that are red and must go green, include them explicitly in the plan
- Do not weaken, delete, or dilute valid tests to obtain a passing result — fix the code instead
- Reference relevant skills with @ syntax
- DRY, YAGNI, Red/Green/Refactor TDD, frequent commits
