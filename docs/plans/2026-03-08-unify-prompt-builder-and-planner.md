# Unified Prompt Builder And Planner Respawn Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use trycycle-executing to implement this plan task-by-task.

**Goal:** Manually recreate the combined end state of the `fresh-impl-after-review-failure` and `python-prompt-builder` worktrees in one clean implementation: render subagent prompts at runtime from a single template per role, and respawn a fresh planning subagent after each failed plan review.

**Architecture:** Add a small Python prompt renderer under `orchestrator/prompt_builder/` and make [SKILL.md](/home/user/code/trycycle/.worktrees/unify-prompt-builder-and-planner/SKILL.md) render every subagent prompt before dispatch. Keep one [prompt-planning.md](/home/user/code/trycycle/.worktrees/unify-prompt-builder-and-planner/subagents/prompt-planning.md) and one [prompt-executing.md](/home/user/code/trycycle/.worktrees/unify-prompt-builder-and-planner/subagents/prompt-executing.md), using conditional blocks so agents only see review-only sections when the corresponding inputs exist. Update the planning loop to spawn a fresh planning subagent on each failed plan review, sync the human-facing and maintainer-facing docs, and verify the result with render probes plus disposable clean smoke repos. Do not add committed tests in this repo.

**Tech Stack:** Markdown skill specs, Python 3 CLI helper, bash/git, temporary files under `/tmp`

---

### Task 1: Add the runtime prompt builder

**Files:**
- Create: `orchestrator/prompt_builder/build.py`

**Step 1: Create the builder CLI**

Implement `orchestrator/prompt_builder/build.py` as a standalone Python 3 script with these exact behaviors:

- Accept `--template <path>`, repeatable `--set NAME=VALUE`, and repeatable `--set-file NAME=PATH`.
- Read the template as UTF-8 and write the rendered prompt to stdout.
- Support placeholder substitution for `{NAME}` where `NAME` matches `[A-Z][A-Z0-9_]*`.
- Support conditional blocks with `{{#if NAME}} ... {{else}} ... {{/if}}` and `{{#if NAME}} ... {{/if}}`.
- Treat a binding as truthy when its bound string is non-empty.
- Fail with exit code `1` and a `prompt builder error: ...` stderr message on malformed bindings, duplicate bindings, missing placeholders, unreadable files, or unbalanced conditionals.
- Keep the implementation dependency-free; use only the standard library.

Use the structure from the reference worktree rather than inventing a different parser:

```python
TOKEN_RE = re.compile(
    r"{{#if (?P<if>[A-Z][A-Z0-9_]*)}}|{{(?P<else>else)}}|{{(?P<endif>/if)}}"
)
PLACEHOLDER_RE = re.compile(r"\{([A-Z][A-Z0-9_]*)\}")
```

Implement small helpers for argument parsing, binding loading, tokenization, recursive conditional parsing, text rendering, and `main()`.

**Step 2: Verify the script compiles**

Run:

```bash
python3 -m py_compile orchestrator/prompt_builder/build.py
```

Expected: command exits successfully and produces no stderr.

**Step 3: Probe the builder directly**

Use a temporary directory under `/tmp` and run a minimal conditional render plus a missing-placeholder failure probe:

```bash
tmpdir="$(mktemp -d /tmp/trycycle-prompt-builder-XXXXXX)"
cat >"$tmpdir/template.md" <<'EOF'
hello {NAME}
{{#if EXTRA}}extra: {EXTRA}{{else}}no extra{{/if}}
EOF
python3 orchestrator/prompt_builder/build.py \
  --template "$tmpdir/template.md" \
  --set NAME=world \
  --set EXTRA=value
python3 orchestrator/prompt_builder/build.py \
  --template "$tmpdir/template.md" \
  --set NAME=world
! python3 orchestrator/prompt_builder/build.py \
  --template "$tmpdir/template.md"
rm -rf "$tmpdir"
```

Expected:
- First render prints `hello world` and `extra: value`.
- Second render prints `hello world` and `no extra`.
- Third command exits non-zero and reports a missing placeholder error.

**Step 4: Commit**

```bash
git add orchestrator/prompt_builder/build.py
git commit -m "feat: add runtime prompt builder"
```

### Task 2: Collapse planning and execution prompts into single renderable templates

**Files:**
- Modify: `subagents/prompt-planning.md`
- Modify: `subagents/prompt-executing.md`

**Step 1: Update the planning prompt template**

