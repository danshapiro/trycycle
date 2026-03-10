from __future__ import annotations

import json
import shutil
from pathlib import Path

from .extract import build_model


ASSET_FILES = [
    "index.html",
    "app.js",
    "app.css",
    "vendor/markdown-lite.js",
]


def build_site(repo_root: Path, output_dir: Path, sidecar_path: Path | None = None) -> Path:
    repo_root = repo_root.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    model = build_model(repo_root, sidecar_path=sidecar_path)
    model_path = output_dir / "explorer-model.json"
    model_path.write_text(
        json.dumps(model.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    asset_root = Path(__file__).with_name("assets")
    for relative_path in ASSET_FILES:
        source = asset_root / relative_path
        destination = output_dir / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    return output_dir
