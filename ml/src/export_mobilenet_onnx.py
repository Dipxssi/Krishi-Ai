"""Export the public MobileNetV3 checkpoint to ONNX for CPU inference on Render Free.

Run from the repo root with torch + torchvision installed:

    python ml/src/export_mobilenet_onnx.py
"""

from __future__ import annotations

import urllib.request
from pathlib import Path

import torch
import torch.nn as nn
from torchvision import models

ROOT = Path(__file__).resolve().parents[2]
CKPT = ROOT / "backend" / "models" / "mobilenetv3_plantdisease_best.pth"
ONNX = ROOT / "backend" / "models" / "mobilenetv3_plantdisease.onnx"
URL = (
    "https://huggingface.co/Ishan2702/krishiai-mobilenetv3/resolve/main/"
    "mobilenetv3_plantdisease_best.pth"
)


def create_mobilenetv3(num_classes: int = 17) -> nn.Module:
    model = models.mobilenet_v3_small(weights=None)
    in_features = model.classifier[-1].in_features
    model.classifier[-1] = nn.Linear(in_features, num_classes)
    return model


def main() -> None:
    CKPT.parent.mkdir(parents=True, exist_ok=True)
    if not CKPT.exists():
        print(f"downloading {URL}")
        urllib.request.urlretrieve(URL, CKPT)
    ckpt = torch.load(CKPT, map_location="cpu", weights_only=False)
    model = create_mobilenetv3(num_classes=int(ckpt["num_classes"]))
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()
    dummy = torch.zeros(1, 3, 224, 224)
    torch.onnx.export(
        model,
        dummy,
        str(ONNX),
        input_names=["image"],
        output_names=["logits"],
        dynamo=False,
        opset_version=18,
    )
    print(f"wrote {ONNX} ({ONNX.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
