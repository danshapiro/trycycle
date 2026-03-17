from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from deepcycle.data.registry import DatasetSpec


@dataclass(frozen=True)
class CocoAdapter:
    spec: DatasetSpec

    def iter_samples(self) -> Iterable[dict[str, Any]]:
        # Expected spec.extra:
        # - annotation_json: path to COCO annotations (instances/ stuff)
        # - images_dir: directory containing images (optional; defaults to spec.root)
        # Optional official_splits:
        # - train_annotation_json / val_annotation_json / test_annotation_json (each COCO file)
        extra = self.spec.extra or {}

        if self.spec.official_splits:
            yield from self._iter_official_splits()
            return

        ann_path = Path(extra.get("annotation_json", self.spec.root / "annotations.json")).expanduser()
        images_dir = Path(extra.get("images_dir", self.spec.root)).expanduser()
        yield from self._iter_one(ann_path, images_dir, split=None)

    def _iter_official_splits(self) -> Iterable[dict[str, Any]]:
        extra = self.spec.extra or {}
        for split in ("train", "val", "test"):
            ann_key = f"{split}_annotation_json"
            if ann_key not in extra:
                continue
            ann_path = Path(extra[ann_key]).expanduser()
            images_dir = Path(extra.get(f"{split}_images_dir", extra.get("images_dir", self.spec.root))).expanduser()
            yield from self._iter_one(ann_path, images_dir, split=split)

    def _iter_one(self, ann_path: Path, images_dir: Path, *, split: str | None) -> Iterable[dict[str, Any]]:
        if not ann_path.exists():
            raise FileNotFoundError(str(ann_path))
        if not images_dir.exists():
            raise FileNotFoundError(str(images_dir))

        coco = json.loads(ann_path.read_text(encoding="utf-8"))
        images = {im["id"]: im for im in coco.get("images", [])}

        # group annotations by image_id
        anns_by_image: dict[int, list[dict[str, Any]]] = {}
        for ann in coco.get("annotations", []):
            anns_by_image.setdefault(int(ann["image_id"]), []).append(ann)

        for image_id, im in images.items():
            file_name = im.get("file_name")
            if not file_name:
                continue
            img_path = images_dir / file_name
            s: dict[str, Any] = {
                "path": str(img_path),
                "image_id": int(image_id),
                "coco_annotations": anns_by_image.get(int(image_id), []),
                "width": int(im.get("width", -1)),
                "height": int(im.get("height", -1)),
            }
            if split is not None:
                s["official_split"] = split
            yield s