Edit `subagents/prompt-planning.md` so it can serve both the initial planning round and revision rounds:

- Add a conditional block that emits `<current_implementation_plan_path>` and `<plan_review_findings_verbatim>` only when `PLAN_REVIEW_FINDINGS_VERBATIM` is bound.
- Replace the static first task bullet with a conditional sentence:
  - initial render: produce a complete implementation plan
  - revision render: revise the current implementation plan against the attached review report
- Remove the current prose telling the agent to ignore a future review block when none exists.
- Change the commit instruction from `Commit the plan` to `Commit the current plan`.

Follow the reference wording from the prompt-builder worktree; do not reintroduce split files like `prompt-planning-initial.md` or `prompt-planning-revision.md`.

**Step 2: Update the execution prompt template**

Edit `subagents/prompt-executing.md` so it can serve both the initial implementation round and fix rounds:

- Add a conditional `<post_implementation_review_findings_verbatim>` block gated by `POST_IMPLEMENTATION_REVIEW_FINDINGS_VERBATIM`.
- Replace the current always-present prose about later fix rounds with a conditional sentence that appears only in fix rounds.
- Keep the initial-round prompt branch-free when no review findings are bound.

**Step 3: Render both variants of both prompts**

Create temp input files under `/tmp` and verify the rendered outputs:

```bash
tmpdir="$(mktemp -d /tmp/trycycle-prompt-templates-XXXXXX)"
printf '[{\"role\":\"user\",\"text\":\"example\"}]\n' >"$tmpdir/transcript.json"
printf '1. Example plan issue.\n' >"$tmpdir/plan-review.txt"
printf '1. Example implementation issue.\n' >"$tmpdir/post-impl-review.txt"

python3 orchestrator/prompt_builder/build.py \
  --template subagents/prompt-planning.md \
  --set WORKTREE_PATH=/tmp/example-worktree \
  --set-file USER_REQUEST_TRANSCRIPT="$tmpdir/transcript.json" \
  >"$tmpdir/planning-initial.out"

python3 orchestrator/prompt_builder/build.py \
  --template subagents/prompt-planning.md \
  --set WORKTREE_PATH=/tmp/example-worktree \
  --set IMPLEMENTATION_PLAN_PATH=/tmp/example-worktree/docs/plans/example.md \
  --set-file USER_REQUEST_TRANSCRIPT="$tmpdir/transcript.json" \
  --set-file PLAN_REVIEW_FINDINGS_VERBATIM="$tmpdir/plan-review.txt" \
  >"$tmpdir/planning-revision.out"

python3 orchestrator/prompt_builder/build.py \
  --template subagents/prompt-executing.md \
  --set IMPLEMENTATION_PLAN_PATH=/tmp/example-worktree/docs/plans/example.md \
  --set TEST_PLAN_PATH=/tmp/example-worktree/docs/plans/example-test-plan.md \
  --set WORKTREE_PATH=/tmp/example-worktree \
  >"$tmpdir/executing-initial.out"

python3 orchestrator/prompt_builder/build.py \
  --template subagents/prompt-executing.md \
  --set IMPLEMENTATION_PLAN_PATH=/tmp/example-worktree/docs/plans/example.md \
  --set TEST_PLAN_PATH=/tmp/example-worktree/docs/plans/example-test-plan.md \
  --set WORKTREE_PATH=/tmp/example-worktree \
  --set-file POST_IMPLEMENTATION_REVIEW_FINDINGS_VERBATIM="$tmpdir/post-impl-review.txt" \
  >"$tmpdir/executing-fix.out"
```

Then check:

```bash
! rg -n "<current_implementation_plan_path>|<plan_review_findings_verbatim>" "$tmpdir/planning-initial.out"
rg -n "<current_implementation_plan_path>|<plan_review_findings_verbatim>" "$tmpdir/planning-revision.out"
! rg -n "<post_implementation_review_findings_verbatim>" "$tmpdir/executing-initial.out"
rg -n "<post_implementation_review_findings_verbatim>" "$tmpdir/executing-fix.out"
rm -rf "$tmpdir"
```

Expected: the initial renders omit the review-only blocks and the revision/fix renders include them.

**Step 4: Commit**

```bash
git add subagents/prompt-planning.md subagents/prompt-executing.md
git commit -m "feat: unify planning and execution prompt templates"
```

### Task 3: Rewire the orchestrator to render prompts and respawn planning agents

