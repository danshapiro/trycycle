import argparse
from pathlib import Path

from deepcycle.eval.evaluator import run_evaluation


def add_eval_subcommand(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("eval", help="Evaluate a checkpoint on test split and write report bundle.")
    p.add_argument("--config", required=True, help="Path to run config YAML used for training.")
    p.add_argument("--checkpoint", required=True, help="Path to checkpoint file.")
    p.add_argument("--run-dir", required=True, help="Run directory to write eval artifacts into.")
    p.set_defaults(_handler=_run)


def _run(args: argparse.Namespace) -> int:
    run_evaluation(
        config_path=Path(args.config),
        checkpoint_path=Path(args.checkpoint),
        run_dir=Path(args.run_dir),
    )
    return 0
