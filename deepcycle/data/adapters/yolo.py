from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from deepcycle.data.registry import DatasetSpec


_IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


@dataclass(frozen=True)
class YoloAdapter:
    spec: DatasetSpec

    def iter_samples(self) -> Iterable[dict[str, Any]]:
        # Expected layout (default):
        # - images in spec.root/images
        # - labels in spec.root/labels with same stem, .txt
        # spec.extra may override with images_dir/labels_dir.
        extra = self.spec.extra or {}

        if self.spec.official_splits:
            yield from self._iter_official_splits()
            return

        images_dir = Path(extra.get("images_dir", self.spec.root / "images")).expanduser()
        labels_dir = Path(extra.get("labels_dir", self.spec.root / "labels")).expanduser()
        yield from self._iter_pair(images_dir, labels_dir, split=None)

    def _iter_official_splits(self) -> Iterable[dict[str, Any]]:
        extra = self.spec.extra or {}
        for split in ("train", "val", "test"):
            images_dir = extra.get(f"{split}_images_dir")
            labels_dir = extra.get(f"{split}_labels_dir")
            if images_dir and labels_dir:
                yield from self._iter_pair(Path(images_dir).expanduser(), Path(labels_dir).expanduser(), split=split)

    def _iter_pair(self, images_dir: Path, labels_dir: Path, *, split: str | None) -> Iterable[dict[str, Any]]:
        if not images_dir.exists():
            raise FileNotFoundError(str(images_dir))
        if not labels_dir.exists():
            raise FileNotFoundError(str(labels_dir))

        for img_path in images_dir.rglob("*"):
            if img_path.suffix.lower() not in _IMG_EXTS:
                continue
            label_path = labels_dir / f"{img_path.stem}.txt"
            boxes = []
            if label_path.exists():
                for line in label_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split()
                    if len(parts) != 5:
                        continue
                    cls, xc, yc, w, h = parts
                    boxes.append(
                        {
                            "class_id": int(float(cls)),
                            "xc": float(xc),
                            "yc": float(yc),
                            "w": float(w),
                            "h": float(h),
                        }
                    )

            s: dict[str, Any] = {"path": str(img_path), "yolo_boxes": boxes}
            if split is not None:
                s["official_split"] = split
            yield s
