from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from deepcycle.data.h5_dataset import H5ClassificationDataset


@dataclass
class MultiH5ClassificationDataset:
    dataset_dirs: list[Path]
    split: str  # train/val/test
    transform: object | None = None
    weights: list[float] | None = None

    def __post_init__(self) -> None:
        if self.split not in {"train", "val", "test"}:
            raise ValueError(f"Unknown split: {self.split}")
        self._datasets: list[H5ClassificationDataset] = []
        for d in self.dataset_dirs:
            path = d / f"dataset-{self.split}.h5"
            self._datasets.append(H5ClassificationDataset(path, transform=self.transform))

        self._offsets = np.cumsum([0] + [len(ds) for ds in self._datasets])
        self.labels = np.concatenate([ds.labels for ds in self._datasets]) if self._datasets else np.array([], dtype=np.int64)

    def __len__(self) -> int:
        return int(self._offsets[-1])

    def __getitem__(self, idx: int):
        # Locate dataset by offsets.
        ds_i = int(np.searchsorted(self._offsets, idx, side="right") - 1)
        local = int(idx - self._offsets[ds_i])
        return self._datasets[ds_i][local]

