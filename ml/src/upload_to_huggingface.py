"""Upload MobileNetV3 Plant Disease Classifier artifact to Hugging Face Model Hub.

Usage:
    # 1. Login with Hugging Face CLI or set environment variable:
    export HF_TOKEN="hf_your_token_here"

    # 2. Run upload script:
    python ml/src/upload_to_huggingface.py --repo-id "Dipxssi/krishiai-mobilenetv3"

    # Optional: make the repo private
    python ml/src/upload_to_huggingface.py --repo-id "Dipxssi/krishiai-mobilenetv3" --private
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import torch

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ml.src.config import MODELS_DIR, TARGET_CLASSES

DEFAULT_REPO_ID = "Dipxssi/krishiai-mobilenetv3"
CHECKPOINT_NAME = "mobilenetv3_plantdisease_best.pth"


def generate_model_card() -> str:
    return """---
language:
- en
license: mit
tags:
- plant-disease
- agriculture
- computer-vision
- mobilenetv3
- pytorch
- krishiai
datasets:
- PlantVillage
metrics:
- accuracy
- f1
pipeline_tag: image-classification
---

# KrishiAI MobileNetV3 Plant Disease & Foliar Health Classifier

Trained lightweight transfer learning model for foliar plant disease classification across 17 target classes in **Tomato**, **Potato**, and **Corn (Maize)**.

Integrated as the primary visual screening backbone in the **KrishiAI Multi-Agent Farmer Advisory System**.

## Model Summary

- **Architecture**: `mobilenet_v3_small` (1.54M parameters, 5.98 MB)
- **Pretrained Backbone**: ImageNet-1K (`torchvision.models.MobileNet_V3_Small_Weights.DEFAULT`)
- **Input Dimensions**: 224 × 224 pixels, RGB
- **Normalization**: ImageNet Mean `[0.485, 0.456, 0.406]`, Std `[0.229, 0.224, 0.225]`
- **Inference Latency**: 4.29 ms on Apple Silicon GPU/MPS; ~12 ms on standard CPU

## Evaluation Performance

| Evaluation Split | Metric | Score | Notes |
| :--- | :--- | :---: | :--- |
| **PlantVillage Test** (Held-out, N=3,621) | **Accuracy** | **98.56%** | Zero specimen overlap with training |
| | **Macro-F1** | **0.9805** | Balanced across all 17 classes |
| | **Weighted-F1** | **0.9857** | Clean laboratory reference leaves |
| | **Confidence-Gated Acc (≥ 0.60)** | **98.89%** | Rejection rate: 0.88% |
| **PlantDoc External Benchmark** (Field, N=1,151) | **In-Scope Accuracy** | **20.85%** | Real-world in-the-wild field imagery |
| | **In-Scope Macro-F1** | **0.1280** | Unconstrained field domain gap |
| | **Out-of-Scope Rejection Rate** | **30.73%** | Rejects unsupported species |

## Supported Classes (17 Target Categories)

1. Corn (Maize) — Gray Leaf Spot (*Cercospora zeae-maydis*)
2. Corn (Maize) — Common Rust (*Puccinia sorghi*)
3. Corn (Maize) — Northern Leaf Blight (*Exserohilum turcicum*)
4. Corn (Maize) — Healthy Foliage
5. Potato — Early Blight (*Alternaria solani*)
6. Potato — Late Blight (*Phytophthora infestans*)
7. Potato — Healthy Foliage
8. Tomato — Bacterial Spot (*Xanthomonas campestris*)
9. Tomato — Early Blight (*Alternaria solani*)
10. Tomato — Late Blight (*Phytophthora infestans*)
11. Tomato — Leaf Mold (*Passalora fulva*)
12. Tomato — Septoria Leaf Spot (*Septoria lycopersici*)
13. Tomato — Two-Spotted Spider Mite (*Tetranychus urticae*)
14. Tomato — Target Spot (*Corynespora cassiicola*)
15. Tomato — Yellow Leaf Curl Virus (TYLCV)
16. Tomato — Mosaic Virus (ToMV)
17. Tomato — Healthy Foliage

## Agronomic Usage Disclaimers

> [!WARNING]
> This model is trained primarily on laboratory imagery and is deployed within KrishiAI as an **advisory screening tool with confidence gating ($\tau = 0.60$)**. It is **not verified for unattended chemical pesticide or fungicide spraying**. Physical confirmation by a local Krishi Vigyan Kendra (KVK) agronomist or extension specialist is mandatory prior to applying commercial treatments.

## How to Load in Python