**Files:**
- Modify: `SKILL.md`

**Step 1: Add prompt-builder instructions near the top of the skill**

Replace the current "pass the prompt template together with the parameters it names" guidance with explicit render-time instructions:

- tell the orchestrator not to reconstruct prompt text manually
- require `python3 <skill-directory>/orchestrator/prompt_builder/build.py`
- require `--set` for short scalar values and `--set-file` for multiline values
- require multiline command/subagent outputs to be saved to temp files immediately before rendering
- state that builder stdout is the exact prompt to send
- explain that `{{#if NAME}}` blocks render only when `NAME` is bound to a non-empty value

**Step 2: Make planning agents ephemeral across failed plan reviews**

Update `SKILL.md` so the planning lifecycle matches the user-approved intent:

- In `## Subagent Defaults`, planning subagents become ephemeral across plan-review rounds.
- In Step 6, dispatch a fresh planning subagent for the initial round.
- If that active planning subagent returns `USER DECISION REQUIRED:`, keep using that active subagent until it returns a planning report.
- After a failed plan review in Step 7, do not resume the old planning subagent. Spawn a fresh planning subagent for the revision round.
- Keep implementation subagents persistent; do not accidentally reintroduce the earlier rejected "fresh implementation agent" behavior.

**Step 3: Render every subagent prompt before dispatch**

Update every prompt-dispatch site in `SKILL.md` to render the corresponding template first, then send the rendered prompt verbatim:

- Step 3: `subagents/prompt-test-strategy.md`
- Step 6: `subagents/prompt-planning.md`
- Step 7 reviewer: `subagents/prompt-plan-review.md`
- Step 7 revision round: `subagents/prompt-planning.md` again, this time with `IMPLEMENTATION_PLAN_PATH` and `PLAN_REVIEW_FINDINGS_VERBATIM`
- Step 8: `subagents/prompt-test-plan.md`
- Step 9: `subagents/prompt-executing.md`
- Step 10 reviewer: `subagents/prompt-post-impl-review.md`
- Step 10 fix rounds: `subagents/prompt-executing.md` again, this time with `POST_IMPLEMENTATION_REVIEW_FINDINGS_VERBATIM`

Use the prompt-builder branch’s exact operational pattern:

- rebuild transcript placeholders immediately before each rendered prompt that uses them
- save multiline placeholder values to temp files before binding them with `--set-file`
- keep scalar paths on `--set`

**Step 4: Delete stale orchestration wording**

Search `SKILL.md` and remove stale instructions from the old model:

- references to passing raw template paths plus parameters directly to subagents
- the persistent-planner wording
- inline manual revision/fix messages that should now come from rendered templates
- any mention of `prompt-planning-initial.md` or `prompt-planning-revision.md`

Run:

```bash
rg -n "prompt-planning-initial|prompt-planning-revision|Pass the prompt template together with|Revise the current implementation plan against this review report|Fix the implementation against this review report" SKILL.md
```

Expected: no matches after the rewrite.

**Step 5: Commit**

```bash
git add SKILL.md
git commit -m "feat: render prompts and respawn planning agents"
```

### Task 4: Sync the user-facing and maintainer-facing docs

**Files:**
- Modify: `README.md`
- Modify: `maintenance/skill-instructions/trycycle-planning.txt`

**Step 1: Update the README behavior summary**

Adjust the "How it works" section in `README.md` so it matches the new orchestration:

- reviewers are always fresh
- failed plan-review rounds respawn a fresh planning agent before the next planning revision
- wording stays high-level and user-facing; do not explain prompt-builder internals here

Use the fresh-planner worktree as the wording baseline.

**Step 2: Update the planning-maintenance note**

Edit `maintenance/skill-instructions/trycycle-planning.txt` to describe the real orchestrator behavior that now matters when adapting the planning subskill:

- if plan review fails, the orchestrator spawns a fresh planning subagent rather than resuming the old one
- the revision-round dispatch may include the current plan path and raw reviewer findings
- keep the rest of the note intact

**Step 3: Verify the docs say the same thing as the implementation**

Run:

```bash
rg -n "fresh planning agent|fresh planning subagent|respawn.*planning" README.md maintenance/skill-instructions/trycycle-planning.txt SKILL.md
```

Expected: the README, maintainer note, and `SKILL.md` all clearly describe fresh planning agents after failed plan review.

**Step 4: Commit**

