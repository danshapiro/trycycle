---
name: trycycle
description: Invoke trycycle only when the user requests it by name.
---

# Trycycle

Use this skill only when the user requests `trycycle` to implement something.

The user's instructions are paramount. If anything in this skill conflicts with the user's instructions, follow the user.

## 1) Confirm critical unknowns before work

Read the user's request and identify whether any missing information could materially change the outcome and likely upset the user if guessed wrong.

Assume the user cares about outcomes, not technologies. Mention technology choices only when they impact user experience.

If there are no critical unknowns, reply exactly:

`Getting started.`

If there are critical unknowns, list each succinctly as:

`1. Question? (recommended answer)`

Example:
`1. Webapp or local? (webapp)`

If needed, follow up with additional questions of similar importance or discussion. Proceed either when the user indicates they are ready, or when the user has answered all critical questions.

## 2) Create worktree

Use the `trycycle-worktrees` skill to create an isolated worktree for the implementation with an appropriately named branch, for example `add-connection-status-icon`.

Immediately after creating the worktree, run:
- `git -C {WORKTREE_PATH} branch --show-current`
- `git -C {WORKTREE_PATH} status --short`

Do not continue until the branch is correct and the status is clean.

## 2.5) Worktree hygiene gate (mandatory)

Before and after each major phase (`plan-review`, `execution`, `post-implementation review`), run:
- `git -C {WORKTREE_PATH} branch --show-current`
- `git -C {WORKTREE_PATH} status --short`

After every subagent completion, also run:
- `git -C {WORKTREE_PATH} rev-parse --short HEAD`
- `git -C {WORKTREE_PATH} diff --name-only main...HEAD`

**GATE — Do not advance phases** until all of the following are true:
- branch matches expected branch for `{WORKTREE_PATH}`
- changed-file list matches what the subagent reported
- any dirty status is understood and intentional

## 3) Plan with trycycle-planning (subagent-owned)

Spec writing must be done by a dedicated subagent.

Spawn a fresh planning subagent and give it the user's initial request plus all critical questions back-and-forth verbatim.

Use this template:

```text
You are the planning subagent. Do not spawn additional subagents.

<context>
{INITIAL_REQUEST_AND_SUBSEQUENT_CONVERSATION}
</context>

Task:
- Use the `trycycle-planning` skill to produce a complete implementation plan for the user's request.
- The `trycycle-planning` skill may reference a brainstorming phase as a precondition. Disregard that — the context above replaces brainstorming output.
- Do not ask the user for input until the plan is complete.
- Do not use other skills unless they are referenced internally by `trycycle-planning`.
- Prefer approaches that are idiomatic to the stack and architecturally clean, even if they are much more effort or require much bigger changes.
- Work in the worktree at `{WORKTREE_PATH}`.
- Commit the plan to the worktree.
- Skip the execution handoff section of `trycycle-planning` — just return the absolute path to your plan.
```

Do not proceed until the planning subagent has returned a complete plan.

Before starting plan-review round 1, run the Worktree hygiene gate checks and confirm the plan file exists at the returned path.

## 4) Plan-review loop (up to 5 rounds)

Deploy a subagent to review the plan.

Provide the user's initial request and all back-and-forth verbatim.

Instruct the subagent to read the plan and return a numbered list of issues. An issue must be significant enough that the user's intent might not be met due to a technical or product-direction deficiency.

The reviewer should be stateless: you should NOT tell it that it is on review X/5, that it is looking at a plan that has previously been reviewed, etc.

Use this template:

