import argparse
from pathlib import Path

from deepcycle.attack.attack_runner import run_attack


def add_attack_subcommand(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "attack",
        help="Adversarial task: evaluate robustness and/or train attack networks.",
    )
    p.add_argument("--mode", choices=["eval", "train_attack_model", "both"], default="both")
    p.add_argument("--config", required=True, help="Path to run config YAML.")
    p.add_argument("--checkpoint", required=True, help="Path to target model checkpoint.")
    p.add_argument("--run-dir", required=True, help="Run directory to write attack artifacts into.")
    p.set_defaults(_handler=_run)


def _run(args: argparse.Namespace) -> int:
    run_attack(
        mode=args.mode,
        config_path=Path(args.config),
        checkpoint_path=Path(args.checkpoint),
        run_dir=Path(args.run_dir),
    )
    return 0
