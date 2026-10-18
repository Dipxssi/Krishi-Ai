# Image Diagnosis Model — Design

**Date:** 2026-10-09  
**Status:** Draft — awaiting user review (approach B: shared backbone + per-crop heads)

## Goal

Replace the color-ratio heuristic in `backend/app/vision/` with a trained, calibrated CNN that identifies the crop and its disease from a leaf photo, for all 7 crops in `experts.py`. Must produce report-grade eval numbers (academic use) and degrade safely on real field photos (later real users).

## Decisions

| Topic | Choice |
|-------|--------|
| Architecture | Shared EfficientNet-B0 backbone (ImageNet-pretrained) + crop head + one disease head per crop (AdapterMoE-style) |
| Crops | tomato, potato, maize, wheat, rice, onion, cotton (+ `not_a_plant` class on crop head) |
| Training | Google Colab / Kaggle free GPU, single joint run (PyTorch + timm) |
| Inference | ONNX Runtime on CPU inside FastAPI; no PyTorch in backend |
| Model hosting | Hugging Face Hub repo + `backend/scripts/download_vision_model.py`; model files gitignored |
| Fallback | Existing heuristic when model files absent; always `requires_expert=True`, `model_version="heuristic"` |
| Public interface | `diagnose_image_bytes(image_base64, crop_hint)` unchanged; callers untouched |

## Part 1 — Model & training (Colab)

### Architecture

```text
image 224x224 ─► EfficientNet-B0 backbone ─► pooled features
                                              ├─► crop head      (8 classes: 7 crops + not_a_plant)
                                              └─► disease heads  (one Linear per crop, sized by its class list)
```

### Loss

Per image: `loss = CE(crop_head, crop_label) + CE(disease_head[crop_label], disease_label)`.  
`not_a_plant` images contribute only the crop term. Disease heads of other crops receive no gradient from that image.

Adding a crop later: freeze backbone, add crop class + new disease head, train heads only.

### Data

| Crop | Candidate sources (verify size + license in data audit) |
|------|------|
| tomato, potato, maize | PlantVillage (lab) + PlantDoc (field) |
| rice | Kaggle rice leaf disease datasets |
| wheat | Kaggle / CGIAR wheat rust & leaf disease datasets |
| cotton | Kaggle cotton leaf disease datasets |
| onion | Kaggle onion leaf disease datasets (expected sparse) |
| not_a_plant | PlantVillage `Background_without_leaves` + generic non-leaf images |

Rules:

- Disease class lists come from the data (e.g. tomato uses all PlantVillage tomato classes), not from the current hard-coded `CROP_DISEASES`.
- A disease class needs **≥150 training images** or it is dropped from training (listed with its image count in `metrics.json`).
- A crop head with **fewer than 2 viable classes** ships with `enabled: false`; backend returns `requires_expert=True` for that crop.
- Each image is tagged `domain: lab | field`.

### Splits

- Train / val / test split per class, stratified, no near-duplicate leakage (split by source file group where datasets provide it).
- **Test set is field-heavy**: all PlantDoc test images + team phone photos + field subsets of Kaggle sets.
- Val set is used for temperature scaling and threshold selection only.

### Augmentation

Random resized crop, flips, rotation ±25°, color jitter (brightness/contrast/saturation), Gaussian blur, JPEG compression. Goal: survive phone photos.

### Calibration & thresholds

- Temperature scaling per head (crop head + each disease head), fit on val.
- Per-head confidence threshold `tau` chosen from the val coverage-vs-accuracy curve: smallest `tau` giving ≥90% accuracy on accepted predictions (fallback `tau = 0.6` if the curve never reaches 90%).

### Notebook artifacts

| File | Contents |
|------|----------|
| `plant_v1.onnx` | Inputs: `image` float32 `[N,3,224,224]`. Outputs: `crop_logits [N,8]`, `disease_logits [N,D_total]` (all disease heads concatenated) |
| `plant_v1.json` | Metadata (schema below) |
| `metrics.json` | All eval numbers from Part 3 |

`plant_v1.json` schema:

```json
{
  "model_version": "plant_v1",
  "input_size": 224,
  "mean": [0.485, 0.456, 0.406],
  "std": [0.229, 0.224, 0.225],
  "crop_classes": ["tomato", "potato", "maize", "wheat", "rice", "onion", "cotton", "not_a_plant"],
  "crop_temperature": 1.0,
  "crop_tau": 0.6,
  "disease_heads": {
    "tomato": {
      "enabled": true,
      "offset": 0,
      "classes": ["healthy", "early_blight", "late_blight"],
      "temperature": 1.0,
      "tau": 0.6
    }
  }
}
```

The notebook lives at `ml/vision/train_plant_v1.ipynb` (repo root, outside the backend package).

## Part 2 — Backend integration

### Dependencies

Add `onnxruntime` and `numpy` to `backend/pyproject.toml`, pinned to releases older than 14 days.

### Config

