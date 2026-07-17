# Prompt Tuning Playbook

Instructions and results ledger for tuning trycycle's prompts against real replay evidence.
Read this before starting a tuning run. Append to the ledger when you finish one.
Written 2026-07-16 after the first three tuning campaigns (plan review, plan edit, code review, approvals).

## The method — the loop that works

1. **Start from a real run, never intuition or reconstructed scenarios.** Pick a run whose
   outcome is known from ground truth (merged branch, acceptance artifacts, breaker trip) —
   not from the run's own claims. Ugly non-converged runs are the most valuable corpora.
2. **Census before building anything.** Read the run's real reports and classify what actually
   drove each round (genuine defects / preference findings / re-litigation / editor-introduced /
   environment). Ten minutes of census has twice redirected an entire campaign. Verify the
   passage you intend to change appears **verbatim** in the run's rendered prompts — runs
   predating a template change are useless for testing that change.
3. **Build a frozen replay bed.** The replay unit is one rendered prompt, byte-identical,
   run as a single headless query. The environment must be frozen to the reviewed moment:
   git clone truncated at the reviewed commit (later commits unresolvable even by SHA),
   artifacts reconstructed by write-time cutoff, gitignored files the prompts assume recreated
   (build-config files!), secrets replaced with placeholders that still pass the prompts' checks,
   per-trial disposable workspaces, and the literal staging paths bind-mounted per trial.
4. **Measure the noise floor first.** Replay identical prompts N times before comparing
   anything. Ours: verdict self-agreement ~89%, finding reproduction ~58%, clean-territory
   false alarms ~8–13%. Any A/B delta inside the floor is noise. This control also catches
   invalid beds (see failures below).
5. **A/B one variable.** Byte-exact substitution of the changed passage, logged with diffs,
   round-trip asserted, stop if the old passage isn't verbatim. 3–5 trials per query minimum.
   Blind grading (Report A vs B, variant and realness hidden); deterministic extraction where
   a production extractor exists, mirroring each variant's own routing rules.
6. **Test both sides.** A defect-dense corpus proves the win; a genuinely-clean corpus proves
   the change doesn't manufacture work. Both are required before shipping.
7. **Ship rule.** Deploy measured wins. Hold proven-safe-but-unproven-better. Never deploy on
   argument alone (prompt changes) — reviewed-only is acceptable solely for orchestration/flow
   changes that no past data can exercise, with an explicit live checkpoint defined.
8. **Deploy** per AGENTS.md "Local test deployment" (copy to every install, byte-verify).
9. **Define the live checkpoint** — the observable behavior in the next real run that confirms
   or falsifies the change. Every real run is free future eval data: archive its staging
   directory immediately (they are perishable; host-agent traces preserve rendered prompts —
   first user message = prompt, last assistant message = report — but staging is richer).

## Hard rules

- **No test-derived content in prompts.** Categorical language only; enforce with a mechanical
  banned-term check built from the corpus's domain vocabulary.
- **Don't chase individual failed cases** — that is memorizing the test. Leave shared failures
  standing and report them.
- **Fix the environment, don't adjust the numbers.** When false alarms trace to bed infidelity,
  recreate the missing piece and rerun. Hand-adjusted estimates drifted optimistic every time.
- **Audit extreme or convenient numbers before believing them** (0%, 100%, or exactly what you
  hoped). Read raw replies, not just grades.
- **One experiment at a time on a bed.** A concurrent uncontrolled run contaminated an A/B once;
  kill and quarantine anything else touching the bed.
- **Timestamp everything** so the next run's wall-clock estimate is grounded.

## Results ledger

### Measured wins (deployed)

| Change | Stage | Evidence |
|---|---|---|
| Category-2 blocking bar re-anchored to outcome (block only for correctness/regression/durability; preference = minor/nit) + design-decisions refute clause | planning-review | 150-trial A/B on a real converged run: preference-driven blockers 4→0, false alarms 12.7%→9.1%, verdict agreement 84%→86.7%. Known trade-off: occasionally downgrades repo-convention gaps (recall 50%→42.5%, localized to that class). |
| Thoroughness / class-enumeration discipline (a found defect implies its class; enumerate siblings before returning; report everything; "clean" requires visible enumeration) | planning-review | Replay of an 8-round grind's round 1: future-round findings surfaced at r1 2/24→5/24 (~2.5×), own-round recall up (panel 7,6,7→8,9,9 of 14), substantive false alarms equal (7 vs 7). Clean-round safety: 2/25 = baseline exactly, verdicts unmoved, enumeration visible in 25/25 reports. |
| Same Category-2 bar + preference-never-forces-REVISED + design-decisions maintenance | planning-edit | 30-trial A/B: no regression (verdicts 15/15 both arms, real fixes 19/20 vs 20/20). Shipped for standard-consistency with its reviewers, not as a win. |

