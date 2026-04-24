"""
Preprocessing: STL file → features + adjacency matrices.

Replicates the exact preprocessing from the original MeshSegNet repo:
https://github.com/Tai-Hsien/MeshSegNet/blob/master/step5_predict.py

Features per face (15D):
  [0:9]   3 vertex coordinates flattened (z-score normalized)
  [9:12]  barycenter (min-max normalized to [0,1])
  [12:15] face normal (z-score normalized)

Adjacency matrices:
  A_S — small radius (d < 0.1), row-normalized
  A_L — large radius (d < 0.2), row-normalized
"""

import numpy as np
import trimesh
from scipy.spatial import distance_matrix


TARGET_NUM_CELLS = 10000


def load_and_preprocess(
    file_path: str,
    target_cells: int = TARGET_NUM_CELLS,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, int]:
    """
    Load STL, downsample, compute features and adjacency matrices.

    Returns:
        X:   (15, N) features
        A_S: (N, N) small-radius adjacency
        A_L: (N, N) large-radius adjacency
        original_num_cells: face count before downsampling
    """
    mesh = trimesh.load(file_path, file_type="stl", force="mesh")
    if not isinstance(mesh, trimesh.Trimesh):
        raise ValueError(f"Could not load mesh from {file_path}")

    original_num_cells = len(mesh.faces)

    # Downsample if needed
    if len(mesh.faces) > target_cells:
        try:
            mesh = mesh.simplify_quadric_decimation(target_cells)
        except (ImportError, Exception):
            # Fallback: random face sampling (no fast-simplification)
            selected = np.sort(np.random.choice(len(mesh.faces), target_cells, replace=False))
            mesh = mesh.submesh([selected], append=True)

    num_cells = len(mesh.faces)

    # Move mesh to origin (center of mass)
    points = mesh.vertices.copy()
    mean_center = mesh.triangles_center.mean(axis=0)
    points -= mean_center

    # Vertex coordinates per face: 3 vertices × 3 coords = 9 values
    cells = points[mesh.faces].reshape(num_cells, 9).astype(np.float32)

    # Face normals
    normals = mesh.face_normals.copy().astype(np.float32)

    # Barycenters (centered)
    barycenters = mesh.triangles_center.copy().astype(np.float32)
    barycenters -= mean_center

    # Normalization
    means = points.mean(axis=0)
    stds = points.std(axis=0)
    stds[stds == 0] = 1.0  # avoid division by zero

    maxs = points.max(axis=0)
    mins = points.min(axis=0)
    ranges = maxs - mins
    ranges[ranges == 0] = 1.0

    nmeans = normals.mean(axis=0)
    nstds = normals.std(axis=0)
    nstds[nstds == 0] = 1.0

    # Z-score normalize vertex coords (3 vertices × 3 axes)
    for i in range(3):
        cells[:, i] = (cells[:, i] - means[i]) / stds[i]
        cells[:, i + 3] = (cells[:, i + 3] - means[i]) / stds[i]
        cells[:, i + 6] = (cells[:, i + 6] - means[i]) / stds[i]

    # Min-max normalize barycenters to [0, 1]
    for i in range(3):
        barycenters[:, i] = (barycenters[:, i] - mins[i]) / ranges[i]

    # Z-score normalize normals
    for i in range(3):
        normals[:, i] = (normals[:, i] - nmeans[i]) / nstds[i]

    # Stack: (N, 15)
    X = np.column_stack([cells, barycenters, normals]).astype(np.float32)

    # Adjacency matrices from barycenter distances
    # Barycenters are columns [9:12] of X
    D = distance_matrix(X[:, 9:12], X[:, 9:12])

    A_S = np.zeros((num_cells, num_cells), dtype=np.float32)
    A_S[D < 0.1] = 1.0
    row_sums = A_S.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1.0
    A_S /= row_sums

    A_L = np.zeros((num_cells, num_cells), dtype=np.float32)
    A_L[D < 0.2] = 1.0
    row_sums = A_L.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1.0
    A_L /= row_sums

    # Transpose X to (15, N) for model input
    X = X.T

    return X, A_S, A_L, original_num_cells
