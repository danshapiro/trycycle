import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

TaskType = Literal["classification", "detection", "segmentation"]
LabelFormat = Literal["classification_folder", "coco", "yolo", "voc", "segmentation_masks", "custom"]


@dataclass(frozen=True)
class DatasetSpec:
    name: str
    task: TaskType
    label_format: LabelFormat
    root: Path

    # Optional hints
    classes: list[str] | None = None
    official_splits: dict[str, Any] | None = None  # e.g. {"train_dir": "...", "val_dir": "...", "test_dir": "..."}
    group_key: str | None = None
    extra: dict[str, Any] | None = None


def load_dataset_spec(path: Path) -> DatasetSpec:
    raw = _load_structured(path)
    root = Path(raw["root"]).expanduser()
    return DatasetSpec(
        name=str(raw["name"]),
        task=raw["task"],
        label_format=raw["label_format"],
        root=root,
        classes=raw.get("classes"),
        official_splits=raw.get("official_splits"),
        group_key=raw.get("group_key"),
        extra=raw.get("extra") or {},
    )


def _load_structured(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(str(path))
    if path.suffix.lower() in {".yml", ".yaml"}:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    raise ValueError(f"Unsupported spec format: {path.suffix} (use .yaml/.yml/.json)")
