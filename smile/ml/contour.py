"""
Smile contour extraction from MediaPipe Face Mesh landmarks.

Two contours are produced:
  - teeth_contour: the visible teeth zone bounded by inner lip edges
                   (primary contour — used for cutout mask and STL overlay)
  - lip_contour:   the full outer lip outline (secondary reference)

Contours are smoothed using scipy B-spline interpolation.
When the source image is provided, the lower lip boundary is additionally
refined using edge detection for pixel-precise teeth-to-lip alignment.
"""

import cv2
import numpy as np
from scipy import interpolate

# MediaPipe Face Mesh landmark indices for lip regions.
# These form closed polygons when connected in order.

# Outer lip — full lip boundary
OUTER_LIP_UPPER = [61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291]
OUTER_LIP_LOWER = [291, 375, 321, 405, 314, 17, 84, 181, 91, 146, 61]

# Inner lip — teeth-visible zone
INNER_LIP_UPPER = [78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308]
INNER_LIP_LOWER = [308, 324, 318, 402, 317, 14, 87, 178, 88, 95, 78]


def _smooth_contour(points: list[tuple[float, float]], num_points: int = 80) -> list[dict]:
    """
    Smooth a polygon using periodic B-spline interpolation.

    Args:
        points: list of (x, y) tuples forming a closed polygon
        num_points: number of output points

    Returns:
        list of {x, y} dicts — smooth closed contour
    """
    if len(points) < 4:
        return [{"x": round(x, 1), "y": round(y, 1)} for x, y in points]

    pts = np.array(points, dtype=np.float64)

    # Close the polygon if not already closed
    if not np.allclose(pts[0], pts[-1]):
        pts = np.vstack([pts, pts[0]])

    # Parameterize by cumulative chord length
    diffs = np.diff(pts, axis=0)
    distances = np.sqrt((diffs ** 2).sum(axis=1))
    distances = np.concatenate([[0], np.cumsum(distances)])
    total = distances[-1]
    if total == 0:
        return [{"x": round(x, 1), "y": round(y, 1)} for x, y in points]
    distances /= total

    try:
        tck_x = interpolate.splrep(distances, pts[:, 0], s=0, per=True)
        tck_y = interpolate.splrep(distances, pts[:, 1], s=0, per=True)
    except Exception:
        # Fallback: return raw points if spline fails
        return [{"x": round(x, 1), "y": round(y, 1)} for x, y in points]

    u_new = np.linspace(0, 1, num_points, endpoint=False)
    x_new = interpolate.splev(u_new, tck_x)
    y_new = interpolate.splev(u_new, tck_y)

    return [{"x": round(float(x), 1), "y": round(float(y), 1)} for x, y in zip(x_new, y_new)]


def _densify_points(
    points: list[tuple[float, float]],
    subdivisions: int = 3,
) -> list[tuple[float, float]]:
    """
    Insert linearly interpolated intermediate points between each pair
    of adjacent points for finer contour resolution before edge refinement.
    """
    if len(points) < 2 or subdivisions < 2:
        return list(points)

    result = []
    for i in range(len(points) - 1):
        x1, y1 = points[i]
        x2, y2 = points[i + 1]
        for j in range(subdivisions):
            t = j / subdivisions
            result.append((
                round(x1 + (x2 - x1) * t, 1),
                round(y1 + (y2 - y1) * t, 1),
            ))
    result.append(points[-1])
    return result


