# User Intent Artifact Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use trycycle-executing to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a conductor-managed `USER_INTENT` artifact that is initially extracted by a subagent, then updated append-only by the conductor whenever the user adds relevant intent.

**Architecture:** Reuse Trycycle's existing phase wrapper and prompt-builder plumbing. Add one new subagent prompt to create the initial artifact from the transcript, store the artifact as a run temp file, pass it to later phase prompts with `--set-file USER_INTENT=...`, and make the conductor append later user-intent updates under a chronological section without rewriting the initial extraction.

**Tech Stack:** Markdown skill orchestration, Trycycle prompt templates, existing `orchestrator/run_phase.py`, existing prompt-builder `--set-file` support, Trycycle Explorer static model/docs.

---

## Working Directory

Run every command in this plan from the deepening worktree:

```bash
cd /home/user/code/trycycle/.worktrees/deepening
```

Do not run these steps from `/home/user/code/trycycle`, which is a separate `main` checkout and may not contain the deepening-branch prompt files this plan modifies.

## Design Decisions

### Initial extraction is subagent-owned

The conductor must order a subagent to create the initial `USER_INTENT` artifact. The conductor does not perform the initial extraction itself. This keeps the conductor from spending context on transcript distillation and preserves the role split: subagents do focused document work, while the conductor coordinates and communicates with the user.

### Updates are conductor-owned and append-only

After the initial artifact exists, the conductor owns freshness because it is the only role that continuously receives live user messages. After every user message received after `{USER_INTENT_PATH}` has been created, before dispatching or resuming a subagent, the conductor checks whether the new message adds, removes, corrects, approves, rejects, narrows, broadens, prioritizes, supports an assistant proposal, or otherwise changes the user's intent, constraints, process requirements, scope, or acceptance criteria.

If it does, the conductor appends the new learning to the existing `USER_INTENT` file. It does not rewrite, regenerate, reorder, or summarize prior content. Later appended entries naturally supersede earlier conflicting text because the update section is chronological.

### Preserve exact user intent, not a summary

The initial extraction prompt and conductor update rule should both preserve exact or minimally trimmed source wording. User-authored text is always source material. Assistant-proposed text is also source material when a later user message clearly supports it, accepts it, corrects only part of it, or otherwise makes it part of the user's intent. They must not infer goals, resolve conflicts, normalize language, or convert examples into requirements. If a sentence contains both intent and non-intent material, keep the smallest exact contiguous span or spans that express intent.

### Raw transcript remains available for audit

`USER_INTENT` is the primary scope artifact for subagents, but it should not replace the transcript everywhere. Planning and synthesis prompts should still receive the current transcript where they already do, because the transcript is useful for audit, ambiguity checks, and detecting whether the intent artifact is missing context. The new artifact is a scope condenser, not the only source of truth.

### One artifact per run

Create one `USER_INTENT_PATH` temp file for the Trycycle run after critical unknowns are answered and the testing strategy has been approved or accepted. Keep passing that same path throughout the run. Do not create one intent artifact per phase.

If the user adds intent later, append to the same file. Do not rerun the initial extraction subagent for every user clarification.

### Test strategy remains before intent preparation

The existing testing-strategy phase needs the raw conversation so it can propose a strategy and get user approval. The initial `USER_INTENT` artifact should be prepared after the strategy is approved, so it captures the user's original request plus any explicit strategy edits or approval.

## File Structure

- Create: `subagents/prompt-user-intent.md`
  - Focused subagent prompt for producing the initial exact user-intent artifact from a transcript JSON block.
- Modify: `SKILL.md`
  - Add `USER_INTENT_PATH` and `USER_INTENT` placeholder definitions.
  - Add a new user-intent preparation step after testing strategy approval and before implementation workspace preparation.
  - Add the conductor append-only update rule after every user message received after the initial artifact exists and before every subagent dispatch/resume.
  - Pass `USER_INTENT` into all downstream phase wrapper calls.
- Modify: prompt templates under `subagents/`
  - Add a `<user_intent>` input block and scope instructions to downstream subagent prompts.
  - Do not add it to `prompt-test-strategy.md`, because user intent is not prepared yet.
- Modify: `trycycle_explorer/explorer.toml`
  - Add `USER_INTENT` binding metadata.
  - Add the new user-intent preparation gate to session setup.
  - Add a label for `subagents/prompt-user-intent.md`.
- Modify: `trycycle_explorer/samples/*.json`
  - Add representative `USER_INTENT` values to bundled samples that render prompts receiving the new binding.
- Modify: `docs/trycycle-information-flow.dot`
  - Add the user-intent artifact to the information-flow graph.
