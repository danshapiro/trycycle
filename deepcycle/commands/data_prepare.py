import argparse
from pathlib import Path

from deepcycle.data.registry import DatasetSpec, load_dataset_spec
from deepcycle.data.preprocess_hdf5 import preprocess_to_hdf5_splits


def add_data_prepare_subcommand(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "data:prepare",
        help="Preprocess raw dataset into dataset-{train,val,test}.h5 + metadata.",
    )
    p.add_argument("--dataset", required=True, help="Path to dataset spec YAML/JSON.")
    p.add_argument("--out-dir", required=True, help="Output directory for HDF5 splits.")
    p.add_argument("--seed", type=int, default=1337)
    p.add_argument(
        "--split-policy",
        default="existing_else_80_10_10",
        choices=["existing_else_80_10_10", "80_10_10", "70_15_15"],
        help="Split policy used when no official split exists.",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing output HDF5 files if present.",
    )
    p.set_defaults(_handler=_run)


def _run(args: argparse.Namespace) -> int:
    spec_path = Path(args.dataset)
    out_dir = Path(args.out_dir)

    spec: DatasetSpec = load_dataset_spec(spec_path)
    preprocess_to_hdf5_splits(
        spec=spec,
        out_dir=out_dir,
        seed=args.seed,
        split_policy=args.split_policy,
        force=args.force,
    )
    return 0