| Env var | Default | Purpose |
|---------|---------|---------|
| `VISION_MODEL_DIR` | `backend/models/vision` | Where `.onnx` + `.json` live (gitignored) |
| `VISION_MODEL_NAME` | `plant_v1` | File stem |
| `VISION_HF_REPO` | none | Hugging Face repo id used by the download script |
| `VISION_BLUR_MIN` | `100.0` | Minimum Laplacian variance (grayscale, longest side 512px) |
| `VISION_CROP_HINT_MIN` | `0.20` | Min crop-head prob to trust the profile crop |
| `VISION_CROP_MISMATCH` | `0.70` | Model crop prob above which a disagreeing profile crop is overridden |

### Components

| File | Responsibility |
|------|----------------|
| `app/vision/quality.py` | `assess_quality(img) -> (score, reason or None)`: Laplacian variance (numpy 3x3 kernel) + mean brightness in `[0.15, 0.90]` |
| `app/vision/model.py` | `PlantPredictor` protocol: `predict(img) -> Prediction(crop_probs: dict, disease_probs: dict[crop, dict])`. `OnnxPlantPredictor` loads files, preprocesses, applies temperatures, softmax per head. `get_predictor()` returns cached instance or `None` if files missing |
| `app/vision/heuristic.py` | Current color-ratio logic moved from `experts.py` + `diagnosis.py`, plus lesion-area severity estimate |
| `app/vision/diagnosis.py` | Orchestrates the flow below; same public signature |
| `scripts/download_vision_model.py` | Downloads `.onnx` + `.json` from `VISION_HF_REPO` via HTTPS (httpx) into `VISION_MODEL_DIR` |

`experts.py` is removed; its disease lists are superseded by `plant_v1.json`.

### Flow in `diagnose_image_bytes`

1. Decode → on failure reject "Could not decode image — upload JPEG or PNG."
2. `assess_quality` → on failure reject with its reason (blurry / too dark / too bright).
3. `get_predictor()`; if `None` → heuristic path (`model_version="heuristic"`, `requires_expert=True`).
4. Crop decision:
   - top crop is `not_a_plant` → reject "No crop leaf detected — photograph a leaf up close."
   - `crop_hint` normalized and `p(hint) ≥ VISION_CROP_HINT_MIN` → use hint.
   - model top crop ≠ hint and `p(top) ≥ VISION_CROP_MISMATCH` → use model crop, set `crop_mismatch_note`.
   - no hint → use model top crop; if `p(top) < crop_tau` (from metadata) → reject "Crop not identified confidently…"
5. Disease head for chosen crop:
   - `enabled: false` → `requires_expert=True`, reason "No trained disease model for {crop} yet."
   - top prob `< tau` → `status="rejected"`, `requires_expert=True`, disease + confidence still reported.
   - else `status="ok"`.
6. `severity`: `"none"` when healthy; else lesion-area estimate (`low | moderate | high`) from heuristic, documented as an estimate.
7. `treatment_hints`: short generic scouting/safety hints only; real treatment text comes from RAG via `crop_agent` (no dose generation).

### Schema change

`ImageDiagnosisResult` gains optional fields:

- `model_version: str | None = None`
- `crop_mismatch_note: str | None = None`

No other contract changes; `crop_agent`, validator, orchestrator, frontend unchanged (frontend may display the new fields later).

### Error handling

- ONNX load error → log warning, treat as missing model (heuristic path).
- Inference exception → reject "Diagnosis failed — try another photo.", `requires_expert=True`.
- Images larger than 10 MB decoded bytes → reject before decoding.

## Part 3 — Evaluation & testing

### Report metrics (`metrics.json`)

- Crop head: accuracy, confusion matrix.
- Disease heads: per-crop macro-F1, per-class precision/recall, confusion matrix.
- Each of the above split by `domain` (lab vs field).
- ECE before and after temperature scaling, per head.
- Coverage-vs-accuracy curve per head and chosen `tau`.
- Rejection quality: `not_a_plant` recall; blur gate rejection rate on synthetic blurred test images.
- Dropped classes / disabled heads with image counts.

### Backend tests (`backend/tests/test_vision.py`)

Use a `FakePredictor` injected via monkeypatching `get_predictor`:

- blurry image rejected; sharp image passes quality
- fake `not_a_plant` → rejected
- fake crop disagrees with hint at high prob → model crop used, `crop_mismatch_note` set
- fake low disease confidence → `requires_expert=True`
- fake high disease confidence → `status="ok"`, correct disease, `model_version` set
- disabled head → `requires_expert=True`
- predictor `None` → heuristic path, `model_version="heuristic"`, `requires_expert=True`
- existing `test_phases_2_5.py` vision tests pass unchanged
- optional real-model smoke test, `pytest.skip` when model files absent

### Manual verification (Windows, local)

1. `cd backend; uv run python scripts/download_vision_model.py`
2. Run backend + frontend.
3. Upload: real tomato leaf → diagnosis; blurred photo → quality rejection; photo of a cup → not-a-plant rejection.

## Work order

1. Data audit — confirm datasets, sizes, licenses; finalize class lists.
2. Colab notebook — train, calibrate, evaluate, export.
3. Upload to Hugging Face; download script.
4. Backend integration + tests.
5. Docs (`README.md`, `docs/describe.md`, `backend/README.md`).

## Out of scope

- Lesion segmentation / true severity model
- On-device (mobile) inference
- Active-learning feedback loop from farmer uploads
- Vision-language model fallback
