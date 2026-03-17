from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from deepcycle.utils.config import load_yaml


def run_evaluation(*, config_path: Path, checkpoint_path: Path, run_dir: Path) -> None:
    _require_torch()
    import torch
    from torch.utils.data import DataLoader

    from deepcycle.augmentations.builder import build_classification_transforms
    from deepcycle.data.h5_dataset import H5ClassificationDataset
    from deepcycle.data.multi_h5 import MultiH5ClassificationDataset
    from deepcycle.models.vision import build_classification_model

    cfg = load_yaml(config_path)
    task = str(cfg["task"])
    if task != "classification":
        raise NotImplementedError("Only task=classification is runnable in this initial implementation.")

    tfs = build_classification_transforms(cfg)
    dataset_dirs = cfg.get("dataset_dirs")
    if dataset_dirs:
        dataset_dirs = [Path(p) for p in dataset_dirs]
        test_ds = MultiH5ClassificationDataset(
            dataset_dirs,
            split="test",
            transform=tfs.eval,
            weights=cfg.get("dataset_weights"),
        )
    else:
        dataset_dir = Path(cfg["dataset_dir"])
        test_ds = H5ClassificationDataset(dataset_dir / "dataset-test.h5", transform=tfs.eval)
    test_loader = DataLoader(test_ds, batch_size=int(cfg.get("eval", {}).get("batch_size", 64)), shuffle=False)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    num_classes = int(cfg.get("model", {}).get("num_classes", int(np.max(test_ds.labels) + 1)))
    model = build_classification_model(cfg.get("model", {}), num_classes=num_classes).to(device)

    ckpt = torch.load(checkpoint_path, map_location="cpu")
    state = ckpt["model"] if isinstance(ckpt, dict) and "model" in ckpt else ckpt
    model.load_state_dict(state, strict=True)
    model.eval()

    correct = 0
    total = 0
    per_class_correct: dict[int, int] = {}
    per_class_total: dict[int, int] = {}

    with torch.no_grad():
        for xb, yb in test_loader:
            xb = xb.to(device)
            yb = yb.to(device)
            logits = model(xb)
            pred = torch.argmax(logits, dim=1)
            correct_mask = (pred == yb)
            correct += int(correct_mask.sum().item())
            total += int(yb.numel())

            for y, ok in zip(yb.detach().cpu().tolist(), correct_mask.detach().cpu().tolist()):
                per_class_total[y] = per_class_total.get(y, 0) + 1
                if ok:
                    per_class_correct[y] = per_class_correct.get(y, 0) + 1

    metrics: dict[str, Any] = {
        "task": task,
        "top1_acc": float(correct / max(1, total)),
        "n_test": int(total),
        "per_class_acc": {
            str(k): float(per_class_correct.get(k, 0) / max(1, per_class_total.get(k, 0)))
            for k in sorted(per_class_total.keys())
        },
    }

    eval_dir = run_dir / "eval"
    eval_dir.mkdir(parents=True, exist_ok=True)
    (eval_dir / "metrics.json").write_text(json.dumps(metrics, indent=2, sort_keys=True), encoding="utf-8")
    (eval_dir / "report.md").write_text(_render_report(metrics), encoding="utf-8")
    _maybe_write_per_class_plot(eval_dir, metrics)


def _render_report(metrics: dict[str, Any]) -> str:
    lines = []
    lines.append("# Evaluation report")
    lines.append("")
    lines.append(f"- **task**: `{metrics['task']}`")
    lines.append(f"- **top1_acc**: **{metrics['top1_acc']:.4f}**")
    lines.append(f"- **n_test**: {metrics['n_test']}")
    lines.append("")
    lines.append("## Per-class accuracy")
    lines.append("")
    for k, v in (metrics.get("per_class_acc") or {}).items():
        lines.append(f"- class `{k}`: {float(v):.4f}")
    lines.append("")
    return "\n".join(lines)


def _maybe_write_per_class_plot(eval_dir: Path, metrics: dict[str, Any]) -> None:
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return

    per_class = metrics.get("per_class_acc") or {}
    if not per_class:
        return

    keys = list(per_class.keys())
    vals = [float(per_class[k]) for k in keys]

    plt.figure(figsize=(max(6, len(keys) * 0.4), 3))
    plt.bar(keys, vals)
    plt.ylim(0, 1)
    plt.xlabel("class")
    plt.ylabel("accuracy")
    plt.title(f"Per-class accuracy (top1={float(metrics.get('top1_acc', 0.0)):.4f})")
    plt.tight_layout()
    plt.savefig(eval_dir / "per_class_accuracy.png", dpi=150)
    plt.close()


def _require_torch() -> None:
    try:
        import torch  # noqa: F401
    except Exception as e:  # pragma: no cover
        raise RuntimeError("PyTorch is required. Install with `pip install -e '.[torch]'`.") from e
