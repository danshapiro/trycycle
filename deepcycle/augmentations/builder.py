from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from PIL import Image


@dataclass(frozen=True)
class TransformBundle:
    train: Callable[[Image.Image], object]
    eval: Callable[[Image.Image], object]


def build_classification_transforms(cfg: dict[str, Any]) -> TransformBundle:
    """
    Minimal, dependency-light augmentation pipeline.

    Uses torchvision transforms if available (recommended), otherwise falls back
    to a tiny PIL-based pipeline.
    """
    aug = (cfg.get("augmentations") or {}).get("classification") or {}
    image_size = int(aug.get("image_size", 224))

    try:
        import torchvision.transforms as T

        train_tf = T.Compose(
            [
                T.RandomResizedCrop(image_size, scale=(float(aug.get("rrc_min_scale", 0.7)), 1.0)),
                T.RandomHorizontalFlip(p=float(aug.get("hflip_p", 0.5))),
                T.ColorJitter(
                    brightness=float(aug.get("brightness", 0.2)),
                    contrast=float(aug.get("contrast", 0.2)),
                    saturation=float(aug.get("saturation", 0.2)),
                    hue=float(aug.get("hue", 0.05)),
                )
                if bool(aug.get("color_jitter", True))
                else _identity(),
                T.ToTensor(),
            ]
        )

        eval_tf = T.Compose(
            [
                T.Resize(int(aug.get("eval_resize", 256))),
                T.CenterCrop(image_size),
                T.ToTensor(),
            ]
        )

        return TransformBundle(train=_strip_identities(train_tf), eval=eval_tf)
    except Exception:
        # Pillow-only fallback; returns torch tensors if torch is present, else numpy arrays.
        return TransformBundle(
            train=_pil_train_fallback(image_size=image_size, hflip_p=float(aug.get("hflip_p", 0.5))),
            eval=_pil_eval_fallback(image_size=image_size),
        )


def _identity():
    return lambda x: x


def _strip_identities(compose):
    # torchvision Compose can contain lambdas; keep as-is.
    return compose


def _pil_train_fallback(*, image_size: int, hflip_p: float):
    import random

    def tf(img: Image.Image):
        img2 = img.convert("RGB")
        img2 = img2.resize((image_size, image_size))
        if random.random() < hflip_p:
            img2 = img2.transpose(Image.FLIP_LEFT_RIGHT)
        return _pil_to_tensor(img2)

    return tf


def _pil_eval_fallback(*, image_size: int):
    def tf(img: Image.Image):
        img2 = img.convert("RGB")
        img2 = img2.resize((image_size, image_size))
        return _pil_to_tensor(img2)

    return tf


def _pil_to_tensor(img: Image.Image):
    import numpy as np

    arr = (np.asarray(img, dtype=np.float32) / 255.0).transpose((2, 0, 1))
    try:
        import torch

        return torch.from_numpy(arr)
    except Exception:
        return arr
