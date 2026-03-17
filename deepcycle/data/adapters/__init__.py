from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Protocol

from deepcycle.data.registry import DatasetSpec


class DatasetAdapter(Protocol):
    def iter_samples(self) -> Iterable[dict[str, Any]]: ...


def get_adapter(spec: DatasetSpec) -> DatasetAdapter:
    if spec.label_format == "classification_folder":
        from deepcycle.data.adapters.classification_folder import ClassificationFolderAdapter

        return ClassificationFolderAdapter(spec)
    if spec.label_format == "coco":
        from deepcycle.data.adapters.coco import CocoAdapter

        return CocoAdapter(spec)
    if spec.label_format == "yolo":
        from deepcycle.data.adapters.yolo import YoloAdapter

        return YoloAdapter(spec)
    if spec.label_format == "voc":
        from deepcycle.data.adapters.voc import VocAdapter

        return VocAdapter(spec)
    if spec.label_format == "segmentation_masks":
        from deepcycle.data.adapters.segmentation_masks import SegmentationMasksAdapter

        return SegmentationMasksAdapter(spec)
    if spec.label_format == "custom":
        from deepcycle.data.adapters.custom import CustomAdapter

        return CustomAdapter(spec)
    raise ValueError(f"Unknown label_format: {spec.label_format}")

