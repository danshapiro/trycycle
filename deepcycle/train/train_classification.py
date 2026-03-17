from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np


def train_classification(*, cfg: dict[str, Any], run_dir: Path) -> None:
    _require_torch()
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader

    from deepcycle.augmentations.builder import build_classification_transforms
    from deepcycle.data.h5_dataset import H5ClassificationDataset
    from deepcycle.data.multi_h5 import MultiH5ClassificationDataset
    from deepcycle.models.vision import build_classification_model

    tfs = build_classification_transforms(cfg)

    dataset_dirs = cfg.get("dataset_dirs")
    if dataset_dirs:
        dataset_dirs = [Path(p) for p in dataset_dirs]
        weights = cfg.get("dataset_weights")
        train_ds = MultiH5ClassificationDataset(dataset_dirs, split="train", transform=tfs.train, weights=weights)
        val_ds = MultiH5ClassificationDataset(dataset_dirs, split="val", transform=tfs.eval, weights=weights)
    else:
        dataset_dir = Path(cfg["dataset_dir"])
        train_ds = H5ClassificationDataset(dataset_dir / "dataset-train.h5", transform=tfs.train)
        val_ds = H5ClassificationDataset(dataset_dir / "dataset-val.h5", transform=tfs.eval)

    batch_size = int(cfg.get("train", {}).get("batch_size", 32))
    num_workers = int(cfg.get("train", {}).get("num_workers", 2))
    epochs = int(cfg.get("train", {}).get("epochs", 1))
    lr = float(cfg.get("train", {}).get("lr", 1e-3))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    num_classes = int(cfg.get("model", {}).get("num_classes", int(np.max(train_ds.labels) + 1)))
    model = build_classification_model(cfg.get("model", {}), num_classes=num_classes).to(device)

    criterion = nn.CrossEntropyLoss()
    optimizer = optim.AdamW(model.parameters(), lr=lr)

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=num_workers)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=num_workers)

    best_acc = -1.0
    ckpt_path = run_dir / "checkpoints"
    ckpt_path.mkdir(parents=True, exist_ok=True)

    for epoch in range(1, epochs + 1):
        model.train()
        train_loss = 0.0
        for xb, yb in train_loader:
            xb = xb.to(device)
            yb = yb.to(device)
            optimizer.zero_grad(set_to_none=True)
            logits = model(xb)
            loss = criterion(logits, yb)
            loss.backward()
            optimizer.step()
            train_loss += float(loss.detach().cpu())

        val_acc = _eval_acc(model, val_loader, device)
        metrics = {"epoch": epoch, "train_loss": train_loss / max(1, len(train_loader)), "val_acc": val_acc}
        (run_dir / "train_metrics.jsonl").open("a", encoding="utf-8").write(json.dumps(metrics) + "\n")

        if val_acc > best_acc:
            best_acc = val_acc
            torch.save({"model": model.state_dict(), "epoch": epoch, "val_acc": val_acc}, ckpt_path / "best.pt")


def _eval_acc(model, loader, device) -> float:
    import torch

    model.eval()
    correct = 0
    total = 0
    with torch.no_grad():
        for xb, yb in loader:
            xb = xb.to(device)
            yb = yb.to(device)
            logits = model(xb)
            pred = torch.argmax(logits, dim=1)
            correct += int((pred == yb).sum().item())
            total += int(yb.numel())
    return float(correct / max(1, total))


def _require_torch() -> None:
    try:
        import torch  # noqa: F401
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "PyTorch is required. Install with `pip install -e '.[torch]'` (or install torch/torchvision manually)."
        ) from e
