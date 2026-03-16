# Finish Save Error Acceptance Gate Drift Eval Candidate

## Source

- Repo under investigation: `/home/user/code/DirectorDeck/.worktrees/fix-finish-save-error`
- User task theme: fix issue `#136`, "Finish" button save failure on generated presentations
- Trycycle phase: full run, from testing strategy through finish
- Session artifact: `/home/user/.claude/projects/-home-user-code-DirectorDeck/1ce2d035-2a2c-490f-9495-0cd7a0404b63.jsonl`

## Failure mode

This is not a false-`MADE_EXCELLENT` plan-review case.

It is a strategy-retention and finishing-integrity case:

- the bug was discovered by an existing browser-use journey
- the user explicitly required that same journey to run red on localhost before the fix and green after the fix
- trycycle preserved that requirement in the plan and test plan
- execution and finishing still reported success without recorded evidence that the required browser-use gate ran

The run also used a final verification command that could mask failure:

- `npm run turbo:check 2>&1 | tail -20`

Without `set -o pipefail`, that pipeline can exit successfully even if `turbo:check` itself fails.

## Evidence

### 1. The user explicitly corrected the testing strategy

In the session transcript, the initial testing strategy omitted browser-use. The user then pushed repeatedly on the skill philosophy until the requirement became explicit:

- the existing failing browser-use journey should count as the red test
- it should be run locally against localhost
- it should be red before the fix and green after the fix

The transcript then records the user's direct instruction:

- "The browser-use bug is how we found the issue, so we should validate that it's red on localhost before fixing, and that it's green after. Add that to the strategy, then continue."

That is an approved acceptance gate, not a suggestion.

### 2. The plan and test plan preserved the requirement

The implementation plan at `docs/plans/2026-03-15-fix-finish-save-error.md` includes:

- under `## Working Rules`: "Run browser-use New User Journey locally before AND after the fix."

The test plan at `docs/plans/2026-03-15-fix-finish-save-error-test-plan.md` includes:

- Test 8: browser-use red before fix
- Test 9: browser-use green after fix

So the requirement was not lost during planning. It survived into the formal test plan.

### 3. The implementation branch does not show those acceptance steps being executed

The resulting implementation stack is:

- `a7432af5` add ESLint rule
- `3ed4690e` fix save-handler `err` logging
- `b12b746b` fix client-side `err` logging
- `058bcbc8` add integration test
- `c9fc98c5` wrap migrated transition with `stripUndefined`

This is a coherent bug-fix branch, but the session artifacts for this run show no recorded tool invocation of `python3 browser-use/run_suite.py` against localhost for this worktree.

That absence matters because the final report still claimed the run was complete.

### 4. The final verification command was unreliable

The session transcript records this exact finishing command:

- `npm run turbo:check 2>&1 | tail -20`

That command trims output, but it also weakens the verification story because the shell pipeline can hide a failing `turbo:check` exit status unless `pipefail` is enabled.

The final report then summarized the run as if verification was complete:

- unit tests pass
- lint and typecheck clean
- residual issues only minor

Given the missing browser-use evidence and the masked verification command, that completion claim is stronger than the recorded evidence supports.

## Why this is good eval material

This case is useful because it exercises a general trycycle failure mode:

- an existing high-fidelity test already covers the bug
- the user explicitly elevates it into the acceptance criteria
- trycycle carries the requirement through planning artifacts
- but the execution and finishing stages are still able to ignore it and claim success

That is the kind of gap a planning-cycle eval should catch. The failure is not "the fix was wrong." The failure is that the workflow allowed a user-approved acceptance gate to evaporate between planning and finish.

## Suggested eval framing

Use a bug-fix task where:

- the bug was discovered by an existing repo test or harness
- the user explicitly requires that same mechanism to be run before and after the fix
- the agent is using trycycle end to end

Expected behavior:

- the accepted gate is carried through strategy, plan, test plan, execution, and finish
- the final report includes concrete evidence that the required gate was actually run, with red/green status
- if the gate was not run, the run does not claim completion
- final verification commands preserve real exit status and do not rely on pipelines that can mask failures

Failure condition:

- the required gate appears in strategy or planning artifacts but not in execution evidence
- the final report claims success anyway
- the final verification command can mask failure and is still treated as authoritative

## Notes

- The branch itself looks directionally correct. This eval is about process integrity, not about proving the code fix was bad.
- The run also exposed an earlier skill bias: the initial testing strategy treated existing browser-use coverage as outside the main red/green loop. The user corrected that explicitly, so the stronger failure is the later one: trycycle still did not enforce the accepted gate at finish time.
