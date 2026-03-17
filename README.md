<!-- GitHub repo settings (set manually in Settings > General):
  Description: A skill that builds, evaluates, attacks, and deploys deep learning models — automatically.
  Topics: claude-code, codex-cli, deep-learning, computer-vision, adversarial-ml, ai-skill
-->

## Deepcycle

A **skill** for coding agents (Claude Code, Codex CLI, etc.) that helps you **develop computer vision deep-learning models** end-to-end:

- **Datasets**: preprocess to integrity-preserving HDF5 splits (`dataset-{train,val,test}.h5` + `metadata.json`)
- **Training**: PyTorch-first runners (Lightning optional later)
- **Evaluation**: test-set execution + report bundles (metrics + optional plots)
- **Adversarial**: robustness evaluation (FGSM/PGD) + learned attack model training (UAP generator)
- **Deployment**: export/freeze + quantize (dynamic + static PTQ) + quantify accuracy drops
- **Research**: roadmap generation driven by evaluation artifacts

Designed for both:
- **Greenfield** projects, and
- **Optimizing existing GitHub repos** (brownfield).

---

## Installing Deepcycle

### If you are human

Tell your favorite coding agent:

```
Read the README in this repo and follow the installation instructions. Then use the Deepcycle skill in your requests.
```

### If you've been sent here by your human

Use this instead of a standard install. Clone into your skills directory:

- **Claude Code:** `git clone <THIS_REPO_URL> ~/.claude/skills/deepcycle`
- **Codex CLI:** `git clone <THIS_REPO_URL> ~/.codex/skills/deepcycle`
 
Replace `<THIS_REPO_URL>` with: `https://github.com/aborzin/deepcycle.git`

Deepcycle requires `python3` at runtime. Make sure it is installed and on your `PATH`.

---

## Using Deepcycle

Include the word Deepcycle in your request and describe what you want built or improved:

```
Use deepcycle to train and evaluate a ResNet50 classifier on my dataset, run FGSM/PGD robustness evaluation, then export a quantized deployment model and report the accuracy drop.
```

Deepcycle will (a) define dataset preprocessing/splits and augmentations, (b) run training/evaluation/attacks/deployment steps, and (c) produce report artifacts you can compare across runs.

---

## Developer CLI (implementation detail)

When you (or the agent) need to run the underlying pipeline directly, use the CLI:

- `deepcycle data:prepare`
- `deepcycle train`
- `deepcycle eval`
- `deepcycle attack`
- `deepcycle deploy`
- `deepcycle report`
- `deepcycle research`