```bash
git add README.md maintenance/skill-instructions/trycycle-planning.txt
git commit -m "docs: sync planning retry behavior"
```

### Task 5: Run heavy verification without polluting this repo

**Files:** (none modified; verification only)

**Step 1: Re-run deterministic render verification for every prompt path**

Create a temp directory under `/tmp`, generate representative placeholder files, and render every prompt used by `SKILL.md`:

```bash
tmpdir="$(mktemp -d /tmp/trycycle-heavy-verify-XXXXXX)"
mkdir -p "$tmpdir/rendered"
printf '[{\"role\":\"user\",\"text\":\"example\"}]\n' >"$tmpdir/user-request.json"
printf '[{\"role\":\"user\",\"text\":\"full conversation\"}]\n' >"$tmpdir/full-conversation.json"
printf '1. Example plan review finding.\n' >"$tmpdir/plan-review.txt"
printf '1. Example post-implementation review finding.\n' >"$tmpdir/post-impl-review.txt"

python3 orchestrator/prompt_builder/build.py \
  --template subagents/prompt-test-strategy.md \
  --set-file INITIAL_REQUEST_AND_SUBSEQUENT_CONVERSATION="$tmpdir/full-conversation.json" \
  >"$tmpdir/rendered/test-strategy.md"

python3 orchestrator/prompt_builder/build.py \
  --template subagents/prompt-plan-review.md \
  --set IMPLEMENTATION_PLAN_PATH=/tmp/example/docs/plans/example.md \
  --set-file USER_REQUEST_TRANSCRIPT="$tmpdir/user-request.json" \
  >"$tmpdir/rendered/plan-review.md"

python3 orchestrator/prompt_builder/build.py \
  --template subagents/prompt-planning.md \
  --set WORKTREE_PATH=/tmp/example-worktree \
  --set-file USER_REQUEST_TRANSCRIPT="$tmpdir/user-request.json" \
  >"$tmpdir/rendered/planning-initial.md"

python3 orchestrator/prompt_builder/build.py \
  --template subagents/prompt-planning.md \
  --set WORKTREE_PATH=/tmp/example-worktree \
  --set IMPLEMENTATION_PLAN_PATH=/tmp/example/docs/plans/example.md \
  --set-file USER_REQUEST_TRANSCRIPT="$tmpdir/user-request.json" \
  --set-file PLAN_REVIEW_FINDINGS_VERBATIM="$tmpdir/plan-review.txt" \
  >"$tmpdir/rendered/planning-revision.md"

python3 orchestrator/prompt_builder/build.py \
  --template subagents/prompt-test-plan.md \
  --set IMPLEMENTATION_PLAN_PATH=/tmp/example/docs/plans/example.md \
  --set WORKTREE_PATH=/tmp/example-worktree \
  --set-file FULL_CONVERSATION_VERBATIM="$tmpdir/full-conversation.json" \
  >"$tmpdir/rendered/test-plan.md"

python3 orchestrator/prompt_builder/build.py \
  --template subagents/prompt-executing.md \
  --set IMPLEMENTATION_PLAN_PATH=/tmp/example/docs/plans/example.md \
  --set TEST_PLAN_PATH=/tmp/example/docs/plans/example-test-plan.md \
  --set WORKTREE_PATH=/tmp/example-worktree \
  >"$tmpdir/rendered/executing-initial.md"

python3 orchestrator/prompt_builder/build.py \
  --template subagents/prompt-executing.md \
  --set IMPLEMENTATION_PLAN_PATH=/tmp/example/docs/plans/example.md \
  --set TEST_PLAN_PATH=/tmp/example/docs/plans/example-test-plan.md \
  --set WORKTREE_PATH=/tmp/example-worktree \
  --set-file POST_IMPLEMENTATION_REVIEW_FINDINGS_VERBATIM="$tmpdir/post-impl-review.txt" \
  >"$tmpdir/rendered/executing-fix.md"

python3 orchestrator/prompt_builder/build.py \
  --template subagents/prompt-post-impl-review.md \
  --set WORKTREE_PATH=/tmp/example-worktree \
  >"$tmpdir/rendered/post-impl-review.md"
```

Then assert:

