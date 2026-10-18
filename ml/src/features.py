"""Handcrafted feature extraction pipeline for plant disease leaf diagnosis.

Combines:
1. HSV Color Histograms & Color Moments: Captures chlorosis (yellowing), necrosis (browning/blackening), and healthy tissue.
2. Histogram of Oriented Gradients (HOG): Captures lesion borders, edge orientations, spot contours, and texture differences.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Union
import numpy as np
from PIL import Image

from ml.src.config import FEATURE_CONFIG


def extract_color_features(
    img: Image.Image,
    h_bins: int = 16,
    s_bins: int = 8,
    v_bins: int = 8,
) -> np.ndarray:
    """Extract normalized HSV histogram and RGB statistical moments."""
    # Convert to HSV for color distribution
    hsv_img = img.convert("HSV")
    hsv_arr = np.array(hsv_img, dtype=np.uint8)

    h_hist, _ = np.histogram(hsv_arr[:, :, 0], bins=h_bins, range=(0, 256), density=True)
    s_hist, _ = np.histogram(hsv_arr[:, :, 1], bins=s_bins, range=(0, 256), density=True)
    v_hist, _ = np.histogram(hsv_arr[:, :, 2], bins=v_bins, range=(0, 256), density=True)

    # RGB statistical moments (mean, std)
    rgb_arr = np.array(img.convert("RGB"), dtype=np.float32) / 255.0
    rgb_mean = np.mean(rgb_arr, axis=(0, 1))
    rgb_std = np.std(rgb_arr, axis=(0, 1))

    return np.concatenate([h_hist, s_hist, v_hist, rgb_mean, rgb_std])


def extract_hog_features(
    img: Image.Image,
    target_size: tuple[int, int] = (128, 128),
    cell_size: int = 16,
    n_bins: int = 8,
) -> np.ndarray:
    """
    Extract Histogram of Oriented Gradients (HOG) features in pure NumPy.
    Deterministic, reproducible, and fast without external native dependencies.
    """
    # Resize and convert to grayscale float
    gray = np.array(img.convert("L").resize(target_size), dtype=np.float32)

    # Gradient computation with 1D Sobel-equivalent central differences
    gx = np.zeros_like(gray)
    gy = np.zeros_like(gray)
    gx[:, 1:-1] = gray[:, 2:] - gray[:, :-2]
    gy[1:-1, :] = gray[2:, :] - gray[:-2, :]

    magnitude = np.hypot(gx, gy)
    angle = (np.arctan2(gy, gx) * 180.0 / np.pi) % 180.0

    h, w = target_size
    n_cells_y = h // cell_size
    n_cells_x = w // cell_size
    bin_width = 180.0 / n_bins

    # Spatial cell histograms
    cell_hists = np.zeros((n_cells_y, n_cells_x, n_bins), dtype=np.float32)
    bin_indices = np.clip(np.floor(angle / bin_width).astype(int), 0, n_bins - 1)

    for cy in range(n_cells_y):
        y_start, y_end = cy * cell_size, (cy + 1) * cell_size
        for cx in range(n_cells_x):
            x_start, x_end = cx * cell_size, (cx + 1) * cell_size
            c_mag = magnitude[y_start:y_end, x_start:x_end]
            c_bins = bin_indices[y_start:y_end, x_start:x_end]
            for b in range(n_bins):
                cell_hists[cy, cx, b] = np.sum(c_mag[c_bins == b])

    # 2x2 Cell Block L2-Hys normalization
    blocks = []
    eps = 1e-6
    for by in range(n_cells_y - 1):
        for bx in range(n_cells_x - 1):
            block = cell_hists[by : by + 2, bx : bx + 2, :].ravel()
            norm = np.sqrt(np.sum(block**2) + eps)
            block = np.minimum(block / norm, 0.2)
            norm = np.sqrt(np.sum(block**2) + eps)
            block = block / norm
            blocks.append(block)

    return np.concatenate(blocks)


def extract_features_from_image(
    image_input: Union[str, Path, bytes, Image.Image],
    config: dict = FEATURE_CONFIG,
) -> np.ndarray:
    """Extract joint color + HOG feature vector from path, bytes, or PIL Image."""
    if isinstance(image_input, (str, Path)):
        img = Image.open(image_input).convert("RGB")
    elif isinstance(image_input, bytes):
        img = Image.open(io.BytesIO(image_input)).convert("RGB")
    elif isinstance(image_input, Image.Image):
        img = image_input.convert("RGB")
    else:
        raise TypeError(f"Unsupported image input type: {type(image_input)}")

    color_feat = extract_color_features(
        img,
        h_bins=config["color_h_bins"],
        s_bins=config["color_s_bins"],
        v_bins=config["color_v_bins"],
    )
    hog_feat = extract_hog_features(
        img,
        target_size=config["image_size"],
        cell_size=config["hog_cell_size"],
        n_bins=config["hog_bins"],
    )

    return np.concatenate([color_feat, hog_feat]).astype(np.float32)