def _refine_contour_by_edges(
    image: np.ndarray,
    points: list[tuple[float, float]],
    mouth_center: tuple[float, float],
    search_radius: int = 15,
    min_gradient: float = 5.0,
) -> list[tuple[float, float]]:
    """
    Refine contour points by snapping each to the nearest strong image edge
    along the outward normal direction.

    Uses LAB L-channel (lightness) to detect the teeth-to-lip brightness
    transition.  For each point a 1D intensity profile is sampled along
    the normal; the steepest brightness descent is taken as the true edge.
    Points where no clear edge is found are left unchanged.
    """
    h, w = image.shape[:2]
    cx, cy = mouth_center
    n = len(points)

    if n < 3:
        return list(points)

    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    L = lab[:, :, 0].astype(np.float64)
    L = cv2.GaussianBlur(L, (3, 3), 0)

    refined = []
    for i in range(n):
        px, py = points[i]

        # Tangent from neighbors
        prev_i = (i - 1) % n
        next_i = (i + 1) % n
        tx = points[next_i][0] - points[prev_i][0]
        ty = points[next_i][1] - points[prev_i][1]
        t_len = np.hypot(tx, ty)

        if t_len < 1e-6:
            refined.append((px, py))
            continue

        # Outward normal (perpendicular to tangent, away from mouth center)
        nx_d = ty / t_len
        ny_d = -tx / t_len
        if nx_d * (cx - px) + ny_d * (cy - py) > 0:
            nx_d, ny_d = -nx_d, -ny_d

        # Sample 1D intensity profile along normal
        valid_steps: list[int] = []
        profile: list[float] = []
        for s in range(-search_radius, search_radius + 1):
            sx = int(round(px + nx_d * s))
            sy = int(round(py + ny_d * s))
            if 0 <= sx < w and 0 <= sy < h:
                profile.append(L[sy, sx])
                valid_steps.append(s)

        if len(profile) < 5:
            refined.append((px, py))
            continue

        profile_arr = np.array(profile)
        # Positive gradient = bright-to-dark (teeth -> lip)
        grad = -np.diff(profile_arr)

        # Prefer edges close to the original position (Gaussian proximity weight)
        center = valid_steps.index(0) if 0 in valid_steps else len(valid_steps) // 2
        sigma = search_radius * 0.6
        weight = np.exp(-0.5 * ((np.arange(len(grad)) - center) / sigma) ** 2)
        weighted = grad * weight

        best_idx = int(np.argmax(weighted))

        if grad[best_idx] > min_gradient:
            best_step = (valid_steps[best_idx] + valid_steps[best_idx + 1]) / 2
            refined.append((
                round(px + nx_d * best_step, 1),
                round(py + ny_d * best_step, 1),
            ))
        else:
            refined.append((px, py))

    return refined


def _segment_teeth_contour(
    image: np.ndarray,
    landmarks: dict,
    padding: float = 0.25,
) -> list[tuple[float, float]] | None:
    """
    Extract visible teeth contour via color segmentation.

    MediaPipe landmarks are used **only** for mouth ROI localization.
    The actual contour shape comes from image analysis, preserving real
    asymmetry caused by jaw defects, malocclusion, etc.

    Algorithm:
      1. Crop mouth ROI from lip landmarks (with generous padding).
      2. Compute teeth-likelihood score in LAB space:
         bright (high L) and not red (low a) → teeth.
      3. Otsu threshold → binary teeth mask.
      4. Constrain mask to dilated inner-lip area (avoids white skin/clothing).
      5. Morphological cleanup + largest-contour extraction.
      6. Simplify with approxPolyDP (preserves shape, removes pixel noise).

    Returns list of (x, y) in full-image coordinates, or None on failure.
    """
    h, w = image.shape[:2]

    # ── 1. Mouth ROI ──
    all_lip = set(INNER_LIP_UPPER + INNER_LIP_LOWER + OUTER_LIP_UPPER + OUTER_LIP_LOWER)
    pts = [(landmarks[i]["x"], landmarks[i]["y"]) for i in all_lip if i in landmarks]
    if len(pts) < 10:
        return None

    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    rw, rh = max(xs) - min(xs), max(ys) - min(ys)

    x1 = max(0, int(min(xs) - rw * padding))
    y1 = max(0, int(min(ys) - rh * padding))
    x2 = min(w, int(max(xs) + rw * padding))
    y2 = min(h, int(max(ys) + rh * padding))

    roi = image[y1:y2, x1:x2]
    if roi.size == 0 or min(roi.shape[:2]) < 20:
        return None

    # ── 2. Teeth-likelihood in LAB ──
    lab = cv2.cvtColor(roi, cv2.COLOR_BGR2LAB)
    L = lab[:, :, 0].astype(np.float64)
    a = lab[:, :, 1].astype(np.float64)

    score = L - 0.7 * a  # high for teeth (bright + not red)
    s_min, s_max = score.min(), score.max()
    if s_max - s_min < 1:
        return None
    score_u8 = ((score - s_min) / (s_max - s_min) * 255).astype(np.uint8)

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
    score_u8 = clahe.apply(score_u8)

    _, mask = cv2.threshold(score_u8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # ── 3. Constrain to mouth area (dilated — allows asymmetry) ──
    inner_idx = INNER_LIP_UPPER + INNER_LIP_LOWER[1:]
    inner_pts = np.array(
        [(int(landmarks[i]["x"] - x1), int(landmarks[i]["y"] - y1))
         for i in inner_idx if i in landmarks],
        dtype=np.int32,
    )
    if len(inner_pts) >= 3:
        constraint = np.zeros(mask.shape, dtype=np.uint8)
        cv2.fillPoly(constraint, [inner_pts], 255)
        dil_size = max(5, int(rw * 0.08))
        if dil_size % 2 == 0:
            dil_size += 1
        constraint = cv2.dilate(
            constraint,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dil_size, dil_size)),
            iterations=2,
        )
        mask = cv2.bitwise_and(mask, constraint)

    # ── 4. Morphological cleanup ──
    kern = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kern, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kern, iterations=1)

    # ── 5. Largest contour ──
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        return None

    largest = max(contours, key=cv2.contourArea)
    roi_area = (x2 - x1) * (y2 - y1)
    if cv2.contourArea(largest) < roi_area * 0.03:
        return None

    # ── 6. Simplify, preserving asymmetric details ──
    perimeter = cv2.arcLength(largest, True)
    epsilon = 0.006 * perimeter
    approx = cv2.approxPolyDP(largest, epsilon, True)

    if len(approx) < 8:
        return None

    return [
        (round(float(pt[0][0] + x1), 1), round(float(pt[0][1] + y1), 1))
        for pt in approx
    ]


