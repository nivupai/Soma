import numpy as np

from soma.anatomy.fs_skull import voxelize
from soma.geometry import Frame, Points
from soma.imaging.surfaces import Mesh
from soma.imaging.volumes import Volume


def _icosphere(radius_m: float, subdivisions: int = 3) -> Mesh:
    t = (1 + 5**0.5) / 2
    v = [
        [-1, t, 0],
        [1, t, 0],
        [-1, -t, 0],
        [1, -t, 0],
        [0, -1, t],
        [0, 1, t],
        [0, -1, -t],
        [0, 1, -t],
        [t, 0, -1],
        [t, 0, 1],
        [-t, 0, -1],
        [-t, 0, 1],
    ]
    f = [
        [0, 11, 5],
        [0, 5, 1],
        [0, 1, 7],
        [0, 7, 10],
        [0, 10, 11],
        [1, 5, 9],
        [5, 11, 4],
        [11, 10, 2],
        [10, 7, 6],
        [7, 1, 8],
        [3, 9, 4],
        [3, 4, 2],
        [3, 2, 6],
        [3, 6, 8],
        [3, 8, 9],
        [4, 9, 5],
        [2, 4, 11],
        [6, 2, 10],
        [8, 6, 7],
        [9, 8, 1],
    ]
    verts = [np.array(x, float) / np.linalg.norm(x) for x in v]
    faces = f
    for _ in range(subdivisions):
        cache: dict[tuple[int, int], int] = {}

        def mid(a: int, b: int, cache: dict[tuple[int, int], int] = cache) -> int:
            key = (min(a, b), max(a, b))
            if key not in cache:
                m = verts[a] + verts[b]
                verts.append(m / np.linalg.norm(m))
                cache[key] = len(verts) - 1
            return cache[key]

        new = []
        for a, b, c in faces:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            new += [[a, ab, ca], [b, bc, ab], [c, ca, bc], [ab, bc, ca]]
        faces = new
    return Mesh(Points(np.array(verts) * radius_m, Frame.RAS), np.array(faces, dtype=np.int64))


def test_voxelize_sphere_volume_and_lps_grid() -> None:
    shape = (60, 60, 60)
    a = np.diag([-0.001, -0.001, 0.001, 1.0])  # LPS-stored 1 mm grid like SynthRAD
    a[:3, 3] = -a[:3, :3] @ ((np.asarray(shape) - 1) / 2)
    like = Volume(np.zeros(shape, np.float32), a)
    mask = voxelize(_icosphere(0.02), like)
    expected = 4 / 3 * np.pi * 20**3
    assert abs(mask.sum() - expected) / expected < 0.04
    assert mask[30, 30, 30] and not mask[0, 0, 0]
