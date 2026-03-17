from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from deepcycle.utils.config import load_yaml


def run_attack(*, mode: str, config_path: Path, checkpoint_path: Path, run_dir: Path) -> None:
    _require_torch()
    import torch
    from torch.utils.data import DataLoader

    from deepcycle.attack.attacks import AttackConfig, fgsm, pgd
    from deepcycle.data.h5_dataset import H5ClassificationDataset
    from deepcycle.data.multi_h5 import MultiH5ClassificationDataset
    from deepcycle.augmentations.builder import build_classification_transforms
    from deepcycle.models.vision import build_classification_model

    cfg = load_yaml(config_path)
    task = str(cfg["task"])
    if task != "classification":
        raise NotImplementedError("Adversarial task currently supports classification targets only.")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
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
        train_ds = MultiH5ClassificationDataset(
            dataset_dirs,
            split="train",
            transform=tfs.train,
            weights=cfg.get("dataset_weights"),
        )
    else:
        dataset_dir = Path(cfg["dataset_dir"])
        test_ds = H5ClassificationDataset(dataset_dir / "dataset-test.h5", transform=tfs.eval)
        train_ds = H5ClassificationDataset(dataset_dir / "dataset-train.h5", transform=tfs.train)
    loader = DataLoader(test_ds, batch_size=int(cfg.get("eval", {}).get("batch_size", 64)), shuffle=False)

    num_classes = int(cfg.get("model", {}).get("num_classes", int(np.max(test_ds.labels) + 1)))
    model = build_classification_model(cfg.get("model", {}), num_classes=num_classes).to(device)
    ckpt = torch.load(checkpoint_path, map_location="cpu")
    state = ckpt["model"] if isinstance(ckpt, dict) and "model" in ckpt else ckpt
    model.load_state_dict(state, strict=True)
    model.eval()

    attack_cfg = cfg.get("attack", {}) or {}
    eps = float(attack_cfg.get("eps", 8 / 255))
    pgd_cfg = AttackConfig(
        eps=eps,
        steps=int(attack_cfg.get("pgd_steps", 10)),
        step_size=float(attack_cfg.get("pgd_step_size", 2 / 255)),
        norm=str(attack_cfg.get("norm", "linf")),
    )

    attack_dir = run_dir / "attack"
    attack_dir.mkdir(parents=True, exist_ok=True)

    results: dict[str, Any] = {"task": "adversarial_attack", "target_task": task, "eps": eps}

    if mode in {"eval", "both"}:
        results["clean_top1"] = _acc(model, loader, device)
        results["fgsm_top1"] = _acc_adv(model, loader, device, lambda x, y: fgsm(model=model, x=x, y=y, eps=eps))
        results["pgd_top1"] = _acc_adv(model, loader, device, lambda x, y: pgd(model=model, x=x, y=y, cfg=pgd_cfg))

    if mode in {"train_attack_model", "both"}:
       results["attack_model_training"] = _train_uap_generator(
           model=model,
           train_ds=train_ds,
           device=device,
           eps=eps,
           cfg=cfg.get("attack", {}) or {},
           out_dir=attack_dir,
       )

    (attack_dir / "metrics.json").write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
    (attack_dir / "report.md").write_text(_render_attack_report(results), encoding="utf-8")


def _acc(model, loader, device) -> float:
    import torch

    correct = 0
    total = 0
    with torch.no_grad():
        for xb, yb in loader:
            xb = xb.to(device)
            yb = yb.to(device)
            pred = torch.argmax(model(xb), dim=1)
            correct += int((pred == yb).sum().item())
            total += int(yb.numel())
    return float(correct / max(1, total))


def _acc_adv(model, loader, device, make_adv) -> float:
    import torch

    correct = 0
    total = 0
    for xb, yb in loader:
        xb = xb.to(device)
        yb = yb.to(device)
        xb_adv = make_adv(xb, yb).to(device)
        with torch.no_grad():
            pred = torch.argmax(model(xb_adv), dim=1)
        correct += int((pred == yb).sum().item())
        total += int(yb.numel())
    return float(correct / max(1, total))


def _render_attack_report(m: dict[str, Any]) -> str:
    lines = []
    lines.append("# Adversarial attack report")
    lines.append("")
    lines.append(f"- **target_task**: `{m.get('target_task')}`")
    lines.append(f"- **eps**: {m.get('eps')}")
    if "clean_top1" in m:
        lines.append(f"- **clean_top1**: **{float(m['clean_top1']):.4f}**")
        lines.append(f"- **fgsm_top1**: **{float(m['fgsm_top1']):.4f}**")
        lines.append(f"- **pgd_top1**: **{float(m['pgd_top1']):.4f}**")
    lines.append("")
    if isinstance(m.get("attack_model_training"), dict):
        lines.append("## Attack-network training")
        lines.append("")
        lines.append(f"- **status**: `{m['attack_model_training'].get('status')}`")
        lines.append("")
    return "\n".join(lines)


def _train_uap_generator(*, model, train_ds, device, eps: float, cfg: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    import torch
    import torch.nn.functional as F
    from torch.utils.data import DataLoader

    batch_size = int(cfg.get("train_batch_size", 64))
    steps = int(cfg.get("train_steps", 200))
    lr = float(cfg.get("train_lr", 1e-3))

    loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    gen = UAPGenerator().to(device)
    opt = torch.optim.AdamW(gen.parameters(), lr=lr)

    model.eval()
    gen.train()

    step = 0
    it = iter(loader)
    while step < steps:
        try:
            xb, yb = next(it)
        except StopIteration:
            it = iter(loader)
            xb, yb = next(it)

        xb = xb.to(device)
        yb = yb.to(device)

        # Generator outputs perturbation; project to eps-ball.
        delta = gen(xb)
        delta = torch.clamp(delta, -eps, eps)
        xb_adv = torch.clamp(xb + delta, 0.0, 1.0)

        logits = model(xb_adv)
        loss = -F.cross_entropy(logits, yb)  # maximize target loss

        opt.zero_grad(set_to_none=True)
        loss.backward()
        opt.step()

        step += 1

    # Save generator checkpoint
    gen_path = out_dir / "uap_generator.pt"
    torch.save({"model": gen.state_dict(), "eps": eps, "steps": steps}, gen_path)

    return {"status": "ok", "artifact": str(gen_path.name), "steps": steps, "train_lr": lr}


def _require_torch() -> None:
    try:
        import torch  # noqa: F401
    except Exception as e:  # pragma: no cover
        raise RuntimeError("PyTorch is required. Install with `pip install -e '.[torch]'`.") from e
