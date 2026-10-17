"""Leaf-foreground segmentation module using Excess Green (ExG) and Otsu thresholding.

Provides modular, non-destructive preprocessing to isolate plant foliage from
outdoor field backgrounds (soil, mulch, shadows, weeds, and sky) and replace
background pixels with neutral studio grey (128, 128, 128).
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Union
import numpy as np
from PIL import Image
from scipy import ndimage

from ml.src.config import FEATURE_CONFIG
from ml.src.features import extract_features_from_image


def otsu_threshold(arr: np.ndarray) -> int:
    """Compute the Otsu optimal threshold maximizing inter-class variance in pure NumPy."""
    hist, _ = np.histogram(arr, bins=256, range=(0, 256))
    total = arr.size
    sum_total = float(np.dot(np.arange(256), hist))

    sum_b = 0.0
    weight_b = 0.0
    current_max = 0.0
    threshold = 0

    for t in range(256):
        weight_b += hist[t]
        if weight_b == 0.0:
            continue
        weight_f = total - weight_b
        if weight_f == 0.0:
            break

        sum_b += t * hist[t]
        mean_b = sum_b / weight_b
        mean_f = (sum_total - sum_b) / weight_f

        # Inter-class variance
        var_between = weight_b * weight_f * (mean_b - mean_f) ** 2
        if var_between > current_max:
            current_max = var_between
            threshold = t

    return int(threshold)


def segment_leaf_foreground(
    image_input: Union[str, Path, bytes, Image.Image],
    min_coverage: float = 0.05,
    max_coverage: float = 0.95,
    fill_color: tuple[int, int, int] = (128, 128, 128),
) -> tuple[Image.Image, dict[str, Any]]:
    """
    Segment leaf foreground using Excess Green Index (ExG = 2G - R - B) and Otsu thresholding.

    If leaf coverage is below min_coverage (under-segmentation) or above max_coverage
    (failed background separation), falls back gracefully to the original image.

    Returns:
        (processed_image, metadata_dict)
    """
    if isinstance(image_input, (str, Path)):
        img = Image.open(image_input).convert("RGB")
    elif isinstance(image_input, bytes):
        img = Image.open(io.BytesIO(image_input)).convert("RGB")
    elif isinstance(image_input, Image.Image):
        img = image_input.convert("RGB")
    else:
        raise TypeError(f"Unsupported image input type: {type(image_input)}")

    arr = np.array(img, dtype=np.float32)
    r = arr[:, :, 0]
    g = arr[:, :, 1]
    b = arr[:, :, 2]

    # Excess Green vegetation index
    exg = 2.0 * g - r - b
    exg_min = float(exg.min())
    exg_max = float(exg.max())

    if exg_max - exg_min < 1e-4:
        return img, {
            "is_fallback": True,
            "fallback_reason": "Zero ExG contrast",
            "coverage": 1.0,
            "threshold": 0,
        }

    exg_norm = np.clip((exg - exg_min) / (exg_max - exg_min) * 255.0, 0, 255).astype(np.uint8)
    threshold = otsu_threshold(exg_norm)

    mask = exg_norm >= threshold

    # Morphological refinement:
    # 1. Opening removes small background noise/flecks
    # 2. Closing fills small internal holes/lesions within leaf boundaries
    struct = ndimage.generate_binary_structure(2, 1)
    mask_opened = ndimage.binary_opening(mask, structure=struct, iterations=2)
    mask_refined = ndimage.binary_closing(mask_opened, structure=struct, iterations=3)

    coverage = float(np.mean(mask_refined))

    # Guardrails: coverage thresholds
    if coverage < min_coverage:
        return img, {
            "is_fallback": True,
            "fallback_reason": f"Under-coverage ({coverage:.3f} < {min_coverage})",
            "coverage": round(coverage, 4),
            "threshold": threshold,
        }
    if coverage > max_coverage:
        return img, {
            "is_fallback": True,
            "fallback_reason": f"Over-coverage ({coverage:.3f} > {max_coverage})",
            "coverage": round(coverage, 4),
            "threshold": threshold,
        }

    # Infill non-leaf background with neutral studio grey
    out_arr = np.array(img, dtype=np.uint8)
    out_arr[~mask_refined] = fill_color
    segmented_img = Image.fromarray(out_arr)

    return segmented_img, {
        "is_fallback": False,
        "fallback_reason": None,
        "coverage": round(coverage, 4),
        "threshold": threshold,
    }


def extract_features_with_optional_segmentation(
    image_input: Union[str, Path, bytes, Image.Image],
    use_segmentation: bool = True,
    config: dict = FEATURE_CONFIG,
) -> tuple[np.ndarray, dict[str, Any]]:
    """
    Extract 1,606-dimensional features from an image, optionally applying leaf segmentation.
    Returns (features_array, segmentation_metadata).
    """
    if use_segmentation:
        img_to_extract, meta = segment_leaf_foreground(image_input)
    else:
        if isinstance(image_input, (str, Path)):
            img_to_extract = Image.open(image_input).convert("RGB")
        elif isinstance(image_input, bytes):
            img_to_extract = Image.open(io.BytesIO(image_input)).convert("RGB")
        else:
            img_to_extract = image_input.convert("RGB")
        meta = {"is_fallback": False, "fallback_reason": "Segmentation bypassed", "coverage": 1.0, "threshold": 0}

    features = extract_features_from_image(img_to_extract, config=config)
    return features, meta
