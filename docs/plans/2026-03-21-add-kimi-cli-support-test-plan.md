# Kimi CLI Support Test Plan

The accepted strategy still holds. The implementation plan confirms the same explicit-Kimi architecture and user-visible surfaces, and narrows the deterministic harnesses to synthesized `.kimi` share roots plus a fake `kimi` binary. That does not change cost or scope; it just makes the coverage more reproducible. The strategy also called for targeted code-behavior unit tests; this plan keeps those as small support checks at the end because the higher-value subprocess tests already cover most of the same logic through the real user-facing seams.

## Harness requirements

### Synthesized Kimi share-root harness

- **What it does:** Creates temporary Kimi runtime trees with `kimi.json`, `sessions/<md5(workdir)>/<session-id>/context.jsonl`, and optional top-level decoy files such as `wire.jsonl` and `context_sub_1.jsonl`.
- **What it exposes:** Deterministic direct-lookup and canary-fallback transcript inputs for `orchestrator/user-request-transcript/build.py` and `orchestrator/run_phase.py`.
- **Estimated complexity:** Low. It is simple temp-dir fixture setup inside the existing subprocess tests.
- **Tests that depend on it:** T1, T2, T3, T10, T15.

### Fake Kimi CLI harness

- **What it does:** Prepends a temporary fake `kimi` executable to an isolated `PATH`, serves Kimi-compatible help text for probe checks, records argv, and can write success or failure `context.jsonl` files under a temporary `KIMI_SHARE_DIR`.
- **What it exposes:** A deterministic way to exercise probe, run, resume, effort/model mapping, reply capture, and zero-exit failure normalization through the real `subagent_runner.py` and `run_phase.py` CLIs.
- **Estimated complexity:** Medium. It needs temp-file state plus a small scriptable fake binary.
- **Tests that depend on it:** T4, T5, T6, T7, T8, T15.

### Live Kimi smoke harness

- **What it does:** Runs the real installed `kimi` CLI against temp prompts and workdirs, then asserts against `result.json`, `reply.txt`, stdout/stderr captures, and the persisted Kimi session files.
- **What it exposes:** Acceptance evidence that Trycycle works against the real Kimi CLI surface and real Kimi session persistence, including the known zero-exit misconfiguration case.
- **Estimated complexity:** Medium. It depends on a working local Kimi installation; success-path smokes also depend on auth/config.
- **Tests that depend on it:** T9, T10, T11.

## Test plan

1. **T1 — Kimi direct transcript lookup renders visible conversation turns without a canary**
   - **Type:** scenario
   - **Disposition:** extend
   - **Harness:** Synthesized Kimi share-root harness + Interaction harness + Output capture harness
   - **Preconditions:** A temp share root contains `kimi.json` with `last_session_id` for the temp `workdir`, plus `sessions/<md5(workdir)>/<session-id>/context.jsonl` containing a user turn and an assistant `content` list with both `think` and `text` blocks.
   - **Actions:** Run `python3 orchestrator/user-request-transcript/build.py --cli kimi-cli --search-root <share-root> --output <output-path>` from `cwd=<workdir>`.
   - **Expected outcome:** The command exits `0`; the rendered JSON at `<output-path>` contains the user turn and only the visible assistant text, not the `think` content. This follows the accepted local Kimi session observations in the testing strategy and the implementation plan’s direct-lookup contract.
   - **Interactions:** `argparse` choice handling, Kimi adapter lookup, filesystem reads from `kimi.json` and `context.jsonl`, transcript rendering.

2. **T2 — Kimi canary fallback ignores non-transcript decoys when direct lookup is unavailable**
   - **Type:** boundary
   - **Disposition:** extend
   - **Harness:** Synthesized Kimi share-root harness + Interaction harness + Output capture harness
   - **Preconditions:** A temp share root contains `kimi.json` with `last_session_id: null`, a top-level `context.jsonl` containing the canary and visible conversation turns, and decoy files such as `wire.jsonl` and `context_sub_1.jsonl` containing the same canary.
   - **Actions:** Run `python3 orchestrator/user-request-transcript/build.py --cli kimi-cli --canary <canary> --search-root <share-root> --output <output-path>`.
   - **Expected outcome:** The command exits `0`; the rendered JSON comes from the top-level transcript file and matches the visible conversation, rather than accidentally matching `wire.jsonl` or `context_sub_*.jsonl`. This is justified by the implementation plan and accepted strategy, which identify only top-level `context*.jsonl` files as valid fallback transcript sources.
   - **Interactions:** Canary search, transcript-file filtering, session-file recency selection, transcript rendering.

