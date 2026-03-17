from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AttackConfig:
    eps: float = 8 / 255
    steps: int = 10
    step_size: float = 2 / 255
    norm: str = "linf"  # "linf" or "l2" (l2 not implemented yet)


def fgsm(*, model, x, y, eps: float):
    import torch
    import torch.nn.functional as F

    x_adv = x.detach().clone().requires_grad_(True)
    logits = model(x_adv)
    loss = F.cross_entropy(logits, y)
    grad = torch.autograd.grad(loss, x_adv)[0]
    x_adv = x_adv + eps * grad.sign()
    return torch.clamp(x_adv.detach(), 0.0, 1.0)


def pgd(*, model, x, y, cfg: AttackConfig):
    import torch
    import torch.nn.functional as F

    if cfg.norm != "linf":
        raise NotImplementedError("Only Linf PGD is implemented.")

    x0 = x.detach()
    x_adv = x0 + torch.empty_like(x0).uniform_(-cfg.eps, cfg.eps)
    x_adv = torch.clamp(x_adv, 0.0, 1.0)

    for _ in range(int(cfg.steps)):
        x_adv.requires_grad_(True)
        logits = model(x_adv)
        loss = F.cross_entropy(logits, y)
        grad = torch.autograd.grad(loss, x_adv)[0]
        x_adv = x_adv.detach() + float(cfg.step_size) * grad.sign()
        x_adv = torch.max(torch.min(x_adv, x0 + cfg.eps), x0 - cfg.eps)
        x_adv = torch.clamp(x_adv, 0.0, 1.0)

    return x_adv.detach()
