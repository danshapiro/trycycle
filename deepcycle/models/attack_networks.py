from __future__ import annotations

import torch
import torch.nn as nn


class UAPGenerator(nn.Module):
    """
    A tiny universal perturbation generator.

    Generates a single image-shaped perturbation (broadcastable) constrained
    by an epsilon bound in attack training loops.
    """

    def __init__(self, channels: int = 3, hidden: int = 64):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(channels, hidden, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(hidden, hidden, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(hidden, channels, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B,C,H,W) -> perturbation (B,C,H,W)
        return self.net(x)