### No measurable effect (lesson: fix the right layer)

- **Category-2 bar at the plan editor**: the editor was already robust to preference pressure —
  it never produced a preference-driven REVISED in any tested round. The reviewers, not the
  decider, were the round-amplifier. Measure each layer separately before "fixing" it.
- **Category-2 bar at post-impl review + merge**: parity on a converged run (would-block 0/25
  in BOTH arms; merge 5/5 both). The corpus lacked the failure the change targets. **Held, not
  deployed.** Needs a real run where code review blocks on preference; replay that round when
  one appears.

### Invalid approaches — do not repeat

1. **Tuning on reconstructed/synthetic fixtures.** An entire first campaign (8 files) was
   reverted: inputs the model sees must be byte-identical to production, or you tune for the
   wrong thing and risk single-axis optimization with unmeasured regressions elsewhere.
2. **Replaying against a live workspace.** Prompts reference absolute paths; the workspace had
   advanced past the reviewed state and replays scored 0% recall by correctly reviewing
   already-fixed code. Freeze everything (git truncation + artifacts cutoff + /tmp binding).
3. **Omitting gitignored files from the bed.** One missing build-config file caused 9 of 12
   false alarms. The bed must contain what the original reviewer's machine had.
4. **Hand-adjusting metrics for known artifacts** instead of fixing the bed and rerunning —
   the estimate (~9%) was optimistic vs the measured truth (~13–17%).
5. **Building on a wrong-era corpus.** A converged run predated the prompt under test (used a
   different review design entirely); caught by the verbatim check before any spend.
6. **Greedy-regex extraction of verdicts.** Anchor parsing to the production wrapper/extractor;
   a regex bug silently misread 6 replies before being caught.

### Shipped on review only — live checkpoint pending

- **Combined approvals** (one approval at the strategy gate carrying a binding validation
  forecast; test plan re-asks only on material deviation incl. dropped validation; autonomy
  relocates the approval, never removes it). Not replay-testable — no past data exercises an
  approval flow. **Checkpoint: the next real run must ask exactly once.** A second ask for
  already-forecast ground, or a mid-run probe permission covered by the forecast, is a defect —
  archive that run as the fix's corpus.

## Open targets (in expected-value order)

1. **Editor shallow-fix discipline** (~13% of the 8-round grind was editor-introduced defects —
   incomplete fixes, count drift). Same class-enumeration principle applied to the edit prompt;
   the grind corpus supports replaying its edit rounds directly.
2. **Late findings invisible even to thorough round-1 review** (19/24 in the grind corpus).
   Needs a forensic pass: genuinely emergent (visible only after plan edits) vs per-territory
   time starvation. The answer decides between "accept multi-round" and a different lever
   (e.g., more reviewers per territory — untested; the ~58% reproduction floor suggests
   coverage is a lottery, so panel size may buy breadth).
3. **Code-review-stage discriminating corpus** — accumulates for free from live runs; act on
   the first preference-blocked round.

## Operational facts

- Tuning workspace convention: `~/.amplifier/evaluation/trycycle/` — `corpus/` (archived run
  stagings), `replay/` (harness + frozen snapshots + rewritten prompts), `replay/runs/<id>/`
  (per-run raw replies, grades, summary.md). Corpora and results never live in this repo.
- Costs (claude-class model, 6–8 parallel): ~350–520s per replayed query; 150-trial A/B ≈ 2h;
  30-trial editor A/B ≈ 1h; grading ~1–4s/trial amortized. Snapshot construction: minutes.
- Deploy procedure: AGENTS.md "Local test deployment". Revert in an install:
  `git checkout -- <files>` in that clone.
