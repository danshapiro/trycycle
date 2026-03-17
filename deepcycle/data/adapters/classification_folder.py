from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from deepcycle.data.registry import DatasetSpec


_IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


@dataclass(frozen=True)
class ClassificationFolderAdapter:
    spec: DatasetSpec

    def iter_samples(self) -> Iterable[dict[str, Any]]:
        # Supports either:
        # - root/<class_name>/*.jpg (single root, later split by policy), or
        # - official_splits: {"train_root": "...", "val_root": "...", "test_root": "..."} with same folder-per-class layout.
        if self.spec.official_splits:
            yield from self._iter_official_splits()
        else:
            yield from self._iter_root(self.spec.root, split=None)

    def _iter_official_splits(self) -> Iterable[dict[str, Any]]:
        splits = self.spec.official_splits or {}
        for split in ("train", "val", "test"):
            key = f"{split}_root"
            if key not in splits:
                continue
            root = Path(splits[key]).expanduser()
            yield from self._iter_root(root, split=split)

    def _iter_root(self, root: Path, *, split: str | None) -> Iterable[dict[str, Any]]:
        if not root.exists():
            raise FileNotFoundError(str(root))

        class_dirs = [p for p in root.iterdir() if p.is_dir()]
        class_names = sorted([p.name for p in class_dirs]) if self.spec.classes is None else list(self.spec.classes)
        class_to_idx = {c: i for i, c in enumerate(class_names)}

        for class_name in class_names:
            class_dir = root / class_name
            if not class_dir.exists():
                continue
            for img_path in class_dir.rglob("*"):
                if img_path.suffix.lower() not in _IMG_EXTS:
                    continue
                s: dict[str, Any] = {"path": str(img_path), "y": int(class_to_idx[class_name])}
                if split is not None:
                    s["official_split"] = split
                yield s
