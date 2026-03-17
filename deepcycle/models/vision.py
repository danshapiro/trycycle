from __future__ import annotations

from typing import Any


def build_classification_model(model_cfg: dict[str, Any], *, num_classes: int):
    _require_torchvision()
    import torchvision.models as M
    import torch.nn as nn

    name = str(model_cfg.get("name", "resnet50"))
    pretrained = bool(model_cfg.get("pretrained", True))

    if name == "resnet50":
        weights = M.ResNet50_Weights.DEFAULT if pretrained else None
        m = M.resnet50(weights=weights)
        m.fc = nn.Linear(m.fc.in_features, num_classes)
        return m

    if name == "efficientnet_b0":
        weights = M.EfficientNet_B0_Weights.DEFAULT if pretrained else None
        m = M.efficientnet_b0(weights=weights)
        m.classifier[-1] = nn.Linear(m.classifier[-1].in_features, num_classes)
        return m

    if name == "convnext_tiny":
        weights = M.ConvNeXt_Tiny_Weights.DEFAULT if pretrained else None
        m = M.convnext_tiny(weights=weights)
        m.classifier[-1] = nn.Linear(m.classifier[-1].in_features, num_classes)
        return m

    raise ValueError(f"Unknown classification model name: {name}")


def build_detection_model(model_cfg: dict[str, Any]):
    """
    Baseline detection models via torchvision.

    NOTE: Data pipelines for detection are implemented separately; this function
    exists to standardize model construction and config naming.
    """
    _require_torchvision()
    import torchvision.models.detection as D

    name = str(model_cfg.get("name", "fasterrcnn_resnet50_fpn"))
    pretrained = bool(model_cfg.get("pretrained", True))

    if name == "fasterrcnn_resnet50_fpn":
        weights = D.FasterRCNN_ResNet50_FPN_Weights.DEFAULT if pretrained else None
        return D.fasterrcnn_resnet50_fpn(weights=weights)

    if name == "retinanet_resnet50_fpn":
        weights = D.RetinaNet_ResNet50_FPN_Weights.DEFAULT if pretrained else None
        return D.retinanet_resnet50_fpn(weights=weights)

    raise ValueError(f"Unknown detection model name: {name}")


def build_segmentation_model(model_cfg: dict[str, Any], *, num_classes: int):
    """
    Baseline semantic segmentation models via torchvision.
    """
    _require_torchvision()
    import torchvision.models.segmentation as S

    name = str(model_cfg.get("name", "deeplabv3_resnet50"))
    pretrained = bool(model_cfg.get("pretrained", True))

    if name == "deeplabv3_resnet50":
        weights = S.DeepLabV3_ResNet50_Weights.DEFAULT if pretrained else None
        m = S.deeplabv3_resnet50(weights=weights)
        m.classifier[-1] = _conv1x1(m.classifier[-1].in_channels, num_classes)
        return m

    if name == "fcn_resnet50":
        weights = S.FCN_ResNet50_Weights.DEFAULT if pretrained else None
        m = S.fcn_resnet50(weights=weights)
        m.classifier[-1] = _conv1x1(m.classifier[-1].in_channels, num_classes)
        return m

    raise ValueError(f"Unknown segmentation model name: {name}")


def _conv1x1(in_ch: int, out_ch: int):
    import torch.nn as nn

    return nn.Conv2d(in_ch, out_ch, kernel_size=1)


def _require_torchvision() -> None:
    try:
        import torchvision  # noqa: F401
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "torchvision is required. Install with `pip install -e '.[torch]'` (or install torch/torchvision manually)."
        ) from e