3. **T3 — `run_phase.py prepare` anchors Kimi transcript lookup to `--workdir`, not the caller’s cwd**
   - **Type:** scenario
   - **Disposition:** extend
   - **Harness:** Synthesized Kimi share-root harness + Interaction harness + Output capture harness
   - **Preconditions:** The temp share root registers only the phase `workdir` inside `kimi.json`. The test process runs from a different cwd. A template requires `{USER_REQUEST_TRANSCRIPT}` inside a non-empty tagged block.
   - **Actions:** Run `python3 orchestrator/run_phase.py prepare --phase planning-initial --template <template> --workdir <workdir> --transcript-placeholder USER_REQUEST_TRANSCRIPT --transcript-cli kimi-cli --transcript-search-root <share-root> --require-nonempty-tag task_input_json` from outside `<workdir>`.
   - **Expected outcome:** The command exits `0`; `result.json` reports `status: "prepared"`; the rendered prompt contains the transcript from the registered Kimi session without requiring a canary. This is required by the implementation plan’s workdir-anchoring design and by Kimi’s workdir-keyed session behavior observed in the accepted strategy.
   - **Interactions:** `run_phase.py` cwd control, transcript-builder subprocess invocation, Kimi adapter direct lookup, prompt builder validation.

4. **T4 — `run_phase.py run --backend kimi --dry-run` selects the Kimi runner path**
   - **Type:** scenario
   - **Disposition:** extend
   - **Harness:** Fake Kimi CLI harness + Interaction harness + Output capture harness
   - **Preconditions:** A fake `kimi` binary is first on `PATH` and returns help text that satisfies the Kimi probe. A minimal template and temp workdir exist.
   - **Actions:** Run `python3 orchestrator/run_phase.py run --phase smoke --template <template> --workdir <workdir> --backend kimi --dry-run`.
   - **Expected outcome:** The outer payload exits `0` with `status: "ok"`; the nested `dispatch` payload is also `ok`; `dispatch.backend` is `kimi`; and the recorded command begins with the fake `kimi` binary. This matches the implementation plan’s explicit-backend requirement and the accepted strategy’s dry-run red-to-green goal.
   - **Interactions:** `run_phase.py`, `subagent_runner.py probe`, backend selection, dry-run artifact generation.

5. **T5 — Runner probe reports Kimi as available and resumable when it is the only backend on the machine**
   - **Type:** scenario
   - **Disposition:** new
   - **Harness:** Fake Kimi CLI harness + Interaction harness + Output capture harness
   - **Preconditions:** `PATH` contains only the fake `kimi` binary. `HOME` points at a temp directory so home-based Codex/Claude fallback paths cannot be discovered.
   - **Actions:** Run `python3 orchestrator/subagent_runner.py probe`.
   - **Expected outcome:** The JSON output includes a `kimi` backend entry with `available: true` and `supports_resume: true`; `selected_backend` is `kimi`; and the backend order still keeps Kimi after Codex and Claude. This is justified by the implementation plan and by Kimi’s documented `--session` and `--continue` options plus local help output.
   - **Interactions:** Binary resolution, help parsing, backend preference ordering.

6. **T6 — Runner `run --backend kimi` succeeds only when stdout is backed by a persisted visible assistant reply**
   - **Type:** scenario
   - **Disposition:** new
   - **Harness:** Fake Kimi CLI harness + Programmatic state harness + Output capture harness
   - **Preconditions:** The fake `kimi` binary writes a success `context.jsonl` whose final visible assistant text matches what it prints to stdout. Temp prompt, workdir, artifacts dir, and `KIMI_SHARE_DIR` exist.
   - **Actions:** Run `python3 orchestrator/subagent_runner.py run --phase smoke --prompt-file <prompt> --workdir <workdir> --artifacts-dir <artifacts-dir> --backend kimi --effort max --model kimi-test-model`.
   - **Expected outcome:** The command exits `0`; `result.json` reports `status: "ok"`; `reply.txt` matches stdout; `session_id` is non-empty; and the fake binary’s recorded argv includes `--print`, `--final-message-only`, `--work-dir <workdir>`, `--session <id>`, `--thinking`, and `--model kimi-test-model`. This is required by the implementation plan, Kimi’s print-mode docs, and the accepted strategy’s emphasis on persisted-session validation.
   - **Interactions:** Command construction, effort-to-thinking mapping, stdout capture, session persistence, result classification.

