"""
Dental guideline computation from MediaPipe Face Mesh landmarks.

Guidelines are reference lines used by clinicians to evaluate and plan
smile corrections:

  - facial_midline:   vertical line through forehead → nose → chin
  - interpupillary:   horizontal reference between iris centers
  - smile_arc:        curve following the incisal edges of upper teeth
  - upper_lip_line:   curve of the upper lip at maximum smile
  - buccal_corridors: negative space between teeth and cheeks
"""

import numpy as np


# Key MediaPipe landmark indices
_FOREHEAD = 10
_NOSE_TIP = 1
_CHIN = 152
_LEFT_IRIS = 468    # requires refine_landmarks=True
_RIGHT_IRIS = 473
_LEFT_MOUTH_CORNER = 61
_RIGHT_MOUTH_CORNER = 291

# Inner upper lip — follows incisal edge of upper teeth
_SMILE_ARC_INDICES = [78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308]

# Upper lip line (outer)
_UPPER_LIP_INDICES = [61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291]


def compute_guidelines(landmarks: dict, image_shape: tuple[int, int]) -> dict:
    """
    Compute dental guidelines from face landmarks.

    Args:
        landmarks: {idx: {x, y, z}} from detector
        image_shape: (height, width) of the image

    Returns:
        Dict with guideline definitions:
        {
            "facial_midline": {"start": {x, y}, "end": {x, y}},
            "interpupillary": {"start": {x, y}, "end": {x, y}},
            "smile_arc": [{x, y}, ...],
            "upper_lip_line": [{x, y}, ...],
            "buccal_corridors": {"left": {x, y, w}, "right": {x, y, w}},
        }
    """
    h, w = image_shape

    def _pt(idx):
        lm = landmarks.get(idx)
        if lm is None:
            return None
        return {"x": round(lm["x"], 1), "y": round(lm["y"], 1)}

    def _pts(indices):
        return [_pt(i) for i in indices if _pt(i) is not None]

    result = {}

    # ── Facial midline ──
    forehead = _pt(_FOREHEAD)
    chin = _pt(_CHIN)
    if forehead and chin:
        # Extend the line to span full image height for visual reference
        dx = chin["x"] - forehead["x"]
        dy = chin["y"] - forehead["y"]
        if dy != 0:
            scale_top = -forehead["y"] / dy
            scale_bottom = (h - forehead["y"]) / dy
            result["facial_midline"] = {
                "start": {
                    "x": round(forehead["x"] + dx * scale_top, 1),
                    "y": 0,
                },
                "end": {
                    "x": round(forehead["x"] + dx * scale_bottom, 1),
                    "y": float(h),
                },
            }
        else:
            result["facial_midline"] = {"start": forehead, "end": chin}

    # ── Interpupillary line ──
    left_iris = _pt(_LEFT_IRIS)
    right_iris = _pt(_RIGHT_IRIS)
    if left_iris and right_iris:
        # Extend horizontally across the image
        dx = right_iris["x"] - left_iris["x"]
        dy = right_iris["y"] - left_iris["y"]
        if dx != 0:
            scale_left = -left_iris["x"] / dx
            scale_right = (w - left_iris["x"]) / dx
            result["interpupillary"] = {
                "start": {
                    "x": 0,
                    "y": round(left_iris["y"] + dy * scale_left, 1),
                },
                "end": {
                    "x": float(w),
                    "y": round(left_iris["y"] + dy * scale_right, 1),
                },
            }
        else:
            result["interpupillary"] = {"start": left_iris, "end": right_iris}

    # ── Smile arc (incisal edge curve) ──
    smile_arc = _pts(_SMILE_ARC_INDICES)
    if smile_arc:
        result["smile_arc"] = smile_arc

    # ── Upper lip line ──
    upper_lip = _pts(_UPPER_LIP_INDICES)
    if upper_lip:
        result["upper_lip_line"] = upper_lip

    # ── Buccal corridors ──
    # Estimated as the gap between mouth corners and the last visible teeth.
    # The inner lip corners (78 = left, 308 = right) approximate teeth extent.
    left_corner = _pt(_LEFT_MOUTH_CORNER)
    right_corner = _pt(_RIGHT_MOUTH_CORNER)
    left_teeth_edge = _pt(78)
    right_teeth_edge = _pt(308)

    if all([left_corner, right_corner, left_teeth_edge, right_teeth_edge]):
        # Width of corridor = distance from mouth corner to last tooth
        left_width = abs(left_corner["x"] - left_teeth_edge["x"])
        right_width = abs(right_corner["x"] - right_teeth_edge["x"])
        mid_y = (left_corner["y"] + right_corner["y"]) / 2

        result["buccal_corridors"] = {
            "left": {
                "x": round(left_corner["x"], 1),
                "y": round(mid_y, 1),
                "width": round(left_width, 1),
            },
            "right": {
                "x": round(right_corner["x"], 1),
                "y": round(mid_y, 1),
                "width": round(right_width, 1),
            },
        }

    return result


