import argparse
from pathlib import Path

from deepcycle.reporting.aggregate import aggregate_reports


def add_report_subcommand(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("report", help="Aggregate multiple runs into a single summary report.")
    p.add_argument("--runs-dir", required=True, help="Directory containing run subdirectories.")
    p.add_argument("--out", required=True, help="Output path for aggregated markdown report.")
    p.set_defaults(_handler=_run)


def _run(args: argparse.Namespace) -> int:
    aggregate_reports(runs_dir=Path(args.runs_dir), out_path=Path(args.out))
    return 0
