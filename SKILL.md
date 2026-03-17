---
name: deepcycle
description: Invoke deepcycle only when the user requests it by name.
---

# Deepcycle

Use this skill only when the user requests `deepcycle` to develop, evaluate, attack, and/or deploy deep learning models. You must follow this skill; if for some reason that becomes impossible, stop and tell the user.

The user's instructions are paramount. If anything in this skill conflicts with the user's instructions, follow the user.

## What Deepcycle does

Deepcycle is a **computer-vision deep learning development skill**. It helps you:

- define **datasets** and **split policy**
- define **augmentations**, **architectures**, **losses**, and **training strategy**
- preprocess datasets into **HDF5 integrity splits** (`dataset-{train,val,test}.h5` + `metadata.json`)
- run **train**, **eval**, **adversarial** (FGSM/PGD + learned UAP generator), and **deploy** (TorchScript/ONNX + quantization) workflows
- generate **reports** and a **research roadmap** from evaluation artifacts

This repo contains the Deepcycle CLI implementation (`deepcycle ...`). The skill is the **operating procedure**: ask the right questions, then run the right commands and produce artifacts.

## 0) Version check

Run:

```bash
python3 <skill-directory>/check-update.py
```

If an update is available, ask the user whether to update before continuing.

## 1) Ask critical unknowns (only what blocks execution)

If missing, ask for:

- **task type(s)**: classification / detection / segmentation / adversarial
- **dataset source(s)** and label format(s): folder-per-class, COCO, YOLO, VOC, mask PNGs, or custom adapter
- **split policy**: official splits vs fallback ratio (80/10/10 or 70/15/15)
- **hardware constraints**: CPU-only vs single GPU
- **success metrics**: e.g., top-1 accuracy / mAP / mIoU and which robustness metrics are required

Do not ask more questions than needed to run safely.

## 2) Define the deep-oriented plan (deliverables + artifacts)

Produce a plan that explicitly defines:
- dataset spec(s) and split policy
- augmentation policy (train-only vs eval)
- model architecture(s) (baseline + fine-tuning strategy)
- losses + training loop strategy
- evaluation reports (clean + adversarial where applicable)
- deployment export targets + quantization expectations and how accuracy drops will be measured
- research roadmap generation from evaluation artifacts

Prefer reproducible, config-driven runs with versioned artifacts under `runs/<run_id>/...`.

## 3) Execute the pipeline (CLI)

Run the Deepcycle CLI in this order (skip steps the user didn’t request):

```bash
# Preprocess raw datasets -> HDF5 splits + metadata
deepcycle data:prepare --dataset <spec.yaml> --out-dir <dataset_dir>

# Train
deepcycle train --config <train.yaml> --run-dir runs/<run_id>

# Evaluate (writes runs/<run_id>/eval/*)
deepcycle eval --config runs/<run_id>/config.yaml --checkpoint runs/<run_id>/checkpoints/best.pt --run-dir runs/<run_id>

# Adversarial (writes runs/<run_id>/attack/*)
deepcycle attack --mode both --config runs/<run_id>/config.yaml --checkpoint runs/<run_id>/checkpoints/best.pt --run-dir runs/<run_id>

# Deploy (writes runs/<run_id>/deploy/*; optionally quant-eval)
deepcycle deploy --config runs/<run_id>/config.yaml --checkpoint runs/<run_id>/checkpoints/best.pt --run-dir runs/<run_id> --quantize <none|dynamic|static> --eval-quantized

# Aggregate reports + update roadmap
deepcycle report --runs-dir runs --out docs/summary.md
deepcycle research --runs-dir runs --out docs/roadmap.md
```

## 4) Output expectations

Ensure the user gets concrete artifacts, not just prose:
- `runs/<run_id>/eval/metrics.json` + `report.md`
- `runs/<run_id>/attack/metrics.json` + `report.md`
- `runs/<run_id>/deploy/*` + `quant_report.md` when quantization is used
- `docs/summary.md` and `docs/roadmap.md` for iteration

