"""Configuration and class definitions for Krishi AI 17-class PlantVillage pipeline."""

from pathlib import Path
from typing import Any

# Target classes configuration (Option A: 17 classes covering tomato, potato, maize)
TARGET_CLASSES: list[dict[str, Any]] = [
    {
        "class_idx": 0,
        "folder_name": "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot",
        "crop": "maize",
        "disease": "gray_leaf_spot",
        "display_name": "Corn Gray Leaf Spot",
        "is_healthy": False,
    },
    {
        "class_idx": 1,
        "folder_name": "Corn_(maize)___Common_rust_",
        "crop": "maize",
        "disease": "rust",
        "display_name": "Corn Common Rust",
        "is_healthy": False,
    },
    {
        "class_idx": 2,
        "folder_name": "Corn_(maize)___Northern_Leaf_Blight",
        "crop": "maize",
        "disease": "northern_leaf_blight",
        "display_name": "Corn Northern Leaf Blight",
        "is_healthy": False,
    },
    {
        "class_idx": 3,
        "folder_name": "Corn_(maize)___healthy",
        "crop": "maize",
        "disease": "healthy",
        "display_name": "Corn Healthy",
        "is_healthy": True,
    },
    {
        "class_idx": 4,
        "folder_name": "Potato___Early_blight",
        "crop": "potato",
        "disease": "early_blight",
        "display_name": "Potato Early Blight",
        "is_healthy": False,
    },
    {
        "class_idx": 5,
        "folder_name": "Potato___Late_blight",
        "crop": "potato",
        "disease": "late_blight",
        "display_name": "Potato Late Blight",
        "is_healthy": False,
    },
    {
        "class_idx": 6,
        "folder_name": "Potato___healthy",
        "crop": "potato",
        "disease": "healthy",
        "display_name": "Potato Healthy",
        "is_healthy": True,
    },
    {
        "class_idx": 7,
        "folder_name": "Tomato___Bacterial_spot",
        "crop": "tomato",
        "disease": "bacterial_spot",
        "display_name": "Tomato Bacterial Spot",
        "is_healthy": False,
    },
    {
        "class_idx": 8,
        "folder_name": "Tomato___Early_blight",
        "crop": "tomato",
        "disease": "early_blight",
        "display_name": "Tomato Early Blight",
        "is_healthy": False,
    },
    {
        "class_idx": 9,
        "folder_name": "Tomato___Late_blight",
        "crop": "tomato",
        "disease": "late_blight",
        "display_name": "Tomato Late Blight",
        "is_healthy": False,
    },
    {
        "class_idx": 10,
        "folder_name": "Tomato___Leaf_Mold",
        "crop": "tomato",
        "disease": "leaf_mold",
        "display_name": "Tomato Leaf Mold",
        "is_healthy": False,
    },
    {
        "class_idx": 11,
        "folder_name": "Tomato___Septoria_leaf_spot",
        "crop": "tomato",
        "disease": "septoria_leaf_spot",
        "display_name": "Tomato Septoria Leaf Spot",
        "is_healthy": False,
    },
    {
        "class_idx": 12,
        "folder_name": "Tomato___Spider_mites Two-spotted_spider_mite",
        "crop": "tomato",
        "disease": "spider_mites",
        "display_name": "Tomato Two-spotted Spider Mite",
        "is_healthy": False,
    },
    {
        "class_idx": 13,
        "folder_name": "Tomato___Target_Spot",
        "crop": "tomato",
        "disease": "target_spot",
        "display_name": "Tomato Target Spot",
        "is_healthy": False,
    },
    {
        "class_idx": 14,
        "folder_name": "Tomato___Tomato_Yellow_Leaf_Curl_Virus",
        "crop": "tomato",
        "disease": "yellow_leaf_curl_virus",
        "display_name": "Tomato Yellow Leaf Curl Virus",
        "is_healthy": False,
    },
    {
        "class_idx": 15,
        "folder_name": "Tomato___Tomato_mosaic_virus",
        "crop": "tomato",
        "disease": "mosaic_virus",
        "display_name": "Tomato Mosaic Virus",
        "is_healthy": False,
    },
    {
        "class_idx": 16,
        "folder_name": "Tomato___healthy",
        "crop": "tomato",
        "disease": "healthy",
        "display_name": "Tomato Healthy",
        "is_healthy": True,
    },
]

FOLDER_TO_CLASS = {c["folder_name"]: c for c in TARGET_CLASSES}
IDX_TO_CLASS = {c["class_idx"]: c for c in TARGET_CLASSES}

# Path constants relative to project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATASET_DIR = PROJECT_ROOT / "ml" / "PlantVillage" / "raw" / "color"
SPLITS_DIR = PROJECT_ROOT / "ml" / "splits"
FEATURES_DIR = PROJECT_ROOT / "ml" / "features"
MODELS_DIR = PROJECT_ROOT / "ml" / "models"

# Feature extraction hyperparameters
FEATURE_CONFIG = {
    "image_size": (128, 128),
    "hog_cell_size": 16,
    "hog_bins": 8,
    "color_h_bins": 16,
    "color_s_bins": 8,
    "color_v_bins": 8,
}

# ElasticNet Model configuration
ELASTICNET_CONFIG = {
    "penalty": "elasticnet",
    "solver": "saga",
    "tol": 1e-3,
    "max_iter": 2000,
    "random_state": 42,
    # Hyperparameter grid for validation tuning
    "param_grid": {
        "C": [0.01, 0.1, 1.0, 10.0],
        "l1_ratio": [0.1, 0.3, 0.5, 0.7, 0.9],
        "class_weight": ["balanced", None],
    },
}
