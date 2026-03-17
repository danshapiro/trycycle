import argparse
import sys

from deepcycle.commands.attack import add_attack_subcommand
from deepcycle.commands.data_prepare import add_data_prepare_subcommand
from deepcycle.commands.deploy import add_deploy_subcommand
from deepcycle.commands.eval_cmd import add_eval_subcommand
from deepcycle.commands.report import add_report_subcommand
from deepcycle.commands.research import add_research_subcommand
from deepcycle.commands.train import add_train_subcommand


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="deepcycle",
        description="Deepcycle: CV deep-learning skill (HDF5 data, train/eval/attack/report/research).",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_data_prepare_subcommand(subparsers)
    add_train_subcommand(subparsers)
    add_eval_subcommand(subparsers)
    add_attack_subcommand(subparsers)
    add_deploy_subcommand(subparsers)
    add_report_subcommand(subparsers)
    add_research_subcommand(subparsers)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args._handler(args))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
