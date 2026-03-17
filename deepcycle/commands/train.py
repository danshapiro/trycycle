import argparse
from pathlib import Path

from deepcycle.train.runner import run_training


def add_train_subcommand(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("train", help="Train a model from a config.")
    p.add_argument("--config", required=True, help="Path to training config YAML.")
    p.add_argument("--run-dir", required=True, help="Run output directory.")
    p.set_defaults(_handler=_run)


def _run(args: argparse.Namespace) -> int:
    run_training(config_path=Path(args.config), run_dir=Path(args.run_dir))
    return 0
