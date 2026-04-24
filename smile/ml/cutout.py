"""
Smile cutout: create masked and cutout images from contour polygons.

Produces two RGBA PNG images:
  - cutout:  only the smile region on a transparent background
  - masked:  original photo with the smile area made transparent
             (ready for STL overlay in the next phase)
"""

import cv2
import numpy as np


def create_smile_cutout(
    image: np.ndarray,
    outer_contour: list[dict],
    feather_radius: int = 5,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Create cutout and masked images from smile contour.

    Args:
        image: BGR numpy array (original photo)
        outer_contour: list of {x, y} defining the smile polygon
        feather_radius: Gaussian blur radius for edge feathering (px)

    Returns:
        (cutout_rgba, masked_rgba) — both RGBA numpy arrays
        - cutout_rgba: smile region on transparent background
        - masked_rgba: original with smile area transparent
    """
    h, w = image.shape[:2]

    # Build polygon mask
    pts = np.array(
        [(int(p["x"]), int(p["y"])) for p in outer_contour],
        dtype=np.int32,
    )
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.fillPoly(mask, [pts], 255)

    # Feather edges for smooth blending
    if feather_radius > 0:
        ksize = feather_radius * 2 + 1
        mask = cv2.GaussianBlur(mask, (ksize, ksize), 0)

    # Convert source to RGBA
    rgba = cv2.cvtColor(image, cv2.COLOR_BGR2BGRA)

    # Cutout: smile only on transparent background
    cutout = np.zeros_like(rgba)
    cutout[:, :, :3] = image
    cutout[:, :, 3] = mask

    # Masked: original with smile area transparent (inverted mask)
    masked = rgba.copy()
    masked[:, :, 3] = 255 - mask

    return cutout, masked
