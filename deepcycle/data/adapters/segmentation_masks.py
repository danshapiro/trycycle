from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from deepcycle.data.registry import DatasetSpec


_IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


@dataclass(frozen=True)
class SegmentationMasksAdapter:
    spec: DatasetSpec

    def iter_samples(self) -> Iterable[dict[str, Any]]:
        # Expected spec.extra:
        # - images_dir (default spec.root/images)
        # - masks_dir (default spec.root/masks)
        extra = self.spec.extra or {}

        if self.spec.official_splits:
            yield from self._iter_official_splits()
            return

        images_dir = Path(extra.get("images_dir", self.spec.root / "images")).expanduser()
        masks_dir = Path(extra.get("masks_dir", self.spec.root / "masks")).expanduser()
        yield from self._iter_pair(images_dir, masks_dir, split=None)

    def _iter_official_splits(self) -> Iterable[dict[str, Any]]:
        extra = self.spec.extra or {}
        for split in ("train", "val", "test"):
            images_dir = extra.get(f"{split}_images_dir")
            masks_dir = extra.get(f"{split}_masks_dir")
            if images_dir and masks_dir:
                yield from self._iter_pair(Path(images_dir).expanduser(), Path(masks_dir).expanduser(), split=split)

    def _iter_pair(self, images_dir: Path, masks_dir: Path, *, split: str | None) -> Iterable[dict[str, Any]]:
        if not images_dir.exists():
            raise FileNotFoundError(str(images_dir))
        if not masks_dir.exists():
            raise FileNotFoundError(str(masks_dir))

        for img_path in images_dir.rglob("*"):
            if img_path.suffix.lower() not in _IMG_EXTS:
                continue
            mask_path = masks_dir / f"{img_path.stem}.png"
            s: dict[str, Any] = {"path": str(img_path), "mask_path": str(mask_path)}
            if split is not None:
                s["official_split"] = split
            yield s
