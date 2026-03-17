from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DeployResult:
    exported: dict[str, str]
    quantized: dict[str, str]
    metrics: dict[str, Any]


def deploy_model(
    *,
    config: dict[str, Any],
    checkpoint_path: Path,
    run_dir: Path,
    export_torchscript: bool = True,
    export_onnx: bool = False,
    quantize: str = "none",  # none|dynamic|static
) -> DeployResult:
    _require_torch()
    import torch

    from deepcycle.models.vision import build_classification_model

    task = str(config["task"])
    if task != "classification":
        raise NotImplementedError("Deployment currently supports classification targets only.")

    deploy_dir = run_dir / "deploy"
    deploy_dir.mkdir(parents=True, exist_ok=True)

    # Build model + load weights
    # Export uses CPU for portability
    device = torch.device("cpu")
    num_classes = int(config.get("model", {}).get("num_classes", 1))
    model = build_classification_model(config.get("model", {}), num_classes=num_classes).to(device)
    ckpt = torch.load(checkpoint_path, map_location="cpu")
    state = ckpt["model"] if isinstance(ckpt, dict) and "model" in ckpt else ckpt
    model.load_state_dict(state, strict=True)
    model.eval()

    exported: dict[str, str] = {}
    quantized_artifacts: dict[str, str] = {}

    # TorchScript export (freezing collapses some graph pieces for inference)
    if export_torchscript:
        example = torch.randn(1, 3, int(config.get("export", {}).get("image_size", 224)), int(config.get("export", {}).get("image_size", 224)))
        ts = torch.jit.trace(model, example)
        ts = torch.jit.freeze(ts)
        ts_path = deploy_dir / "model.ts"
        ts.save(str(ts_path))
        exported["torchscript"] = ts_path.name

    # Optional ONNX export
    if export_onnx:
        onnx_path = deploy_dir / "model.onnx"
        example = torch.randn(1, 3, int(config.get("export", {}).get("image_size", 224)), int(config.get("export", {}).get("image_size", 224)))
        torch.onnx.export(
            model,
            example,
            str(onnx_path),
            input_names=["input"],
            output_names=["logits"],
            opset_version=int(config.get("export", {}).get("opset", 17)),
            dynamic_axes={"input": {0: "batch"}, "logits": {0: "batch"}},
        )
        exported["onnx"] = onnx_path.name

    # Quantization
    qmode = str(quantize)
    if qmode == "none":
        pass
    elif qmode == "dynamic":
        qmodel = torch.quantization.quantize_dynamic(model, {torch.nn.Linear}, dtype=torch.qint8)
        q_path = deploy_dir / "model.dynamic_int8.pt"
        torch.save({"model": qmodel.state_dict(), "quantize": "dynamic_int8"}, q_path)
        quantized_artifacts["dynamic_int8_state_dict"] = q_path.name
        # also save TorchScript quantized if TorchScript export is desired
        if export_torchscript:
            example = torch.randn(1, 3, int(config.get("export", {}).get("image_size", 224)), int(config.get("export", {}).get("image_size", 224)))
            qts = torch.jit.trace(qmodel, example)
            qts = torch.jit.freeze(qts)
            qts_path = deploy_dir / "model.dynamic_int8.ts"
            qts.save(str(qts_path))
            quantized_artifacts["dynamic_int8_torchscript"] = qts_path.name
    elif qmode == "static":
        # Post-training static quantization (PTQ) using FX graph mode + calibration.
        # Calibration uses dataset-val.h5 by default.
        qts_name = _static_ptq_fx(
            config=config,
            float_model=model,
            deploy_dir=deploy_dir,
        )
        quantized_artifacts["static_int8_torchscript"] = qts_name
    else:
        raise ValueError(f"Unknown quantize mode: {qmode}")

    # Persist a deploy manifest so evaluation can compare variants
    manifest = {"exported": exported, "quantized": quantized_artifacts, "checkpoint": str(checkpoint_path)}
    (deploy_dir / "deploy_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    return DeployResult(exported=exported, quantized=quantized_artifacts, metrics={})


def _static_ptq_fx(*, config: dict[str, Any], float_model, deploy_dir: Path) -> str:
    import torch
    from torch.utils.data import DataLoader

    from deepcycle.augmentations.builder import build_classification_transforms
    from deepcycle.data.h5_dataset import H5ClassificationDataset
    from deepcycle.data.multi_h5 import MultiH5ClassificationDataset

    # Build calibration loader (val split)
    tfs = build_classification_transforms(config)
    dataset_dirs = config.get("dataset_dirs")
    if dataset_dirs:
        dataset_dirs = [Path(p) for p in dataset_dirs]
        cal_ds = MultiH5ClassificationDataset(
            dataset_dirs,
            split="val",
            transform=tfs.eval,
            weights=config.get("dataset_weights"),
        )
    else:
        dataset_dir = Path(config["dataset_dir"])
        cal_ds = H5ClassificationDataset(dataset_dir / "dataset-val.h5", transform=tfs.eval)

    cal_bs = int((config.get("export", {}) or {}).get("calib_batch_size", 32))
    cal_batches = int((config.get("export", {}) or {}).get("calib_batches", 20))
    cal_loader = DataLoader(cal_ds, batch_size=cal_bs, shuffle=True)

    # FX quantization
    try:
        from torch.ao.quantization import get_default_qconfig_mapping
        from torch.ao.quantization.quantize_fx import convert_fx, prepare_fx
    except Exception as e:
        raise RuntimeError("Static quantization requires torch.ao.quantization (PyTorch >= 1.13).") from e

    float_model.eval()
    example = torch.randn(
        1,
        3,
        int(config.get("export", {}).get("image_size", 224)),
        int(config.get("export", {}).get("image_size", 224)),
    )

    qconfig_mapping = get_default_qconfig_mapping("fbgemm")
    prepared = prepare_fx(float_model, qconfig_mapping, (example,))

    # Calibrate
    with torch.no_grad():
        for i, (xb, _) in enumerate(cal_loader):
            prepared(xb)
            if i + 1 >= cal_batches:
                break

    quantized = convert_fx(prepared)
    quantized.eval()

    # Export quantized TorchScript
    qts = torch.jit.trace(quantized, example)
    qts = torch.jit.freeze(qts)
    qts_path = deploy_dir / "model.static_int8.ts"
    qts.save(str(qts_path))
    return qts_path.name


def _require_torch() -> None:
    try:
        import torch  # noqa: F401
    except Exception as e:  # pragma: no cover
        raise RuntimeError("PyTorch is required. Install with `pip install -e '.[torch]'`.") from e

