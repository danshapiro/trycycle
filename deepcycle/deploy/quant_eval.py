from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def evaluate_quantized_variants(*, config_path: Path, run_dir: Path) -> None:
    """
    Evaluate quantized exported variants (when present) and report accuracy drop vs baseline eval.

    Current behavior:
    - If `deploy/model.dynamic_int8.ts` exists, evaluate it on the same test set.
    - Compare against `eval/metrics.json` if present, else evaluate the fp32 checkpoint model.
    """
    _require_torch()
    import torch
    from torch.utils.data import DataLoader

    from deepcycle.augmentations.builder import build_classification_transforms
    from deepcycle.data.h5_dataset import H5ClassificationDataset
    from deepcycle.data.multi_h5 import MultiH5ClassificationDataset
    from deepcycle.utils.config import load_yaml

    cfg = load_yaml(config_path)
    if str(cfg["task"]) != "classification":
        raise NotImplementedError("Quantized evaluation currently supports classification targets only.")

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

    loader = DataLoader(test_ds, batch_size=int(cfg.get("eval", {}).get("batch_size", 64)), shuffle=False)

    deploy_dir = run_dir / "deploy"
    dyn_path = deploy_dir / "model.dynamic_int8.ts"
    static_path = deploy_dir / "model.static_int8.ts"

    results: dict[str, Any] = {"variants": {}}

    baseline_metrics_path = run_dir / "eval" / "metrics.json"
    if baseline_metrics_path.exists():
        baseline = json.loads(baseline_metrics_path.read_text(encoding="utf-8"))
        results["baseline"] = {"source": "eval/metrics.json", "top1_acc": float(baseline.get("top1_acc", 0.0))}
    else:
        results["baseline"] = {"source": "missing_eval_metrics", "top1_acc": None}

    if dyn_path.exists():
        qmodel = torch.jit.load(str(dyn_path), map_location="cpu")
        qmodel.eval()
        qacc = _acc(qmodel, loader)
        results["variants"]["dynamic_int8_torchscript"] = {"path": str(dyn_path.name), "top1_acc": float(qacc)}
    else:
        results["variants"]["dynamic_int8_torchscript"] = {"status": "missing"}

    if static_path.exists():
        smodel = torch.jit.load(str(static_path), map_location="cpu")
        smodel.eval()
        sacc = _acc(smodel, loader)
        results["variants"]["static_int8_torchscript"] = {"path": str(static_path.name), "top1_acc": float(sacc)}
    else:
        results["variants"]["static_int8_torchscript"] = {"status": "missing"}

    # compute drops
    base_acc = results["baseline"].get("top1_acc")
    if base_acc is not None:
        for v in results["variants"].values():
            if "top1_acc" in v:
                v["acc_drop"] = float(base_acc) - float(v["top1_acc"])

    (deploy_dir / "quant_eval.json").write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
    (deploy_dir / "quant_report.md").write_text(_render_report(results), encoding="utf-8")


def _acc(model, loader) -> float:
    import torch

    correct = 0
    total = 0
    with torch.no_grad():
        for xb, yb in loader:
            logits = model(xb)
            pred = torch.argmax(logits, dim=1)
            correct += int((pred == yb).sum().item())
            total += int(yb.numel())
    return float(correct / max(1, total))


def _render_report(results: dict[str, Any]) -> str:
    lines = []
    lines.append("# Quantization evaluation report")
    lines.append("")
    base = results.get("baseline") or {}
    lines.append(f"- **baseline_source**: `{base.get('source')}`")
    if base.get("top1_acc") is not None:
        lines.append(f"- **baseline_top1_acc**: **{float(base['top1_acc']):.4f}**")
    lines.append("")
    lines.append("## Variants")
    lines.append("")
    for name, v in (results.get("variants") or {}).items():
        if v.get("status") == "missing":
            lines.append(f"- `{name}`: missing")
            continue
        line = f"- `{name}`: top1_acc={float(v['top1_acc']):.4f}"
        if v.get("acc_drop") is not None:
            line += f", acc_drop={float(v['acc_drop']):.4f}"
        lines.append(line)
    lines.append("")
    return "\n".join(lines)


def _require_torch() -> None:
    try:
        import torch  # noqa: F401
    except Exception as e:  # pragma: no cover
        raise RuntimeError("PyTorch is required. Install with `pip install -e '.[torch]'`.") from e