def _snap_to_lip_edge(
    image: np.ndarray,
    points: list[tuple[float, float]],
    search_radius: int = 15,
) -> list[tuple[float, float]]:
    """
    Snap each contour point to the nearest lip-tissue boundary in 2D.

    Processes only the mouth ROI (not the full image) to avoid OOM
    on high-resolution dental photos.

    Detects the **inner lip edge** — where lip tissue (high LAB *a*,
    reddish) ends and the mouth opening begins (teeth, gums, or dark
    cavity — all have lower *a*).  This finds the lip frame of the
    smile, not individual tooth edges.

    Displacement outliers are smoothed via median filter so that
    individual points cannot jump to spurious edges.
    """
    from scipy.ndimage import median_filter as _median1d

    h, w = image.shape[:2]
    n = len(points)

    # ── crop to mouth ROI (saves ~100x memory vs full image) ──
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    pad = search_radius + 10
    roi_x1 = max(0, int(min(xs)) - pad)
    roi_y1 = max(0, int(min(ys)) - pad)
    roi_x2 = min(w, int(max(xs)) + pad)
    roi_y2 = min(h, int(max(ys)) + pad)

    roi = image[roi_y1:roi_y2, roi_x1:roi_x2]
    rh, rw = roi.shape[:2]
    if rh < 20 or rw < 20:
        return list(points)

    # ── edge map based on lip-tissue redness (LAB *a* channel) ──
    # Lip tissue has distinctly high *a* (red); teeth, gums, and
    # dark mouth interior all have lower *a*.  Canny on *a* finds
    # exactly the inner lip boundary.
    lab = cv2.cvtColor(roi, cv2.COLOR_BGR2LAB)
    a_ch = lab[:, :, 1]  # uint8, center ~128
    del lab

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    a_enhanced = clahe.apply(a_ch)
    del a_ch

    edges = cv2.Canny(a_enhanced, 50, 130)
    grad_mag = (np.abs(cv2.Sobel(a_enhanced, cv2.CV_64F, 1, 0, ksize=3))
                + np.abs(cv2.Sobel(a_enhanced, cv2.CV_64F, 0, 1, ksize=3)))
    del a_enhanced

    # ── find best edge for every point (ROI coordinates) ──
    dx_arr = np.zeros(n)
    dy_arr = np.zeros(n)

    for i, (px, py) in enumerate(points):
        # full-image → ROI coordinates
        rx, ry = px - roi_x1, py - roi_y1
        ix, iy = int(round(rx)), int(round(ry))

        y_lo = max(0, iy - search_radius)
        y_hi = min(rh, iy + search_radius + 1)
        x_lo = max(0, ix - search_radius)
        x_hi = min(rw, ix + search_radius + 1)

        local_edges = edges[y_lo:y_hi, x_lo:x_hi]
        ey, ex = np.where(local_edges > 0)

        if len(ex) == 0:
            continue

        gx = (ex + x_lo).astype(np.float64)
        gy = (ey + y_lo).astype(np.float64)

        dist_sq = (gx - rx) ** 2 + (gy - ry) ** 2
        sigma = search_radius * 0.6
        proximity = np.exp(-dist_sq / (2 * sigma ** 2))
        strength = np.array([grad_mag[int(y), int(x)] for x, y in zip(gx, gy)])

        score = strength * proximity
        best = int(np.argmax(score))

        if dist_sq[best] <= search_radius ** 2:
            dx_arr[i] = gx[best] - rx
            dy_arr[i] = gy[best] - ry

    # ── smooth displacements to reject outlier snaps ──
    dx_smooth = _median1d(dx_arr, size=5, mode="wrap")
    dy_smooth = _median1d(dy_arr, size=5, mode="wrap")

    return [
        (round(points[i][0] + dx_smooth[i], 1),
         round(points[i][1] + dy_smooth[i], 1))
        for i in range(n)
    ]


