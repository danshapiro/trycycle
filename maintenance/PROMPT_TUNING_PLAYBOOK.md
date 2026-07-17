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
| Conditional dynamic defect quota ({{#if QUOTA_TOTAL}} block; remaining-count formula, orchestrator-computed; omit when remaining ≤ territories) | planning-review + SKILL.md step 9 | L1 quota (9/6) on a defect-dense round 1: future-round findings surfaced at r1 21%→50% (5/24→12/24 pooled), own-round recall 11/14→12/14, inflation ~flat (3 vs 2 per 15). Round-2 formula A/B: remaining-count D1 (30/6/4) beat static (15/22 vs 14/22 catalog findings at half the inflation, 7 vs 12) and decay (11/22). No-quota render is byte-identical to the clean-round-PASSED template (asserted with the real engine), so near-clean rounds inherit the banked 2/25 false-alarm baseline. Calibration refinement (97859cb, superseding a9592f3): findings-driven upward-only estimate; quota passes iff last round's findings exceeded territory count; plan seed 13/kline (recorded), code review round 1 quota-free then N = 2 x F1. Editor consumption of `## Lesser findings` is an UNTESTED surface. |
| Post-impl review: Category-2 bar + thoroughness + conditional dynamic quota (276fd24; remaining-count formula at the code-review gate — since 97859cb: round 1 quota-free, then N = 2 x first-round critical+major count, upward-only) | post-impl-review + SKILL.md code-review gate | Generalization on a second corpus (fork-oom SDD task gates, different domain and an older template — mechanism test, scope-limited): thoroughness+quota lifted real-finding recall 9/17→12/17 and surfaced 2 of 3 re-review-only findings at first review, including the missed invalid-fork-candidate critical; zero critical-tier severity inflation. Clean gate on the converged yente round (current template, quota omitted per drop rule): would-block 0/25 = baselines exactly; extras all minor/nit; enumeration visible 19/25. Quota-ACTIVE rendering on the current template is an UNTESTED surface — watch the first defect-dense live verification round. |

### Calibration analysis (quota initial estimate)

- Dataset (expanded): ~35 runs across ~15 codebases from a full sweep of all agent stores
  (codex + claude code + opencode, both OS sides) — countable per-round trajectories from
  natively (300 findings over 21 rounds), planchette (plan 127; code review 72 over 9 rounds),
  glowforge, plus the prior 3 anchors. Capture-recapture remains infeasible (disjoint
  territories, zero overlap).
- The expanded data broke the a9592f3 formula three ways: (1) OMIT-RULE UNDER-ESTIMATE —
  natively's cumulative blew past any plausible size-based estimate by round 3, so
  "remaining <= territories" would have silenced the quota while rounds still found 10–20
  each; (2) MULTIPLIER SPREAD — total-vs-first-round ratios span 1.18x–20x (planchette code
  review 2.88x), refuting any fixed multiplier including the shipped 1.2x; (3) RATCHET
  PRECONDITION RARELY HOLDS — per-round counts are non-monotone in most real runs (natively
  x2, planchette reopen, directordeck), and the observed failure mode is UNDER-estimation,
  so downward pressure was backwards.
- Shipped replacement (97859cb): findings-driven, upward-only. N := max(N, cumulative found);
  remaining = max(0, N − cumulative); quota bindings pass iff the LAST round's findings
  exceeded the territory count — evidence of ongoing discovery decides, not a depleting size
  guess. Plan reviews seed N = ceil(13 x plan_lines/1000) when the line count is known, else
  0; code review runs round 1 quota-free then seeds N = 2 x F1 (a seed the upward rule
  immediately overrides when reality outruns it). Least-squares ratchet deleted; the
  nonconvergence review remains the backstop for false convergence.
- 13/kline is now a SEED only — uncheckable against the expanded dataset (historical plan
  line counts weren't recorded); live runs now log the plan line count in the run record, so
  the seed becomes checkable as records accumulate.
- Literature caveat (LLM anchoring): numeric anchors in prompts inflate REPORTED counts more
  reliably than they increase genuine discovery. This reinforces two shipped choices: anchor
  conservatively at the floor (quotas are minimums derived from evidence, never stretch
  goals) and OMIT the quota entirely rather than floor it when last-round findings fall to
  territory count or below.

### No measurable effect (lesson: fix the right layer)

- **Category-2 bar at the plan editor**: the editor was already robust to preference pressure —
  it never produced a preference-driven REVISED in any tested round. The reviewers, not the
  decider, were the round-amplifier. Measure each layer separately before "fixing" it.
- **Category-2 bar at post-impl review + merge**: parity on a converged run (would-block 0/25
  in BOTH arms; merge 5/5 both). The corpus lacked the failure the change targets. **Held, not
  deployed.** Needs a real run where code review blocks on preference; replay that round when
  one appears.
- **Fix-the-class + blast-radius passage at the plan editor**: INERT. 0/6 named late siblings
  closed in all 10 trials, both arms — identical to the real editor. The editor is structurally
  bounded to the findings list ("fix every critical issue" + per-edit proof burden); two
  exhortative bullets don't overcome that. Not harmful (fix completeness unchanged, no overreach),
  not shipped. Byproduct finding: editor-INTRODUCED defects are systemic — ~3–4 grader-flagged
  introductions per edit pass in both arms AND in blind looks at the real diff (the known real
  introduction was flagged 10/10 blind). Round-N+1 reviewers are the working control for these;
  the dynamic quota front-loads them.

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
7. **Static defect quotas beyond round 1.** A fixed 9-critical/6-critical demand saturates once real
   defects thin out: criticals anchor BELOW the floor while severity inflation triples (3→10.7/15 at
   L2 on r1; inflation 12, unmatched-outcome 28 for static-on-r2). The model relabels and fabricates
   instead of discovering. Recalibrate every round from remaining = estimate − fixed-so-far.
8. **Quota floors on near-clean rounds.** Even "at least 1 defect / 1 critical" degraded a genuinely
   clean round (FA cells 2/25→3/25, CLEAN verdicts 23/25→21/25 — failed its pre-registered gate);
   static 45/9/6 on the same clean bed produced 13 critical-tier fabrications (4× baseline) and 19/25
   CLEAN. When remaining ≤ territory count, OMIT the quota entirely; never floor it.

### Shipped on review only — live checkpoint pending

- **Combined approvals** (one approval at the strategy gate carrying a binding validation
  forecast; test plan re-asks only on material deviation incl. dropped validation; autonomy
  relocates the approval, never removes it). Not replay-testable — no past data exercises an
  approval flow. **Checkpoint: the next real run must ask exactly once.** A second ask for
  already-forecast ground, or a mid-run probe permission covered by the forecast, is a defect —
  archive that run as the fix's corpus.

## Open targets (in expected-value order)

1. **Blast-radius post-edit self-check** as its own single-variable experiment (a separate
   verification pass after edits, not exhortation bundled into the edit prompt — the
   fix-the-class bundling is disproven). Editor-introduced defects (~3–4/pass) are the target.
2. **Live checkpoints pending**: (a) combined approvals — the next real run must ask exactly
   once; a second ask for already-forecast ground is a defect, archive that run as the fix's
   corpus; (b) quota-active post-impl round — first defect-dense live verification round
   exercises the untested `{{#if QUOTA_TOTAL}}` rendering on the current template.
3. **Initial-estimate calibration**: 13 defects per 1,000 plan/changed lines comes from ONE
   corpus (memo-relay). Recalibrate as run records accumulate; the formula tolerates error at
   round 1 (saturation only bites when demanded count exceeds true remaining), but a
   materially wrong estimate delays the omit switchover.

## Operational facts

- Tuning workspace convention: `~/.amplifier/evaluation/trycycle/` — `corpus/` (archived run
  stagings), `replay/` (harness + frozen snapshots + rewritten prompts), `replay/runs/<id>/`
  (per-run raw replies, grades, summary.md). Corpora and results never live in this repo.
- Costs (claude-class model, 6–8 parallel): ~350–520s per replayed query; 150-trial A/B ≈ 2h;
  30-trial editor A/B ≈ 1h; grading ~1–4s/trial amortized. Snapshot construction: minutes.
- Deploy procedure: AGENTS.md "Local test deployment". Revert in an install:
  `git checkout -- <files>` in that clone.
