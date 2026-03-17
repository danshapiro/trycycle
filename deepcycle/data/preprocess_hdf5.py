import hashlib
import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable

import h5py
import numpy as np
from PIL import Image
from tqdm import tqdm

from deepcycle.data.adapters import get_adapter
from deepcycle.data.registry import DatasetSpec
from deepcycle.data.splits import make_splits


def preprocess_to_hdf5_splits(
    *,
    spec: DatasetSpec,
    out_dir: Path,
    seed: int,
    split_policy: str,
    force: bool,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    train_path = out_dir / "dataset-train.h5"
    val_path = out_dir / "dataset-val.h5"
    test_path = out_dir / "dataset-test.h5"
    meta_path = out_dir / "metadata.json"

    for p in (train_path, val_path, test_path, meta_path):
        if p.exists() and not force:
            raise FileExistsError(f"{p} exists. Re-run with --force to overwrite.")

    adapter = get_adapter(spec)
    samples = list(adapter.iter_samples())
    splits = make_splits(spec=spec, samples=samples, seed=seed, split_policy=split_policy)

    stats: dict[str, Any] = {}
    stats["counts"] = {k: len(v) for k, v in splits.items()}

    _write_split_h5(train_path, splits["train"])
    _write_split_h5(val_path, splits["val"])
    _write_split_h5(test_path, splits["test"])

    metadata = {
        "schema_version": 1,
        "dataset": asdict(spec),
        "split_policy": split_policy,
        "seed": seed,
        "stats": stats,
        "task": spec.task,
        "label_format": spec.label_format,
        "artifacts": {
            "dataset-train.h5": _sha256(train_path),
            "dataset-val.h5": _sha256(val_path),
            "dataset-test.h5": _sha256(test_path),
        },
    }
    meta_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")


def _write_split_h5(path: Path, samples: list[dict[str, Any]]) -> None:
    # Store variable-sized encoded images + labels. Decode at training time.
    # For non-classification tasks, store labels as JSON strings for now.
    with h5py.File(path, "w") as f:
        dt = h5py.special_dtype(vlen=np.dtype("uint8"))
        img_ds = f.create_dataset("image_bytes", shape=(len(samples),), dtype=dt)
        y_ds = f.create_dataset("y", shape=(len(samples),), dtype=np.int64)
        path_ds = f.create_dataset("path", shape=(len(samples),), dtype=h5py.string_dtype("utf-8"))
        label_json_ds = f.create_dataset("label_json", shape=(len(samples),), dtype=h5py.string_dtype("utf-8"))

        for i, s in enumerate(tqdm(samples, desc=f"writing {os.path.basename(path)}")):
            img_bytes = _load_image_as_bytes(s["path"])
            img_ds[i] = np.frombuffer(img_bytes, dtype=np.uint8)
            y_ds[i] = int(s.get("y", -1))
            path_ds[i] = s["path"]
            label_json_ds[i] = json.dumps({k: v for k, v in s.items() if k not in {"path", "y"}})


def _load_image_as_bytes(path: str) -> bytes:
    # Re-encode to PNG for deterministic representation (integrity) and wide support.
    img = Image.open(path).convert("RGB")
    from io import BytesIO

    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()
