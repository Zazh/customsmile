"""
Inference pipeline: STL file → per-face tooth labels (FDI notation).

Two models:
  - Upper jaw (maxillary): teeth 17-11, 21-27 + gingiva = 15 classes
  - Lower jaw (mandibular): teeth 47-41, 31-37 + gingiva = 15 classes

Usage:
    from stl.ml.inference import segment_mesh
    labels = segment_mesh("/path/to/upper.stl", jaw="upper")
    # labels = {"tooth_11": [0, 1, 2, ...], "gingiva": [55, 56, ...]}
"""

import logging
import zipfile
from pathlib import Path

import numpy as np
import torch

from .model import MeshSegNet
from .preprocess import load_and_preprocess

logger = logging.getLogger(__name__)

# ── Class index → FDI tooth label mapping ──
# 0 = gingiva, 1-14 = teeth from right 2nd molar to left 2nd molar

UPPER_CLASS_MAP = {
    0: "gingiva",
    1: "tooth_17", 2: "tooth_16", 3: "tooth_15", 4: "tooth_14",
    5: "tooth_13", 6: "tooth_12", 7: "tooth_11",
    8: "tooth_21", 9: "tooth_22", 10: "tooth_23", 11: "tooth_24",
    12: "tooth_25", 13: "tooth_26", 14: "tooth_27",
}

LOWER_CLASS_MAP = {
    0: "gingiva",
    1: "tooth_47", 2: "tooth_46", 3: "tooth_45", 4: "tooth_44",
    5: "tooth_43", 6: "tooth_42", 7: "tooth_41",
    8: "tooth_31", 9: "tooth_32", 10: "tooth_33", 11: "tooth_34",
    12: "tooth_35", 13: "tooth_36", 14: "tooth_37",
}

# ── Weights ──
WEIGHTS_DIR = Path(__file__).parent / "weights"
UPPER_WEIGHTS = WEIGHTS_DIR / "MeshSegNet_Max_15_classes_72samples_lr1e-2_best.tar"
LOWER_WEIGHTS = WEIGHTS_DIR / "MeshSegNet_Man_15_classes_72samples_lr1e-2_best.tar"

_model_cache: dict[str, MeshSegNet] = {}


def _ensure_weights_extracted():
    """Extract .tar from .zip if needed."""
    for tar_path in [UPPER_WEIGHTS, LOWER_WEIGHTS]:
        if tar_path.exists():
            continue
        zip_path = tar_path.with_suffix(".zip")
        if zip_path.exists():
            logger.info("Extracting %s", zip_path)
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(WEIGHTS_DIR)
        if not tar_path.exists():
            raise FileNotFoundError(
                f"Model weights not found: {tar_path}\n"
                f"Download from https://github.com/Tai-Hsien/MeshSegNet/tree/master/models"
            )


def get_model(weights_path: Path, device: str = "cpu") -> MeshSegNet:
    """Load model with cached weights."""
    key = str(weights_path)
    if key not in _model_cache:
        checkpoint = torch.load(weights_path, map_location=device, weights_only=False)
        model = MeshSegNet(num_classes=15, num_channels=15)
        model.load_state_dict(checkpoint["model_state_dict"])
        model.to(device)
        model.eval()
        _model_cache[key] = model
        logger.info("Loaded MeshSegNet from %s", weights_path)
    return _model_cache[key]


def segment_mesh(
    file_path: str | Path,
    jaw: str = "upper",
    confidence_threshold: float = 0.5,
    device: str = "cpu",
) -> dict[str, list[int]]:
    """
    Run MeshSegNet segmentation on a single STL file.

    Args:
        file_path: path to .stl file
        jaw: "upper" or "lower" — selects which model to use
        confidence_threshold: min softmax probability to assign a label
        device: "cpu" or "cuda"

    Returns:
        dict mapping label → list of face indices
        e.g. {"tooth_11": [0, 1, 2], "gingiva": [55, 56]}
    """
    _ensure_weights_extracted()

    if jaw == "upper":
        weights_path = UPPER_WEIGHTS
        class_map = UPPER_CLASS_MAP
    elif jaw == "lower":
        weights_path = LOWER_WEIGHTS
        class_map = LOWER_CLASS_MAP
    else:
        raise ValueError(f"jaw must be 'upper' or 'lower', got '{jaw}'")

    logger.info("Segmenting %s (jaw=%s)", file_path, jaw)

    # Preprocess
    X, A_S, A_L, original_num_cells = load_and_preprocess(str(file_path))
    num_cells = X.shape[1]
    logger.info("Mesh: %d faces (original: %d)", num_cells, original_num_cells)

    # To tensors: add batch dim
    X_t = torch.from_numpy(X).unsqueeze(0).to(device)        # (1, 15, N)
    A_S_t = torch.from_numpy(A_S).unsqueeze(0).to(device)    # (1, N, N)
    A_L_t = torch.from_numpy(A_L).unsqueeze(0).to(device)    # (1, N, N)

    # Inference
    model = get_model(weights_path, device=device)
    with torch.no_grad():
        probs = model(X_t, A_S_t, A_L_t)  # (1, N, 15)

    probs = probs.squeeze(0).cpu().numpy()  # (N, 15)
    predictions = probs.argmax(axis=1)      # (N,)
    confidences = probs.max(axis=1)         # (N,)

    # Group by label
    labels: dict[str, list[int]] = {}
    for face_idx in range(num_cells):
        if confidences[face_idx] < confidence_threshold:
            continue
        class_idx = int(predictions[face_idx])
        label = class_map.get(class_idx)
        if label is None:
            continue
        if label not in labels:
            labels[label] = []
        labels[label].append(face_idx)

    face_count = sum(len(v) for v in labels.values())
    logger.info("Segmentation done: %d labels, %d/%d faces", len(labels), face_count, num_cells)

    return labels
