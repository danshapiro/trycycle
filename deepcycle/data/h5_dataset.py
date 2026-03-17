from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import h5py
import numpy as np
from PIL import Image


@dataclass
class H5ClassificationDataset:
    path: Path
    transform: object | None = None

    def __post_init__(self) -> None:
        self._f = h5py.File(self.path, "r")
        self._img = self._f["image_bytes"]
        self._y = self._f["y"]
        self.labels = np.array(self._y[:], dtype=np.int64)

    def __len__(self) -> int:
        return int(self._y.shape[0])

    def __getitem__(self, idx: int):
        img_bytes = bytes(np.array(self._img[idx], dtype=np.uint8).tobytes())
        img = Image.open(BytesIO(img_bytes)).convert("RGB")
        if self.transform is not None:
            x = self.transform(img)
        else:
            x = _to_tensor(img)
        y = int(self._y[idx])
        return x, y


def _to_tensor(img: Image.Image):
    import torch

    arr = np.asarray(img, dtype=np.float32) / 255.0
    # HWC -> CHW
    arr = np.transpose(arr, (2, 0, 1))
    return torch.from_numpy(arr)