```text
Another AI has generated an implementation plan for a user request. You are the reviewer, charged with conducting a deep and thorough review and reporting on your findings. Ensure that it aligns completely with the `trycycle-planning` skill.

<user_intent>
{INITIAL_REQUEST_AND_SUBSEQUENT_CONVERSATION}
</user_intent>

<plan>
{path_to_plan}
</plan>

Task:
- Review this plan for significant issues. A significant issue is an issue which, if not fixed, could cause the final implementation to not follow the user_intent, or which could introduce new problems that were not present before.
- Expect approaches that are idiomatic to the stack and architecturally clean, even if they are much more effort or require much bigger changes.
- To support your search for significant issues, read every file necessary to build up the context to understand the plan and its ramifications.
- Do not modify files.
- Return only a numbered list of significant issues, with comprehensive supporting data sufficient to prove your point to a skeptical and defensive reviewer.
- If there are no significant issues, return: "No significant issues."
- There may be other agents who review your work. If your issues are all judged significant, and you do not miss any significant issues, you will get a cookie.

Rules:
- Do not include praise.
- Do not include minor nits.
```

After each review:
1. Send all issues to the planning subagent, maintaining context from the previous planning session, and have it revise the plan at the same file location.
2. Run the Worktree hygiene gate checks and verify the latest commit hash plus changed-file list match the planning subagent's report.
3. Re-run a fresh reviewer, with no context history, with the same template and updated plan.
4. Repeat up to 5 rounds.

If issues still remain after the 5th review:
1. Stop looping.
2. Summarize the remaining issues.
3. Speculate briefly why the loop is not converging.
4. Await user instructions.

## 5) Execute with trycycle-executing (subagent-owned)

Code implementation must be done by a new, dedicated subagent.

Spawn a fresh implementation subagent and give it the final approved plan.

Use this template:

```text
You are the implementation subagent. Use the trycycle-executing skill to implement this final plan precisely, with these overrides:
- Do not pause between batches or wait for feedback — execute all tasks continuously.
- Do not ask for review.
- If you hit a blocker, document it, use your best judgment to work around it, and continue. Only stop if you cannot find any way to continue without causing harm.
All other trycycle-executing behaviors remain in effect (run verifications, follow plan steps exactly, etc.).

<plan>
{path_to_plan}
</plan>

Work in the worktree at `{WORKTREE_PATH}`.

Commit your changes, then return a concise implementation summary and verification results.
```

Do not proceed to post-implementation review until the implementation subagent has completed execution.

After implementation completes, run the Worktree hygiene gate checks and verify commit hash plus changed-file list before launching post-implementation review.

## 6) Post-implementation review loop (up to 8 rounds)

After execution completes, deploy a new reviewer with no prior context.

Use this template:

```text
You are an independent code reviewer performing a detailed review. Review the diff between the working directory and the merge base in the worktree at `{WORKTREE_PATH}`.

Context gathering:
- Read relevant files and repository context as needed.
- Use read-only git inspection commands if helpful.
- Do not modify files.

Review for:
- Correctness and logic issues
- Missing edge cases
- Security and performance problems
- Error-handling gaps
- Missing or incorrect tests
- Any mismatch between implementation and intended behavior
- Doing things the right way, without taking shortcuts

Output format:
1. Numbered list of issues, each with severity: critical, major, minor, or nit.
2. Include file and line when possible.
3. If no issues, respond: "No issues found."
```

Address all issues each round regardless of severity. Route issues back to the implementation subagent for fixes, then re-run with a fresh stateless reviewer each time.

After each implementation-subagent fix round, run the Worktree hygiene gate checks and verify commit hash plus changed-file list before starting the next fresh review round.

Stop when either condition is met:
1. No **critical** or **major** issues remain.
2. 8 rounds have been completed.

If critical or major issues still remain after the 8th review:
1. Stop looping.
2. Summarize the remaining issues.
3. Speculate briefly why the loop is not converging.
4. Await user instructions.

## 7) Finish

Once the post-implementation review loop passes (no critical or major issues):

Clean up temporary artifacts created during the loop (for example plan scratch files and temp notes), then run:
- `git -C {WORKTREE_PATH} status --short`
- `git -C {WORKTREE_PATH} rev-parse --short HEAD`
- `git -C {WORKTREE_PATH} diff --name-only main...HEAD`

Summarize the ENTIRE process to the user: how many plan-review rounds, how many code-review rounds, what was changed in the codebase, any notes about unresolved minor issues or concerns, and where things stand.

Then use the `trycycle-finishing` skill to present the user with options for integrating the worktree (merge, PR, etc.).
