import argparse
import json
from pathlib import Path

from deepcycle.deploy.export import deploy_model
from deepcycle.utils.config import load_yaml


def add_deploy_subcommand(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "deploy",
        help="Export/freeze/optimize a trained model for deployment; optionally quantize and evaluate accuracy drop.",
    )
    p.add_argument("--config", required=True, help="Path to run config YAML used for training.")
    p.add_argument("--checkpoint", required=True, help="Path to checkpoint file.")
    p.add_argument("--run-dir", required=True, help="Run directory to write deploy artifacts into.")
    p.add_argument("--export-torchscript", action="store_true", default=True)
    p.add_argument("--export-onnx", action="store_true", default=False)
    p.add_argument("--quantize", choices=["none", "dynamic", "static"], default="none")
    p.add_argument(
        "--eval-quantized",
        action="store_true",
        help="If set, run evaluation on quantized TorchScript (when available) and write an accuracy-drop report.",
    )
    p.set_defaults(_handler=_run)


def _run(args: argparse.Namespace) -> int:
    cfg = load_yaml(Path(args.config))
    run_dir = Path(args.run_dir)
    res = deploy_model(
        config=cfg,
        checkpoint_path=Path(args.checkpoint),
        run_dir=run_dir,
        export_torchscript=bool(args.export_torchscript),
        export_onnx=bool(args.export_onnx),
        quantize=str(args.quantize),
    )

    deploy_dir = run_dir / "deploy"
    (deploy_dir / "deploy_result.json").write_text(
        json.dumps({"exported": res.exported, "quantized": res.quantized, "metrics": res.metrics}, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    if args.eval_quantized:
        from deepcycle.deploy.quant_eval import evaluate_quantized_variants

        evaluate_quantized_variants(config_path=Path(args.config), run_dir=run_dir)

    return 0