```bash
! rg -n '\{[A-Z][A-Z0-9_]*\}|{{#if|{{else}}|{{/if}}' "$tmpdir/rendered"
! rg -n "<current_implementation_plan_path>|<plan_review_findings_verbatim>" "$tmpdir/rendered/planning-initial.md"
rg -n "<current_implementation_plan_path>|<plan_review_findings_verbatim>" "$tmpdir/rendered/planning-revision.md"
! rg -n "<post_implementation_review_findings_verbatim>" "$tmpdir/rendered/executing-initial.md"
rg -n "<post_implementation_review_findings_verbatim>" "$tmpdir/rendered/executing-fix.md"
! python3 orchestrator/prompt_builder/build.py --template subagents/prompt-planning.md --set WORKTREE_PATH=/tmp/example-worktree
! python3 orchestrator/prompt_builder/build.py --template subagents/prompt-planning.md --set WORKTREE_PATH=/tmp/example-worktree --set-file USER_REQUEST_TRANSCRIPT=/tmp/does-not-exist
rm -rf "$tmpdir"
```

Expected:
- all prompt renders succeed
- no unresolved placeholders or conditionals remain
- planning/executing review-only sections appear only in revision/fix renders
- missing bindings and unreadable `--set-file` inputs fail loudly

**Step 2: Choose a usable primary CLI and keep the second CLI optional**

Detect which local agents are actually usable for smoke runs:

```bash
codex_bin="$(command -v codex || true)"
claude_bin="$(command -v claude || true)"
if [[ -n "$codex_bin" ]]; then
  primary_cli="codex"
  secondary_cli="${claude_bin:+claude}"
elif [[ -n "$claude_bin" ]]; then
  primary_cli="claude"
  secondary_cli=""
else
  echo "heavy verification blocker: neither codex nor claude is installed" >&2
  exit 1
fi
printf 'primary=%s secondary=%s\n' "$primary_cli" "${secondary_cli:-none}"
```

If the chosen primary CLI fails before trycycle logic because of local auth or unrelated machine setup, retry once. If it still cannot start a trycycle run, record the exact environment blocker and stop verification rather than changing the implementation to work around local CLI setup.

**Step 3: Run one happy-path smoke task in a disposable clean repo**

Use a clean temp repo so the smoke agent never sees this trycycle repo as the working project. Run the happy-path task on the usable primary CLI only.

For `codex`:

```bash
smoke_root="$(mktemp -d /tmp/trycycle-happy-codex-XXXXXX)"
repo="$smoke_root/repo"
codex_home="$smoke_root/codex-home"
mkdir -p "$repo" "$codex_home/skills"
git init -b main "$repo"
printf '# Smoke Repo\n' >"$repo/README.md"
git -C "$repo" add README.md
git -C "$repo" commit -m "chore: init smoke repo"
ln -s /home/user/code/trycycle/.worktrees/unify-prompt-builder-and-planner "$codex_home/skills/trycycle"
CODEX_HOME="$codex_home" codex exec -C "$repo" --sandbox danger-full-access --ask-for-approval never \
  "Use trycycle to add smoke-note.txt containing exactly 'primary smoke'. Testing instructions: do not add tests; verify the file exists, verify its exact contents, and verify the changed-file list in the implementation branch includes smoke-note.txt." \
  | tee "$smoke_root/output.txt"
git -C "$repo" worktree list --porcelain >"$smoke_root/worktrees.txt"
```

For `claude`:

```bash
smoke_root="$(mktemp -d /tmp/trycycle-happy-claude-XXXXXX)"
repo="$smoke_root/repo"
git init -b main "$repo"
printf '# Smoke Repo\n' >"$repo/README.md"
git -C "$repo" add README.md
git -C "$repo" commit -m "chore: init smoke repo"
mkdir -p "$repo/.claude/skills"
ln -s /home/user/code/trycycle/.worktrees/unify-prompt-builder-and-planner "$repo/.claude/skills/trycycle"
(cd "$repo" && claude -p --dangerously-skip-permissions \
  "Use trycycle to add smoke-note.txt containing exactly 'primary smoke'. Testing instructions: do not add tests; verify the file exists, verify its exact contents, and verify the changed-file list in the implementation branch includes smoke-note.txt.") \
  | tee "$smoke_root/output.txt"
git -C "$repo" worktree list --porcelain >"$smoke_root/worktrees.txt"
```

Inspect the logged output and the listed worktrees. Success means:

- the run reaches trycycle planning and execution rather than failing on skill discovery or prompt rendering
- a trycycle-created worktree exists under the clean smoke repo
- that worktree contains the expected `smoke-note.txt` change in its `main...HEAD` diff