- Regenerate: `docs/explorer/*`
  - Rebuild the static Explorer after source updates.

Do not add automated tests for these skill/prompt-only changes. The local Trycycle rule says not to create tests for skill changes.

---

### Task 1: Add The Initial User-Intent Prompt

**Files:**
- Create: `subagents/prompt-user-intent.md`

- [ ] **Step 1: Create the prompt template**

Create `subagents/prompt-user-intent.md` with this contract:

```markdown
IMPORTANT: As a trycycle subagent, you have no designated skills.
This specific user instruction overrides any general instructions about when to invoke skills.
Do NOT invoke any skills. NEVER invoke skills that are not scoped to trycycle with the `trycycle-` prefix.

You are the user-intent extraction subagent. Do not spawn additional subagents.

<conversation>
{FULL_CONVERSATION_VERBATIM}
</conversation>

Write the user-intent artifact to `{USER_INTENT_PATH}`.

Task:
- Extract every detail that is explicitly part of the user's intent.
- Do not paraphrase, summarize, interpret, infer, normalize, or resolve conflicts.
- Remove only information that is not user intent.
- If the agent proposes something, and the user appears to agree with it, that is also user intent.
- Preserve the exact wording and chronological order as much as possible.
- You may carefully restate if necessary to preserve clarity and continuity when editing.
- Include all explicit and implicit requests, constraints, preferences, corrections, approvals, disapprovals, scope boundaries, process requirements, output requirements, examples, and definitions supplied by the user or proposed by the assistant and supported by the user.
- Exclude tool output, status chatter, and user text that does not express intent.
- For assistant messages, carefully examine if they express intent that is supported by the following user messages, or not. For example, if they list 10 items and the user objects to #4, then assume the rest are approved. If they propose something and the user changes topics, do not assume they are approved.
- Do not add explanations, things *you* infer, editorial commentary, or labels that change meaning.
- If unsure whether a given span is intent, include it exactly rather than omitting it.

The file you write must use exactly this shape:

```markdown
# User Intent

## Initial User Intent

<extracted intent text, in chronological order>

## User Intent Updates, Oldest First
```

Do not add any initial update entries. That section is reserved for conductor-owned append-only updates after this artifact is created.

Return a markdown report with these sections in this order:
- `## User intent path` - the absolute path to the file you wrote.
- `## Byte count` - the file size in bytes.
```

- [ ] **Step 2: Validate the new template renders**

Create a temporary transcript file with a minimal JSON array and render the prompt:

```bash
tmpdir="$(mktemp -d)"
printf '[{"role":"user","text":"Make the button say OK."}]\n' > "$tmpdir/conversation.json"
python3 orchestrator/prompt_builder/build.py \
  --template subagents/prompt-user-intent.md \
  --output "$tmpdir/prompt.txt" \
  --set USER_INTENT_PATH="$tmpdir/user-intent.md" \
  --set-file FULL_CONVERSATION_VERBATIM="$tmpdir/conversation.json" \
  --require-nonempty-tag conversation
```

Expected: command exits 0 and writes `$tmpdir/prompt.txt`.

- [ ] **Step 3: Commit the new prompt**

```bash
git add subagents/prompt-user-intent.md
git commit -m "docs: add user intent extraction prompt"
```

---

### Task 2: Wire User Intent Into The Orchestrator

**Files:**
- Modify: `SKILL.md`

- [ ] **Step 1: Add placeholder definitions**

In the placeholder-helper area near the existing definitions for `{IMPLEMENTATION_PLAN_PATH}`, `{TEST_PLAN_PATH}`, and `{REVIEW_LOOP_HISTORY}`, add:

```markdown
When a step below references `{USER_INTENT_PATH}`, use the absolute path to the append-only user-intent artifact for the current Trycycle run.

When a step below references `{USER_INTENT}`, bind the current contents of `{USER_INTENT_PATH}` with `--set-file USER_INTENT={USER_INTENT_PATH}`. Do not manually inline it.
```

- [ ] **Step 2: Add the conductor freshness rule**

In the subagent defaults / user-instructions area, add a rule equivalent to:

```markdown
- User intent freshness is conductor-owned after `{USER_INTENT_PATH}` exists. After every later user message, before dispatching or resuming any subagent, decide whether the new user message adds, removes, corrects, approves, rejects, narrows, broadens, prioritizes, supports an assistant proposal, or otherwise changes the user's intent, constraints, process requirements, scope, or acceptance criteria. If it does, append the exact or minimally trimmed new intent to `{USER_INTENT_PATH}` under `## User Intent Updates, Oldest First`. This may include assistant-proposed text when the user has supported it. Preserve chronological order. Do not rewrite, reorder, summarize, or regenerate earlier content.
```

Also state that the conductor must not create the initial artifact manually; the initial artifact is subagent-owned.

- [ ] **Step 3: Insert a new user-intent preparation step**

Add a new numbered step after the testing-strategy step and before implementation workspace preparation:

```markdown
## 4) Prepare user intent (subagent-owned)

