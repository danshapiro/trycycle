import json
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from deepcycle.utils.config import load_yaml
from deepcycle.utils.git_info import try_get_git_sha


@dataclass(frozen=True)
class TrainConfig:
    task: str
    model: dict[str, Any]
    train: dict[str, Any]


def run_training(*, config_path: Path, run_dir: Path) -> None:
    cfg_raw = load_yaml(config_path)
    cfg = TrainConfig(
        task=str(cfg_raw["task"]),
        model=dict(cfg_raw.get("model") or {}),
        train=dict(cfg_raw.get("train") or {}),
    )

    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "config.yaml").write_text(config_path.read_text(encoding="utf-8"), encoding="utf-8")
    _write_manifest(run_dir, cfg_raw)

    if cfg.task != "classification":
        raise NotImplementedError("Only task=classification is runnable in this initial implementation.")

    from deepcycle.train.train_classification import train_classification

    train_classification(cfg=cfg_raw, run_dir=run_dir)


def _write_manifest(run_dir: Path, cfg_raw: dict[str, Any]) -> None:
    manifest = {
       "git": {
           "sha": try_get_git_sha(Path.cwd()),
       },
        "platform": {
            "python": platform.python_version(),
            "system": platform.platform(),
        },
        "config": cfg_raw,
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