def extract_smile_contour(
    landmarks: dict,
    image: np.ndarray | None = None,
    smooth: bool = True,
    num_points: int = 80,
) -> tuple[list[dict], list[dict]]:
    """
    Extract teeth and lip contours from face landmarks.

    Step 1 — base contour from MediaPipe landmarks (reliable shape).
    Step 2 — if *image* is provided, densify and snap every point
             to the nearest real lip-teeth edge in 2D, capturing
             asymmetry that the landmark mesh may miss.

    Args:
        landmarks: dict from detect_face_landmarks() — {idx: {x, y, z}}
        image: BGR numpy array — enables edge-based refinement
        smooth: whether to apply B-spline smoothing
        num_points: number of points in smoothed contour

    Returns:
        (teeth_contour, lip_contour)
    """
    def _get_points(indices):
        return [(landmarks[i]["x"], landmarks[i]["y"]) for i in indices if i in landmarks]

    # ── Step 1: base contour from landmarks ──
    teeth_points = _get_points(INNER_LIP_UPPER) + _get_points(INNER_LIP_LOWER[1:])

    # ── Step 2: refine all points by snapping to real edges ──
    if image is not None and len(teeth_points) >= 6:
        mouth_xs = [p[0] for p in teeth_points]
        mouth_width = max(mouth_xs) - min(mouth_xs)
        search_r = max(5, int(mouth_width * 0.06))

        dense = _densify_points(teeth_points, subdivisions=3)
        teeth_points = _snap_to_lip_edge(image, dense, search_radius=search_r)

    # ── Lip contour (outer, landmark-based) ──
    lip_points = _get_points(OUTER_LIP_UPPER) + _get_points(OUTER_LIP_LOWER[1:])

    if smooth:
        teeth_num = max(num_points, len(teeth_points))
        teeth_contour = _smooth_contour(teeth_points, teeth_num)
        lip_contour = _smooth_contour(lip_points, num_points)
    else:
        teeth_contour = [{"x": round(x, 1), "y": round(y, 1)} for x, y in teeth_points]
        lip_contour = [{"x": round(x, 1), "y": round(y, 1)} for x, y in lip_points]

    return teeth_contour, lip_contour


def draw_contour_on_image(
    image: np.ndarray,
    teeth_contour: list[dict],
    lip_contour: list[dict],
) -> np.ndarray:
    """
    Draw smile contours on an image copy.

    Args:
        image: BGR numpy array (OpenCV format)
        teeth_contour: list of {x, y} — primary teeth zone contour
        lip_contour: list of {x, y} — secondary lip boundary

    Returns:
        BGR image with contours drawn
    """
    result = image.copy()

    # Lip contour — thin, secondary reference
    if lip_contour:
        pts = np.array([(int(p["x"]), int(p["y"])) for p in lip_contour], dtype=np.int32)
        cv2.polylines(result, [pts], isClosed=True, color=(0, 200, 0), thickness=1)

    # Teeth contour — thick, primary
    if teeth_contour:
        pts = np.array([(int(p["x"]), int(p["y"])) for p in teeth_contour], dtype=np.int32)
        cv2.polylines(result, [pts], isClosed=True, color=(0, 255, 255), thickness=2)

    return result