7. **T7 — Runner `resume --backend kimi` uses the saved session id explicitly instead of `--continue`**
   - **Type:** scenario
   - **Disposition:** new
   - **Harness:** Fake Kimi CLI harness + Programmatic state harness + Output capture harness
   - **Preconditions:** The fake `kimi` binary records argv and can append a visible assistant reply to an existing session context. A known Kimi `session_id` exists.
   - **Actions:** Run `python3 orchestrator/subagent_runner.py resume --phase smoke --session-id <session-id> --prompt-file <prompt> --workdir <workdir> --artifacts-dir <artifacts-dir> --backend kimi`.
   - **Expected outcome:** The command exits `0`; `result.json` reports `status: "ok"` and the same `session_id`; the recorded argv includes `--session <session-id>` and does not include `--continue`. This follows the implementation plan’s deterministic-resume design and Kimi’s documented `--session` option.
   - **Interactions:** Resume command construction, session persistence, stdout/reply capture, result classification.

8. **T8 — Runner escalates when Kimi exits `0` but does not persist a visible assistant reply**
   - **Type:** boundary
   - **Disposition:** new
   - **Harness:** Fake Kimi CLI harness + Programmatic state harness + Output capture harness
   - **Preconditions:** The fake `kimi` binary is configured to print `LLM not set` to stdout, exit `0`, and write no matching visible assistant reply to the session context.
   - **Actions:** Run `python3 orchestrator/subagent_runner.py run --phase smoke --prompt-file <prompt> --workdir <workdir> --artifacts-dir <artifacts-dir> --backend kimi`.
   - **Expected outcome:** The command exits `1`; `result.json` reports `status: "escalate_to_user"`; the message surfaces the real printed problem text instead of `kimi exited with code 0`; and `stdout.txt` plus `reply.txt` preserve the printed failure text for diagnosis. This is the highest-priority failure mode from the accepted strategy and implementation plan.
   - **Interactions:** Exit-code handling, Kimi session validation, user-facing error normalization, artifact capture.

9. **T9 — Real Kimi run and resume preserve session identity and return visible replies through Trycycle**
   - **Type:** scenario
   - **Disposition:** new
   - **Harness:** Live Kimi smoke harness + Programmatic state harness + Output capture harness
   - **Preconditions:** The installed `kimi` CLI is available and authenticated/configured for a normal success-path run. Temp workdir, prompts, and artifacts dirs exist.
   - **Actions:** Run `python3 orchestrator/subagent_runner.py run --phase smoke --prompt-file <prompt1> --workdir <workdir> --artifacts-dir <run1> --backend kimi --timeout-seconds 180`, read `session_id` from `run1/result.json`, then run `python3 orchestrator/subagent_runner.py resume --phase smoke --session-id <session-id> --prompt-file <prompt2> --workdir <workdir> --artifacts-dir <run2> --backend kimi --timeout-seconds 180`.
   - **Expected outcome:** Both commands exit `0`; both payloads report `status: "ok"`; `run2.session_id == run1.session_id`; and the second reply is present both in `run2/reply.txt` and in the persisted Kimi session context. This is the strongest source-of-truth path from the accepted strategy because it exercises the real CLI, real persistence, and Trycycle’s real runner surface together.
   - **Interactions:** Real Kimi CLI, network/auth configuration, runner artifact generation, on-disk Kimi session persistence.

10. **T10 — Builder and phase wrapper agree on the latest visible reply from a live Kimi session**
    - **Type:** differential
    - **Disposition:** new
    - **Harness:** Live Kimi smoke harness + Synthesized/real transcript comparison via Output capture harness
    - **Preconditions:** T9 has created a live Kimi session in the temp `workdir`, with a known final assistant reply in the latest turn.
    - **Actions:** From the repo root, run `python3 orchestrator/run_phase.py prepare --phase smoke --template <template> --workdir <workdir> --artifacts-dir <phase-dir> --transcript-placeholder USER_REQUEST_TRANSCRIPT --transcript-cli kimi-cli --require-nonempty-tag task_input_json`. Separately, from `cwd=<workdir>`, run `python3 orchestrator/user-request-transcript/build.py --cli kimi-cli --output <transcript-json>`. Compare the wrapper’s prompt content and the builder’s rendered JSON.
    - **Expected outcome:** Both outputs include the same final visible assistant reply from the live session, and `run_phase.py prepare` succeeds even though it is launched from outside `<workdir>`. This follows the implementation plan’s workdir-anchoring requirement and uses the live Kimi session files as the reference source of truth.
    - **Interactions:** `run_phase.py`, transcript builder, prompt builder, real Kimi session files.

