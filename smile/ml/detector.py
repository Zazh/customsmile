"""
Face landmark detection using MediaPipe Face Mesh.

MediaPipe ships with pre-trained models inside the pip package —
no separate weight files needed. Just `pip install mediapipe`.

Returns 478 face landmarks with pixel coordinates.
"""

import logging

import cv2
import mediapipe as mp
import numpy as np

logger = logging.getLogger(__name__)


def detect_face_landmarks(image_path: str) -> dict[int, dict]:
    """
    Detect face landmarks from a photo.

    Args:
        image_path: path to the image file

    Returns:
        Dict mapping landmark index to {x, y, z} in pixel coordinates.
        z is relative depth (normalized, not in pixels).

    Raises:
        ValueError: if no face detected or image can't be loaded
    """
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"Cannot load image: {image_path}")

    h, w = image.shape[:2]
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    face_mesh = mp.solutions.face_mesh.FaceMesh(
        static_image_mode=True,
        max_num_faces=1,
        refine_landmarks=True,  # enables iris landmarks (468-477)
        min_detection_confidence=0.5,
    )

    try:
        results = face_mesh.process(rgb)
    finally:
        face_mesh.close()

    if not results.multi_face_landmarks:
        raise ValueError("No face detected in the image")

    face = results.multi_face_landmarks[0]
    landmarks = {}
    for idx, lm in enumerate(face.landmark):
        landmarks[idx] = {
            "x": round(lm.x * w, 1),
            "y": round(lm.y * h, 1),
            "z": round(lm.z, 6),
        }

    logger.info("Detected %d landmarks in %s", len(landmarks), image_path)
    return landmarks


def get_landmark_points(landmarks: dict, indices: list[int]) -> list[tuple[float, float]]:
    """Extract (x, y) points for given landmark indices."""
    return [(landmarks[i]["x"], landmarks[i]["y"]) for i in indices if i in landmarks]
