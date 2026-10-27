"""Automated regression test suite for MobileNetV3 checkpoint caching, staging switching,
unsupported-crop rejection, and extreme image quality safety gates.
"""

from __future__ import annotations

import base64
import concurrent.futures
import io
from pathlib import Path
from PIL import Image, ImageFilter
import pytest
import torch

from app.core.config import get_settings
from app.schemas.models import MobileNetV3DiagnosisRequest
from app.vision.mobilenetv3_service import (
    clear_mobilenetv3_cache,
    diagnose_image_with_mobilenetv3,
    get_cached_mobilenetv3,
    run_mobilenetv3_diagnosis,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BASELINE_PATH = REPO_ROOT / "ml" / "models" / "mobilenetv3_plantdisease_best.pth"
STAGING_PATH = REPO_ROOT / "ml" / "models" / "mobilenetv3_plantdisease_staging.pth"
BACKUP_PATH = REPO_ROOT / "ml" / "models" / "mobilenetv3_plantdisease_best.production_backup_20261019.pth"


def create_test_image_b64(
    color: tuple[int, int, int] = (80, 140, 50),
    size: tuple[int, int] = (224, 224),
    fmt: str = "JPEG",
) -> str:
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


@pytest.fixture(autouse=True)
def clean_cache_between_tests():
    clear_mobilenetv3_cache()
    yield
    clear_mobilenetv3_cache()


# 1. Test model cache invalidation and dynamic switching between checkpoints
def test_checkpoint_caching_and_dynamic_switching():
    assert BASELINE_PATH.exists(), f"Baseline model not found at {BASELINE_PATH}"
    assert STAGING_PATH.exists(), f"Staging model not found at {STAGING_PATH}"

    # Load baseline
    model_1, ckpt_1, _ = get_cached_mobilenetv3(checkpoint_path=BASELINE_PATH)
    from app.vision import mobilenetv3_service
    assert mobilenetv3_service._CACHED_PATH == BASELINE_PATH.resolve()
    assert ckpt_1.get("best_epoch") == 10

    # Repeat call with baseline -> should return same cached instance without reload
    model_1_again, ckpt_1_again, _ = get_cached_mobilenetv3(checkpoint_path=BASELINE_PATH)
    assert model_1 is model_1_again
    assert ckpt_1 is ckpt_1_again

    # Switch to Staging (Experiment C)
    model_2, ckpt_2, _ = get_cached_mobilenetv3(checkpoint_path=STAGING_PATH)
    assert mobilenetv3_service._CACHED_PATH == STAGING_PATH.resolve()
    assert ckpt_2.get("best_epoch") == 9
    assert ckpt_2.get("experiment_name") == "Experiment C - Combined PlantVillage + PlantDoc"
    assert model_2 is not model_1

    # Switch back to Baseline
    model_3, ckpt_3, _ = get_cached_mobilenetv3(checkpoint_path=BASELINE_PATH)
    assert mobilenetv3_service._CACHED_PATH == BASELINE_PATH.resolve()
    assert ckpt_3.get("best_epoch") == 10

    # Test clear cache
    clear_mobilenetv3_cache()
    assert mobilenetv3_service._CACHED_MODEL is None
    assert mobilenetv3_service._CACHED_CKPT is None
    assert mobilenetv3_service._CACHED_PATH is None


# 2. Test concurrent multi-threaded requests
def test_concurrent_model_cache_access():
    def load_model_worker():
        m, c, d = get_cached_mobilenetv3(checkpoint_path=STAGING_PATH)
        return id(m), c.get("best_epoch")

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(load_model_worker) for _ in range(16)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    # All workers should get the exact same model id and epoch
    model_ids = {r[0] for r in results}
    epochs = {r[1] for r in results}
    assert len(model_ids) == 1
    assert epochs == {9}


# 3. Test unsupported-crop rejection
@pytest.mark.parametrize("unsupported_crop", ["apple", "grape", "cotton", "rice", "wheat", "mango", "onion"])
def test_unsupported_crop_rejection_safeguard(unsupported_crop: str):
    b64 = create_test_image_b64()
    req = MobileNetV3DiagnosisRequest(
        image_base64=b64,
        crop_hint=unsupported_crop,
        confidence_threshold=0.60,
    )
    resp = run_mobilenetv3_diagnosis(req, checkpoint_path=STAGING_PATH)

    assert resp.status == "rejected"
    assert resp.requires_expert is True
    assert f"crop '{unsupported_crop}' is outside" in resp.rejection_reason.lower()
    
    # Confirm safe non-chemical guidance
    hints = " ".join(resp.treatment_hints).lower()
    assert "avoid unverified chemical spraying" in hints
    assert not any(chem in hints for chem in ["fungicide", "pesticide spray", "kg/ha", "ml/l"])


# 4. Test low-quality, blank, and heavily blurred photographs
def test_low_quality_and_extreme_photographs():
    # Solid black
    black_img = Image.new("RGB", (224, 224), color=(0, 0, 0))
    buf_black = io.BytesIO()
    black_img.save(buf_black, format="JPEG")
    b64_black = base64.b64encode(buf_black.getvalue()).decode("utf-8")

    resp_black = run_mobilenetv3_diagnosis(
        MobileNetV3DiagnosisRequest(image_base64=b64_black),
        checkpoint_path=STAGING_PATH,
    )
    assert resp_black.status == "rejected"
    assert resp_black.requires_expert is True
    assert "low model confidence" in resp_black.rejection_reason.lower() or "validation failed" in resp_black.rejection_reason.lower()

    # Heavy blur
    real_sample_dir = REPO_ROOT / "ml" / "PlantVillage" / "raw" / "color" / "Tomato___Early_blight"
    sample_img = next(real_sample_dir.glob("*.JPG"))
    blurred = Image.open(sample_img).convert("RGB").filter(ImageFilter.GaussianBlur(radius=25))
    buf_blur = io.BytesIO()
    blurred.save(buf_blur, format="JPEG")
    b64_blur = base64.b64encode(buf_blur.getvalue()).decode("utf-8")

    resp_blur = run_mobilenetv3_diagnosis(
        MobileNetV3DiagnosisRequest(image_base64=b64_blur),
        checkpoint_path=STAGING_PATH,
    )
    assert resp_blur.status == "rejected"
    assert resp_blur.requires_expert is True


# 5. Test unconfirmed crop provisional disclaimer
def test_unknown_crop_provisional_disclaimer():
    b64 = create_test_image_b64()
    req = MobileNetV3DiagnosisRequest(
        image_base64=b64,
        crop_hint=None,  # No crop specified
        confidence_threshold=0.0,  # Accept prediction
    )
    resp = run_mobilenetv3_diagnosis(req, checkpoint_path=STAGING_PATH)

    assert resp.status == "accepted"
    hints = " ".join(resp.treatment_hints)
    assert "Provisional prediction" in hints or "Crop identity was not explicitly confirmed" in hints
    assert "Do not spray chemical pesticides or fungicides on unconfirmed diagnoses" in hints