Create a temp file path for `{USER_INTENT_PATH}`. Do not write the initial artifact yourself.

Immediately before dispatch, prepare the `user-intent` phase via the phase wrapper using template `<skill-directory>/subagents/prompt-user-intent.md`, `--set USER_INTENT_PATH={USER_INTENT_PATH}`, `--transcript-placeholder FULL_CONVERSATION_VERBATIM`, `--require-nonempty-tag conversation`, and `--ignore-tag-for-placeholders conversation`, then dispatch a fresh subagent with the returned `prompt_path`.

Monitor by checking every 5 minutes until 60 minutes have passed. Then, and only then, kill it and retry.

When the subagent returns, verify the report contains `## User intent path`, confirm it matches `{USER_INTENT_PATH}`, and confirm the file exists and is non-empty. Do not read or summarize the file contents. Close the completed user-intent subagent and clear any saved handle or `session_id`.
```

Renumber all later top-level steps and update step cross-references so the flow remains coherent.

- [ ] **Step 4: Update downstream phase wrapper calls**

For every phase after user intent exists, add `--set-file USER_INTENT={USER_INTENT_PATH}` to the phase wrapper call:

- `planning-initial`
- `planning-review`
- `planning-review-deepen`
- `planning-synthesis`
- `test-plan`
- `executing`
- `post-implementation-review`
- `post-implementation-review-deepen`
- `planning-reconsider`
- `nonconvergence-review`

Do not add `USER_INTENT` to `test-strategy`.

- [ ] **Step 5: Update dispatch/resume text**

Where SKILL.md says to dispatch or resume a subagent after a user reply, add a reminder to perform the conductor freshness check before sending the next prompt. This matters for `USER DECISION REQUIRED:` answers and out-of-band user instructions.

Keep this concise. Do not duplicate the full freshness rule at every occurrence; define the rule once, then refer to "the user-intent freshness check" before dispatch/resume.

- [ ] **Step 6: Validate SKILL.md references**

Run:

```bash
rg -n "USER_INTENT|user-intent|Prepare user intent|User Intent Updates" SKILL.md subagents
rg -n "## [0-9]+\\)" SKILL.md
```

Expected:
- `USER_INTENT` appears in every downstream phase that should receive it.
- `test-strategy` does not receive it.
- top-level step numbering is sequential.

- [ ] **Step 7: Commit the orchestrator changes**

```bash
git add SKILL.md
git commit -m "docs: add conductor-managed user intent artifact"
```

---

### Task 3: Add User Intent To Downstream Prompts

**Files:**
- Modify: `subagents/prompt-planning-initial.md`
- Modify: `subagents/prompt-planning-review.md`
- Modify: `subagents/prompt-planning-review-deepen.md`
- Modify: `subagents/prompt-planning-synthesis.md`
- Modify: `subagents/prompt-test-plan.md`
- Modify: `subagents/prompt-executing.md`
- Modify: `subagents/prompt-post-impl-review.md`
- Modify: `subagents/prompt-post-impl-review-deepen.md`
- Modify: `subagents/prompt-planning-reconsider.md`
- Modify: `subagents/prompt-nonconvergence-review.md`

- [ ] **Step 1: Add a standard user-intent block**

Add this block near the other input blocks in every downstream prompt listed above:

```markdown
<user_intent>
{USER_INTENT}
</user_intent>
```

For deepening prompts, include the block even though the active subagent may have earlier context. The conductor may have appended out-of-band user intent since the previous prompt.

- [ ] **Step 2: Add role-specific usage rules**

Use concise prompt text so the artifact changes behavior without bloating prompts.

For planning prompts:

```markdown
- Treat `<user_intent>` as the current scope and constraint record. Use the transcript only as audit context. If they conflict, later entries in `<user_intent>` supersede earlier entries, and recorded user intent supersedes unsupported assistant interpretation.
```

For the test-plan prompt:

```markdown
- Use `<user_intent>` as the scope and acceptance source when reconciling the approved testing strategy against the implementation plan. Use the full conversation to recover testing-strategy details, not to broaden scope beyond user intent.
```

For the execution prompt:

```markdown
- Use `<user_intent>` to detect conflicts between the plan and the recorded user intent. If the plan or test plan appears to contradict user intent in a way that changes the required outcome, stop with a blocker instead of guessing.
```

For post-implementation review:

```markdown
- Use `<user_intent>` as the scope boundary for intended behavior. Findings are blocking only when they are necessary to satisfy this user intent, the finalized plans, or regressions introduced by this work.
```

For plan reconsideration:

```markdown
- Use `<user_intent>` to distinguish plan/test-plan gaps from reviewer scope drift. If a current blocker is outside user intent, classify it as reviewer scope rather than updating the plans for it.
```

For nonconvergence review:

```markdown
- Use `<user_intent>` to judge whether unresolved work was truly required by the user or whether the loop was chasing scope outside the user's intent.
```

- [ ] **Step 3: Render representative prompts**

Render a representative downstream prompt with a temporary `USER_INTENT` file:

```bash
tmpdir="$(mktemp -d)"
printf '# User Intent\n\n## Initial User Intent\n\nMake the button say OK.\n\n## User Intent Updates, Oldest First\n' > "$tmpdir/user-intent.md"
printf '[{"role":"user","text":"Make the button say OK."}]\n' > "$tmpdir/transcript.json"
python3 orchestrator/prompt_builder/build.py \
  --template subagents/prompt-planning-review.md \
  --output "$tmpdir/planning-review.txt" \
  --set WORKTREE_PATH=/tmp/worktree \
  --set IMPLEMENTATION_PLAN_PATH=/tmp/plan.md \
  --set-file USER_REQUEST_TRANSCRIPT="$tmpdir/transcript.json" \
  --set-file USER_INTENT="$tmpdir/user-intent.md" \
  --require-nonempty-tag task_input_json \
  --require-nonempty-tag user_intent
