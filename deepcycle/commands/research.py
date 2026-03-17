import argparse
from pathlib import Path

from deepcycle.research.roadmap import update_roadmap


def add_research_subcommand(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("research", help="Update research roadmap based on eval artifacts.")
    p.add_argument("--runs-dir", required=True, help="Directory containing run subdirectories.")
    p.add_argument("--out", required=True, help="Output roadmap markdown path.")
    p.set_defaults(_handler=_run)


def _run(args: argparse.Namespace) -> int:
    update_roadmap(runs_dir=Path(args.runs_dir), out_path=Path(args.out))
    return 0