**Step 4: Run one controlled smoke task aimed at provoking both review loops**

Create a second clean disposable repo with just enough structure that reviewers are likely to find at least one omission if the new loops are broken:

```bash
smoke_root="$(mktemp -d /tmp/trycycle-controlled-smoke-XXXXXX)"
repo="$smoke_root/repo"
git init -b main "$repo"
cat >"$repo/notes.txt" <<'EOF'
alpha
beta
gamma
EOF
cat >"$repo/notes.py" <<'EOF'
#!/usr/bin/env python3
from pathlib import Path


def main() -> None:
    for line in Path("notes.txt").read_text(encoding="utf-8").splitlines():
        print(f"NOTE: {line}")


if __name__ == "__main__":
    main()
EOF
cat >"$repo/README.md" <<'EOF'
# Notes

Run `python3 notes.py` to print each note.
EOF
chmod +x "$repo/notes.py"
git -C "$repo" add README.md notes.py notes.txt
git -C "$repo" commit -m "chore: init controlled smoke repo"
```

Then run trycycle on the same usable primary CLI with a task that has enough surface area to stress both review loops:

- extend `notes.py` with `--prefix TEXT`, `--format text|json`, and `--limit N`
- preserve the existing default text output when no flags are passed
- reject invalid `--format` values and non-positive `--limit` values with non-zero exit status and a clear error message
- update the README examples for default output, prefixed output, json output, and invalid-input behavior
- do not add tests; verify the example commands and changed-file list

For `codex`:

```bash
codex_home="$smoke_root/codex-home"
mkdir -p "$codex_home/skills"
ln -s /home/user/code/trycycle/.worktrees/unify-prompt-builder-and-planner "$codex_home/skills/trycycle"
CODEX_HOME="$codex_home" codex exec -C "$repo" --sandbox danger-full-access --ask-for-approval never \
  "Use trycycle to extend notes.py with --prefix TEXT, --format text|json, and --limit N. Keep the current default text output unchanged when no flags are passed. Reject invalid --format values and non-positive --limit values with a non-zero exit status and a clear error message. Update README examples for default output, prefixed output, json output, and invalid-input behavior. Testing instructions: do not add tests; verify the example commands, error handling, and the changed-file list." \
  | tee "$smoke_root/output.txt"
```

For `claude`:

```bash
mkdir -p "$repo/.claude/skills"
ln -s /home/user/code/trycycle/.worktrees/unify-prompt-builder-and-planner "$repo/.claude/skills/trycycle"
(cd "$repo" && claude -p --dangerously-skip-permissions \
  "Use trycycle to extend notes.py with --prefix TEXT, --format text|json, and --limit N. Keep the current default text output unchanged when no flags are passed. Reject invalid --format values and non-positive --limit values with a non-zero exit status and a clear error message. Update README examples for default output, prefixed output, json output, and invalid-input behavior. Testing instructions: do not add tests; verify the example commands, error handling, and the changed-file list.") \
  | tee "$smoke_root/output.txt"
```

After the run:

```bash
git -C "$repo" worktree list --porcelain >"$smoke_root/worktrees.txt"
```

Inspect the output and confirm the run shows evidence of both new review-loop behaviors:

- at least one failed plan review followed by a planning revision round
- at least one post-implementation review that triggers an implementation fix round
- successful completion after those retries

Use the final trycycle report plus the logged transcript to confirm loop counts. If this first controlled smoke does not trigger both loops, run one more controlled smoke in a fresh disposable repo with the same structure but one broader request that also requires a new `--summary` mode in both text and json output, then inspect that rerun instead of silently accepting missing loop coverage.

**Step 5: If both CLIs are usable, exercise the secondary transcript-binding path**

Only if both CLIs are actually usable on this machine, run one additional happy-path smoke on the secondary CLI in a fresh disposable repo using the same `smoke-note.txt` task as Step 3. This step is only to cover the alternate transcript-binding path; it is not a substitute for the controlled loop-stressing smoke above.

If the secondary CLI is unavailable or unusable due to local auth/setup, note that the secondary transcript path was skipped and keep the primary-CLI heavy verification as the main result.

**Step 6: Confirm the implementation worktree is still clean**

Run:

```bash
git status --short
git rev-parse --short HEAD
git diff --name-only main...HEAD
```

Expected:
- no uncommitted changes
- `HEAD` matches the last documentation/code commit
- changed-file list is exactly the implementation file set, with no smoke-repo artifacts
