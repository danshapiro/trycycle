---
name: trycycle-proving
description: "Internal trycycle subskill — do not invoke directly."
---

# Proving Claims

## Overview

How to prove a claim before anything relies on it. Use this whenever you are about to depend on something unproven — a library capability, framework behavior, an external service, a tool, an API, a schema or data shape, a performance characteristic, or a mechanism you devised yourself.

Written testimony is not proof. A claim is proven when you hold evidence gathered from reality, and it stays proven only if a fresh agent can re-check it cheaply.

## The Ladder

Climb to the cheapest rung that settles the claim, and stop there:

1. **Read the real thing.** The installed package's source, the version actually present, the actual schema, the existing code path, the docs shipped with the workspace's dependencies.
2. **Run the real thing.** Safe read-only probes, existing tests, local commands that exercise the actual behavior in question.
3. **Build a throwaway experiment.** A minimal spike that exercises exactly the doubted behavior against the real dependencies present in the workspace.
4. **Research credible sources.** Official docs, the project's own repository and issue tracker, proven patterns in comparable open source projects. This is the weakest rung — use it to corroborate, not to substitute for the rungs above when they are available.

When more than one approach could work, compare candidates, then prove the one you choose.

## Throwaway Experiments

- Build them in scratch space, never inside the deliverable, and never commit them.
- Exercise the exact doubted behavior. The closer the experiment is to the real usage, the more the result is worth.
- Delete the experiment when done. What survives is the residue: one precise claim, plus how anyone can re-verify it cheaply — the command to run, the code path to read, the artifact to inspect.

## Rules

- **Prove before you write.** Writing an unproven mechanism into a deliverable does not settle a question; it relocates the defect downstream to whoever relies on it.
- **Record claims precisely enough to falsify.** "The API supports batching" is not checkable; "`POST /v2/items` accepts up to 100 items per request, probed with the command below" is.
- **Never write down evidence you did not gather.** No invented command output, versions, or behavior.
- **Stop only at a hard wall.** Give up on proving a claim only when the decisive evidence physically requires something you cannot obtain — a secret, paid access, authority, or an environment you do not have. Then escalate as your instructions direct instead of guessing.
