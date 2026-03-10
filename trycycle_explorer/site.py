from __future__ import annotations

import json
import shutil
from pathlib import Path

from .extract import ExplorerError, build_model, select_sample
from .simulate import simulate_render


ASSET_FILES = ["index.html", "app.js", "app.css", "vendor/markdown-lite.js"]


def build_site(
    repo_root: Path,
    output_dir: Path,
    sidecar_path: Path | None = None,
    sample_id: str | None = None,
) -> Path:
    repo_root = repo_root.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    model = build_model(repo_root, sidecar_path=sidecar_path)
    model = select_sample(model, sample_id)
    validate_renderable_samples(model)
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


def validate_renderable_samples(model) -> None:
    for sample in model.sample_inputs:
        try:
            simulate_render(
                model,
                gate_id=sample.selected_gate_id,
                bindings=sample.bindings,
                outcome_id=sample.selected_outcome_id,
                prompt_source_id=sample.selected_prompt_source_id,
            )
        except Exception as exc:
            raise ExplorerError(
                f"Sample {sample.id} could not be rendered: {exc}"
            ) from exc
