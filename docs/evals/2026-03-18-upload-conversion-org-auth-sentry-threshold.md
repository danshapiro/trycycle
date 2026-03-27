# Upload Conversion + Org Auth + Sentry Regressions (threshold)

## Source

- Repo under investigation: `/home/user/code/DirectorDeck/.worktrees/trycycle-2w-upload-failure`
- User task theme: two independent bug fixes (corrupt slide PNGs leaking past conversion, org selector subscribing to Firestore before auth) plus Sentry cleanup
- Trycycle phase: plan-editor loop

## Why this input is the right baseline

Commit `26e69181` is the result of 5 successive review rounds on the initial plan. The reviews made substantive architectural corrections:

- Changed thumbnail validation from a standalone `sharp().metadata()` probe to reusing the real `prepareSlideThumbnail()` pipeline, preventing drift across Docker/Windows/Linux.
- Switched error type from plain `Error` to `CodedApiError` with structured context (`stage`, `slideIndex`, `pngPath`).
- Added signed-out terminal state to the org auth hook (prevents permanent `loading` hang).
- Hardened test contracts: dynamic per-slide mocks, `mockDelete` assertions for upload-failure cleanup, Radix Select replaced with deterministic inline mock.
- Fixed test runner invocation throughout (`npx vitest run` instead of `npm run test:unit -- <file>`, which silently drops file arguments in this repo).
- Wrapped Sentry verification script in async IIFE for Node compatibility, added `~/.sentryclirc` auth fallback.
- Added barrel export for `prepareSlideThumbnail()` in file structure and commit steps.
- Added `npm run test:unit` as full-suite verification step (repo policy).

The plan was then executed successfully — commits `9540c198` through `7e10a3b1` on branch `trycycle-2w-upload-failure` implement the plan and pass all tests.

## Why this case adds value to the suite

All three existing threshold cases are single-concern, moderate-size plans. This candidate is structurally different:

1. **Multi-concern plan** — two independent subsystems (server-side thumbnail pipeline + client-side React hook lifecycle) plus an operational task. Tests whether the reviewer can evaluate a compound plan without over-reviewing individual sections that are already correct.
2. **Heavy inline code** — ~200+ lines of inline test code with dynamic mock implementations, inline Node scripts for Sentry API verification, and recommended implementation shapes. Creates a rich surface for cosmetic over-review (rewriting working mocks, restructuring test patterns).
3. **Cross-cutting constraints** — `npx vitest run` appears in multiple tasks; barrel exports affect both file structure and commit steps. A reviewer that "fixes" one section without seeing the cross-cutting constraint would break consistency.
4. **Operational + code hybrid** — Task 1 is purely operational (Sentry CLI/API), Tasks 2–3 are code changes, Task 4 is verification. No existing threshold case has this structure.

## Eval shape

- Source repo: `/home/user/code/DirectorDeck`
- Input plan commit: `26e69181`
- Input plan path: `docs/plans/2026-03-18-fix-upload-conversion-and-org-auth-sentry-regressions.md`
- Session artifact: `/home/user/.claude/projects/-home-user-code-DirectorDeck--worktrees-trycycle-2w-upload-failure/3e24056a-e238-4822-9de2-241d8b100e4a.jsonl`

Mode: single review turn.

Pass only if:
- verdict is `READY`
- there are no file edits
- there is no new commit

Failure condition:
- Returns `REVISED` without finding a substantive gap against the user request or planning standard
- Rewrites inline test code, restructures mock patterns, or normalizes formatting in an already-correct plan
- Splits or reorders independent tasks without a concrete correctness justification
- Imposes template structure on the operational task (Task 1) that doesn't need code steps
