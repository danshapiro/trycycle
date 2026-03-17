from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from deepcycle.data.registry import DatasetSpec


_IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


@dataclass(frozen=True)
class VocAdapter:
    spec: DatasetSpec

    def iter_samples(self) -> Iterable[dict[str, Any]]:
        # Expected layout (default):
        # - images: spec.root/JPEGImages
        # - annotations: spec.root/Annotations/*.xml
        # spec.extra may override images_dir/ann_dir.
        extra = self.spec.extra or {}
        images_dir = Path(extra.get("images_dir", self.spec.root / "JPEGImages")).expanduser()
        ann_dir = Path(extra.get("ann_dir", self.spec.root / "Annotations")).expanduser()

        if self.spec.official_splits:
            # Typical VOC splits are lists of ids; support via extra: train_ids/val_ids/test_ids text files
            yield from self._iter_official_splits(images_dir, ann_dir)
            return

        yield from self._iter_all(images_dir, ann_dir, split=None)

    def _iter_official_splits(self, images_dir: Path, ann_dir: Path) -> Iterable[dict[str, Any]]:
        extra = self.spec.extra or {}
        for split in ("train", "val", "test"):
            ids_path = extra.get(f"{split}_ids")
            if not ids_path:
                continue
            ids = [ln.strip() for ln in Path(ids_path).expanduser().read_text(encoding="utf-8").splitlines() if ln.strip()]
            for image_id in ids:
                img_path = _find_image(images_dir, image_id)
                ann_path = ann_dir / f"{image_id}.xml"
                yield self._one(img_path, ann_path, split=split)

    def _iter_all(self, images_dir: Path, ann_dir: Path, *, split: str | None) -> Iterable[dict[str, Any]]:
        if not ann_dir.exists():
            raise FileNotFoundError(str(ann_dir))
        for ann_path in ann_dir.glob("*.xml"):
            image_id = ann_path.stem
            img_path = _find_image(images_dir, image_id)
            yield self._one(img_path, ann_path, split=split)

    def _one(self, img_path: Path, ann_path: Path, *, split: str | None) -> dict[str, Any]:
        if not img_path.exists():
            raise FileNotFoundError(str(img_path))
        if not ann_path.exists():
            raise FileNotFoundError(str(ann_path))

        tree = ET.parse(ann_path)
        root = tree.getroot()
        objs = []
        for obj in root.findall("object"):
            name = obj.findtext("name") or ""
            bnd = obj.find("bndbox")
            if bnd is None:
                continue
            xmin = float(bnd.findtext("xmin") or 0)
            ymin = float(bnd.findtext("ymin") or 0)
            xmax = float(bnd.findtext("xmax") or 0)
            ymax = float(bnd.findtext("ymax") or 0)
            objs.append({"name": name, "bbox": [xmin, ymin, xmax, ymax]})

        s: dict[str, Any] = {"path": str(img_path), "voc_objects": objs}
        if split is not None:
            s["official_split"] = split
        return s


def _find_image(images_dir: Path, stem: str) -> Path:
    for ext in _IMG_EXTS:
        p = images_dir / f"{stem}{ext}"
        if p.exists():
            return p
    # fallback: any file with same stem
    for p in images_dir.glob(f"{stem}.*"):
        return p
    return images_dir / f"{stem}.jpg"