```python
import torch
from huggingface_hub import hf_hub_download
from torchvision import models

# 1. Download checkpoint from Hugging Face Hub
ckpt_path = hf_hub_download(
    repo_id="Dipxssi/krishiai-mobilenetv3",
    filename="mobilenetv3_plantdisease_best.pth",
)

# 2. Recreate model architecture
ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
model = models.mobilenet_v3_small(weights=None)
model.classifier[-1] = torch.nn.Linear(model.classifier[-1].in_features, ckpt["num_classes"])
model.load_state_dict(ckpt["model_state_dict"])
model.eval()
print(f"Loaded {ckpt['architecture']} with {ckpt['num_classes']} classes.")
```
"""


def generate_config_json() -> str:
    config_dict = {
        "model_type": "mobilenet_v3_small",
        "num_classes": len(TARGET_CLASSES),
        "image_size": [224, 224],
        "normalization": {
            "mean": [0.485, 0.456, 0.406],
            "std": [0.229, 0.224, 0.225],
        },
        "id2label": {str(c["class_idx"]): c["display_name"] for c in TARGET_CLASSES},
        "label2id": {c["display_name"]: c["class_idx"] for c in TARGET_CLASSES},
        "classes_metadata": TARGET_CLASSES,
        "default_confidence_threshold": 0.60,
    }
    return json.dumps(config_dict, indent=2)


def upload_to_hf(
    repo_id: str,
    token: str | None = None,
    private: bool = False,
    checkpoint_path: Path | None = None,
) -> None:
    try:
        from huggingface_hub import HfApi
    except ImportError:
        print("Error: huggingface_hub is not installed. Run `pip install huggingface_hub`.")
        sys.exit(1)

    auth_token = token or os.environ.get("HF_TOKEN")
    if not auth_token:
        print("\n[!] Warning: No HF_TOKEN provided.")
        print("    If the repository is private or does not exist yet, you must supply a token via:")
        print("    export HF_TOKEN='your_token'")
        print("    or --token 'your_token'")

    if checkpoint_path is None:
        checkpoint_path = MODELS_DIR / CHECKPOINT_NAME

    if not checkpoint_path.exists():
        print(f"Error: Checkpoint file not found at {checkpoint_path}")
        sys.exit(1)

    api = HfApi(token=auth_token)

    # Auto-detect namespace from authenticated token
    try:
        user_info = api.whoami()
        current_username = user_info.get("name")
        if "/" in repo_id:
            namespace, model_name = repo_id.split("/", 1)
            if namespace in ("Dipxssi", "username", "your-username") or (current_username and namespace != current_username):
                print(f"[*] Adjusting repository namespace from '{namespace}' to authenticated user '{current_username}'...")
                repo_id = f"{current_username}/{model_name}"
        elif current_username:
            repo_id = f"{current_username}/{repo_id}"
    except Exception as e:
        pass

    print(f"\n1. Ensuring Hugging Face repository exists: {repo_id}...")
    api.create_repo(
        repo_id=repo_id,
        repo_type="model",
        private=private,
        exist_ok=True,
    )
    print("   Repository verified.")

    # Prepare temp files for README and config.json
    temp_dir = MODELS_DIR / "_hf_upload_temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    readme_path = temp_dir / "README.md"
    config_path = temp_dir / "config.json"

    readme_path.write_text(generate_model_card(), encoding="utf-8")
    config_path.write_text(generate_config_json(), encoding="utf-8")

    print(f"\n2. Uploading {checkpoint_path.name} ({checkpoint_path.stat().st_size / (1024*1024):.2f} MB)...")
    api.upload_file(
        path_or_fileobj=str(checkpoint_path),
        path_in_repo=CHECKPOINT_NAME,
        repo_id=repo_id,
        repo_type="model",
    )
    print("   Checkpoint upload complete.")

    print("\n3. Uploading config.json and README.md (Model Card)...")
    api.upload_file(
        path_or_fileobj=str(config_path),
        path_in_repo="config.json",
        repo_id=repo_id,
        repo_type="model",
    )
    api.upload_file(
        path_or_fileobj=str(readme_path),
        path_in_repo="README.md",
        repo_id=repo_id,
        repo_type="model",
    )
    print("   Metadata upload complete.")

    # Cleanup temp dir
    for f in temp_dir.glob("*"):
        f.unlink()
    temp_dir.rmdir()

    print(f"\nSUCCESS! Model published to: https://huggingface.co/{repo_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload MobileNetV3 to Hugging Face Model Hub")
    parser.add_argument(
        "--repo-id",
        type=str,
        default=DEFAULT_REPO_ID,
        help=f"Target Hugging Face model repo (default: {DEFAULT_REPO_ID})",
    )
    parser.add_argument(
        "--token",
        type=str,
        default=None,
        help="Hugging Face User Access Token (or set HF_TOKEN env variable)",
    )
    parser.add_argument(
        "--private",
        action="store_true",
        help="Make the Hugging Face repository private",
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=None,
        help="Path to local .pth file (default: ml/models/mobilenetv3_plantdisease_best.pth)",
    )
    args = parser.parse_args()

    upload_to_hf(
        repo_id=args.repo_id,
        token=args.token,
        private=args.private,
        checkpoint_path=args.checkpoint,
    )


if __name__ == "__main__":
    main()