```

Expected: command exits 0 and the rendered prompt contains a non-empty `<user_intent>` block.

- [ ] **Step 4: Commit prompt updates**

```bash
git add subagents/prompt-*.md
git commit -m "docs: pass user intent to trycycle subagents"
```

---

### Task 4: Update Explorer And Flow Documentation

**Files:**
- Modify: `trycycle_explorer/explorer.toml`
- Modify: `trycycle_explorer/samples/*.json`
- Modify: `docs/trycycle-information-flow.dot`
- Regenerate: `docs/explorer/index.html`
- Regenerate: `docs/explorer/app.js`
- Regenerate: `docs/explorer/app.css`
- Regenerate: `docs/explorer/explorer-model.json`
- Regenerate: `docs/explorer/vendor/markdown-lite.js`

- [ ] **Step 1: Add Explorer binding metadata**

In `trycycle_explorer/explorer.toml`, add:

```toml
[bindings.USER_INTENT]
label = "User intent artifact"
help = "Append-only artifact containing initial exact user-intent extraction plus conductor-owned chronological updates."
widget = "textarea"
source_category = "user-input"
```

Add a prompt label:

```toml
"subagents/prompt-user-intent.md" = "User intent extraction"
```

Add the user-intent gate to the session setup group after testing strategy and before workspace preparation.

- [ ] **Step 2: Update Explorer outcomes**

In the `[[outcomes]]` section of `trycycle_explorer/explorer.toml`, change the approved testing-strategy path from:

```toml
[[outcomes]]
from = "testing-strategy"
id = "approved"
label = "Strategy approved"
to = "prepare-implementation-workspace"
```

to route through the new gate:

```toml
[[outcomes]]
from = "testing-strategy"
id = "approved"
label = "Strategy approved"
to = "prepare-user-intent"

[[outcomes]]
from = "prepare-user-intent"
id = "user-intent-ready"
label = "User intent ready"
to = "prepare-implementation-workspace"
```

Keep the existing `testing-strategy` revise outcome pointing back to `testing-strategy`.

- [ ] **Step 3: Add gate details**

Add a concise `gate_details` entry explaining:

- a fresh subagent writes the initial artifact
- the conductor later appends updates
- downstream prompts receive `USER_INTENT`

- [ ] **Step 4: Update bundled samples**

For every sample that renders downstream prompts receiving `USER_INTENT`, add a representative value:

```json
"USER_INTENT": "# User Intent\n\n## Initial User Intent\n\n<sample user intent>\n\n## User Intent Updates, Oldest First\n"
```

Keep sample text short. It only needs to prove rendering and show the artifact shape.

- [ ] **Step 5: Update the information-flow graph**

In `docs/trycycle-information-flow.dot`, add a `user_intent_artifact` note node and edges showing:

- transcript builder / prompt builder inputs create the user-intent extraction prompt
- user-intent extraction subagent writes the artifact
- conductor appends user updates
- prompt builder passes the artifact to planning, execution, review, reconsideration, and nonconvergence prompts

- [ ] **Step 6: Rebuild Explorer**

Run:

```bash
python3 -m trycycle_explorer build --repo . --output docs/explorer
```

Expected: command exits 0 and regenerates the static Explorer files.

- [ ] **Step 7: Commit Explorer and flow updates**

```bash
git add trycycle_explorer/explorer.toml trycycle_explorer/samples docs/trycycle-information-flow.dot docs/explorer
git commit -m "docs: show user intent in trycycle explorer"
```

---

### Task 5: Final Validation

**Files:**
- Verify all changed files from prior tasks.

- [ ] **Step 1: Check changed files**

Run:

```bash
git diff --name-only main...HEAD
```

Expected: changed files are limited to:

- `SKILL.md`
- `subagents/prompt-user-intent.md`
- downstream `subagents/prompt-*.md` templates listed in Task 3
- `trycycle_explorer/explorer.toml`
- `trycycle_explorer/samples/*.json`
- `docs/trycycle-information-flow.dot`
- regenerated `docs/explorer/*`
- this plan file

The plan file should be present because it is committed before implementation starts. If it is still untracked when executing this plan, add and commit it before continuing:

```bash
git add docs/plans/2026-05-07-user-intent-artifact.md
git commit -m "docs: plan user intent artifact flow"
```

- [ ] **Step 2: Smoke-render the new phase through the phase wrapper**

Run:

```bash
tmpdir="$(mktemp -d)"
python3 orchestrator/run_phase.py prepare \
  --phase user-intent \
  --template subagents/prompt-user-intent.md \
  --workdir . \
  --artifacts-dir "$tmpdir/phase" \
  --set USER_INTENT_PATH="$tmpdir/user-intent.md" \
  --set-file FULL_CONVERSATION_VERBATIM=<(printf '[{"role":"user","text":"Make the button say OK."}]\n') \
  --require-nonempty-tag conversation \
  --ignore-tag-for-placeholders conversation
```

If process substitution is not available in the current shell, write the transcript to `$tmpdir/conversation.json` first and pass `--set-file FULL_CONVERSATION_VERBATIM="$tmpdir/conversation.json"` instead.

Expected: command exits 0 and reports a prepared prompt path.

- [ ] **Step 3: Smoke-render one downstream phase through the phase wrapper**

Run:

```bash
tmpdir="$(mktemp -d)"
printf '[{"role":"user","text":"Make the button say OK."}]\n' > "$tmpdir/transcript.json"
printf '# User Intent\n\n## Initial User Intent\n\nMake the button say OK.\n\n## User Intent Updates, Oldest First\n' > "$tmpdir/user-intent.md"
python3 orchestrator/run_phase.py prepare \
  --phase planning-review \
  --template subagents/prompt-planning-review.md \
  --workdir . \
  --artifacts-dir "$tmpdir/phase" \
  --set WORKTREE_PATH=/tmp/worktree \
  --set IMPLEMENTATION_PLAN_PATH=/tmp/plan.md \
  --set-file USER_REQUEST_TRANSCRIPT="$tmpdir/transcript.json" \
  --set-file USER_INTENT="$tmpdir/user-intent.md" \
  --require-nonempty-tag task_input_json \
  --require-nonempty-tag user_intent
```

Expected: command exits 0 and reports a prepared prompt path.

- [ ] **Step 4: Build Explorer**

Run:

```bash
python3 -m trycycle_explorer build --repo . --output /tmp/trycycle-explorer-user-intent-check
```

Expected: command exits 0.

- [ ] **Step 5: Review final diff**

Run:

```bash
git diff main...HEAD -- SKILL.md subagents trycycle_explorer docs
```

Check:

- the conductor orders a subagent to create the initial artifact
- the conductor owns append-only updates
- the update section is named `## User Intent Updates, Oldest First`
- downstream prompts receive `USER_INTENT`
- raw transcript inputs remain available where they existed before
- no tests were added for prompt-only skill changes

- [ ] **Step 6: Final commit if needed**

If any validation changes were made after earlier commits:

```bash
git add SKILL.md subagents trycycle_explorer docs
git commit -m "docs: validate user intent artifact flow"
```

---

## Handoff Notes

This plan intentionally does not implement relevance/follow-up ledgers. It creates the durable user-intent artifact that relevance decisions can rely on later.

The most important behavioral invariant is that the initial artifact is subagent-owned, while subsequent updates are conductor-owned and append-only under `## User Intent Updates, Oldest First`.