11. **T11 — Real Kimi zero-exit misconfiguration escalates instead of producing a false success**
    - **Type:** boundary
    - **Disposition:** new
    - **Harness:** Live Kimi smoke harness + Output capture harness
    - **Preconditions:** A temp `KIMI_SHARE_DIR` is isolated from any configured Kimi runtime data. Temp workdir, prompt, and artifacts dir exist.
    - **Actions:** Run `KIMI_SHARE_DIR=<isolated-share-root> python3 orchestrator/subagent_runner.py run --phase smoke --prompt-file <prompt> --workdir <workdir> --artifacts-dir <artifacts-dir> --backend kimi --timeout-seconds 60`.
    - **Expected outcome:** The command exits `1`; `result.json` reports `status: "escalate_to_user"`; and the message surfaces the real printed failure text rather than claiming a successful run. This is justified by the accepted strategy’s local observation that Kimi can print `LLM not set` while still exiting `0`.
    - **Interactions:** Real Kimi CLI error semantics, environment-variable-driven runtime location, result classification, artifact capture.

12. **T12 — The existing Python test suite stays green after Kimi support lands**
    - **Type:** regression
    - **Disposition:** existing
    - **Harness:** Interaction harness
    - **Preconditions:** All Kimi implementation tasks are complete.
    - **Actions:** Run `python3 -m unittest discover -s tests -p 'test_*.py'`.
    - **Expected outcome:** The suite exits `0`, including the pre-existing prompt-builder, transcript-builder, and phase-wrapper tests plus the new Kimi coverage. This is the current repo’s main automated regression gate and is already green on the baseline branch.
    - **Interactions:** All Python CLI seams covered by the suite.

13. **T13 — Existing Codex and Claude dry-run runner paths still return `ok`**
    - **Type:** regression
    - **Disposition:** existing
    - **Harness:** Interaction harness + Output capture harness
    - **Preconditions:** A temp prompt file exists. Codex and Claude remain installed or otherwise probeable in the environment.
    - **Actions:** Run `python3 orchestrator/subagent_runner.py run --phase smoke --prompt-file <prompt> --workdir /tmp --backend codex --dry-run` and `python3 orchestrator/subagent_runner.py run --phase smoke --prompt-file <prompt> --workdir /tmp --backend claude --dry-run`.
    - **Expected outcome:** Both commands exit `0` with `status: "ok"`. This follows the accepted strategy’s regression requirement and protects the existing fallback backends from Kimi-related refactors.
    - **Interactions:** Backend selection, existing Codex/Claude command builders, dry-run artifact generation.

14. **T14 — README and SKILL advertise explicit Kimi usage without promising unsupported auto-detection**
    - **Type:** invariant
    - **Disposition:** new
    - **Harness:** Direct file-read harness + Output capture harness
    - **Preconditions:** Documentation changes are complete.
    - **Actions:** Run `rg -n "kimi-cli|~/.kimi/skills/trycycle|--backend kimi|--transcript-cli kimi-cli|auto cannot reliably detect" SKILL.md README.md`.
    - **Expected outcome:** `README.md` names Kimi CLI as a supported host and includes `~/.kimi/skills/trycycle`; `SKILL.md` tells Kimi-hosted Trycycle to pass `--transcript-cli kimi-cli` and `--backend kimi`; and neither file claims that `auto` reliably detects Kimi. This is justified by the implementation plan and the official Kimi skills-discovery docs, which list `~/.kimi/skills/` as a supported skills path.
    - **Interactions:** User-facing install/docs surface only.