def draw_guidelines_on_image(image, guidelines: dict) -> "np.ndarray":
    """
    Draw guidelines on an image copy.

    Args:
        image: BGR numpy array
        guidelines: dict from compute_guidelines()

    Returns:
        BGR image with guidelines drawn
    """
    import cv2

    result = image.copy()

    # Facial midline — cyan dashed
    midline = guidelines.get("facial_midline")
    if midline:
        p1 = (int(midline["start"]["x"]), int(midline["start"]["y"]))
        p2 = (int(midline["end"]["x"]), int(midline["end"]["y"]))
        _draw_dashed_line(result, p1, p2, color=(255, 255, 0), thickness=2)

    # Interpupillary — magenta dashed
    ipd = guidelines.get("interpupillary")
    if ipd:
        p1 = (int(ipd["start"]["x"]), int(ipd["start"]["y"]))
        p2 = (int(ipd["end"]["x"]), int(ipd["end"]["y"]))
        _draw_dashed_line(result, p1, p2, color=(255, 0, 255), thickness=1)

    # Smile arc — yellow solid
    arc = guidelines.get("smile_arc")
    if arc and len(arc) > 1:
        pts = [(int(p["x"]), int(p["y"])) for p in arc]
        for i in range(len(pts) - 1):
            cv2.line(result, pts[i], pts[i + 1], color=(0, 255, 255), thickness=2)

    # Upper lip line — green solid
    lip = guidelines.get("upper_lip_line")
    if lip and len(lip) > 1:
        pts = [(int(p["x"]), int(p["y"])) for p in lip]
        for i in range(len(pts) - 1):
            cv2.line(result, pts[i], pts[i + 1], color=(0, 200, 0), thickness=1)

    # Buccal corridors — red rectangles
    bc = guidelines.get("buccal_corridors")
    if bc:
        for side in ("left", "right"):
            info = bc.get(side)
            if info:
                x, y, bw = int(info["x"]), int(info["y"]), int(info["width"])
                if side == "left":
                    cv2.rectangle(result, (x - bw, y - 15), (x, y + 15), (0, 0, 255), 2)
                else:
                    cv2.rectangle(result, (x, y - 15), (x + bw, y + 15), (0, 0, 255), 2)

    return result


def _draw_dashed_line(img, p1, p2, color, thickness=1, dash_length=10):
    """Draw a dashed line between two points."""
    import cv2

    x1, y1 = p1
    x2, y2 = p2
    dist = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
    if dist == 0:
        return
    dashes = int(dist / dash_length)
    for i in range(0, dashes, 2):
        t1 = i / dashes
        t2 = min((i + 1) / dashes, 1.0)
        start = (int(x1 + (x2 - x1) * t1), int(y1 + (y2 - y1) * t1))
        end = (int(x1 + (x2 - x1) * t2), int(y1 + (y2 - y1) * t2))
        cv2.line(img, start, end, color, thickness)