15. **T15 — Probe, transcript build, and Kimi dry-run stay within a generous local latency bound**
    - **Type:** invariant
    - **Disposition:** new
    - **Harness:** Synthesized Kimi share-root harness + Fake Kimi CLI harness + Interaction harness
    - **Preconditions:** The synthesized share root and fake `kimi` binary from earlier tests are available.
    - **Actions:** Measure wall-clock duration for `python3 orchestrator/subagent_runner.py probe`, `python3 orchestrator/user-request-transcript/build.py --cli kimi-cli --search-root <share-root> --output <output-path>`, and `python3 orchestrator/run_phase.py run --phase smoke --template <template> --workdir <workdir> --backend kimi --dry-run`.
    - **Expected outcome:** Each command completes in under 5 seconds locally. This follows the accepted strategy’s low-risk performance target: probe, transcript prepare, and dry-run should finish in a few seconds, and any larger delay indicates a severe bug or hang.
    - **Interactions:** Process startup, filesystem traversal, subprocess chaining, fake probe path.

16. **T16 — Kimi transcript extraction ignores meta records and keeps the last visible assistant reply in each user interval**
    - **Type:** unit
    - **Disposition:** new
    - **Harness:** Direct API harness
    - **Preconditions:** A temporary `context.jsonl` fixture contains `_system_prompt`, `_checkpoint`, and `_usage` records, multiple assistant records within one user interval, and assistant `content` blocks that mix `think` and `text`.
    - **Actions:** Import the Kimi transcript adapter module directly and call its `extract_transcript(<context-path>)` entry point on the fixture file.
    - **Expected outcome:** The returned turns include every visible user turn, ignore meta records and `think` blocks, and keep only the last non-empty visible assistant reply before the next user turn. This is justified by the accepted local Kimi session observations and the implementation plan’s parser contract.
    - **Interactions:** Pure transcript parsing logic only.

17. **T17 — Kimi reply comparison normalizes line endings and the print-mode trailing newline before deciding success**
    - **Type:** unit
    - **Disposition:** new
    - **Harness:** Direct API harness
    - **Preconditions:** The shared Kimi-aware result-classification helper from Task 3 is available for direct import.
    - **Actions:** Call that helper directly with Kimi cases where printed stdout and persisted assistant text differ only by `\r\n` versus `\n` and a single trailing newline, and with cases where the persisted text is missing or materially different.
    - **Expected outcome:** The normalization-only variants classify as success, while missing or materially different persisted replies classify as `escalate_to_user`. This follows the accepted strategy’s local Kimi print-mode observation and the implementation plan’s persisted-reply validation rule.
    - **Interactions:** Pure result-classification and text-normalization logic only.

## Coverage summary

### Covered

- Transcript lookup and parsing for Kimi direct lookup and canary fallback, including decoy-file filtering and visible-text extraction.
- `run_phase.py` explicit Kimi surfaces for `prepare` and `run`, including the critical cwd-to-workdir handoff.
- `subagent_runner.py` probe, run, and resume behavior for Kimi, including effort/model mapping, explicit session-based resume, stdout/reply capture, and Kimi-specific success validation.
- Real Kimi acceptance behavior for success-path run/resume, transcript reuse, and the known zero-exit misconfiguration failure mode.
- Regression protection for the existing Python suite and for Codex/Claude dry-run behavior.
- User-facing documentation updates that are necessary for real Kimi-hosted usage.
- Low-risk performance sanity for probe, transcript build, and Kimi dry-run paths.
- Small pure-logic checks for transcript extraction and persisted-reply comparison, kept as support material rather than primary evidence.

### Explicitly excluded per the agreed strategy

- Native Kimi `Task`-tool orchestration or subagent/agent integration. The implementation plan explicitly keeps Trycycle on the existing transcript-adapter and fallback-runner architecture. Risk: if someone later adds native Kimi orchestration, this plan will not validate it.
- Reliable `auto` host detection for Kimi. The accepted strategy and implementation plan both treat explicit `--transcript-cli kimi-cli` and `--backend kimi` as the supported contract. Risk: a future heuristic-based auto-detection change would need additional coverage.
- `kimi export`-based workflows. The plan intentionally treats on-disk session files as the source of truth. Risk: if implementation starts depending on `kimi export`, this plan will not catch export-specific regressions.
- Manual QA or subjective review. All checks are artifact-based and reproducible, as required by the accepted strategy. Risk: none beyond whatever objective assertions fail to express.

### Residual risk

- Live Kimi success-path acceptance depends on local auth/config. If the environment is not configured, T9 and the success half of T10 will need to be reported as blocked even if the deterministic tests are green.
- The Kimi docs document the CLI surface and data locations, but not every transcript-record shape or every zero-exit failure string. Deterministic parser and failure-normalization tests therefore rely partly on the accepted local Kimi observations captured in the testing strategy and implementation plan.
