"""Known nested-sphere BEMs and an independent analytical conductor reference."""

from pathlib import Path
from typing import Any

import mne
import numpy as np
from scipy.spatial import ConvexHull

from soma.anatomy.cache import cached_object
from soma.anatomy.surfaces import ConductorSurfaces
from soma.geometry import Frame, Transform
from soma.source.noise import average_projector


def _subdivide(vertices: Any, faces: Any) -> tuple[Any, Any]:
    cache: dict[tuple[int, ...], int] = {}
    points = vertices.tolist()
    triangles = []

    def midpoint(i: int, j: int) -> int:
        key = tuple(sorted((int(i), int(j))))
        if key not in cache:
            point = vertices[i] + vertices[j]
            point /= np.linalg.norm(point)
            cache[key] = len(points)
            points.append(point.tolist())
        return cache[key]

    for a, b, c in faces:
        ab, bc, ca = midpoint(a, b), midpoint(b, c), midpoint(c, a)
        triangles.extend([(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)])
    vertices = np.asarray(points)
    faces = np.asarray(triangles, dtype=int)
    return vertices, faces


def sphere_mesh(subdivisions: int, radius_m: float) -> tuple[Any, Any]:
    if subdivisions not in (0, 1, 2, 3) or radius_m <= 0:
        raise ValueError("Bounded icosphere subdivision and positive radius required")
    phi = (1 + np.sqrt(5)) / 2
    vertices = np.array(
        [(0, a, b * phi) for a in (-1, 1) for b in (-1, 1)]
        + [(a, b * phi, 0) for a in (-1, 1) for b in (-1, 1)]
        + [(a * phi, 0, b) for a in (-1, 1) for b in (-1, 1)],
        dtype=float,
    )
    vertices /= np.linalg.norm(vertices, axis=1)[:, None]
    faces = ConvexHull(vertices).simplices
    for _ in range(subdivisions):
        vertices, faces = _subdivide(vertices, faces)
    tri = vertices[faces]
    outward = np.einsum(
        "ij,ij->i", np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), tri.mean(axis=1)
    )
    faces = faces.copy()
    faces[outward < 0] = faces[outward < 0][:, [0, 2, 1]]
    return vertices * radius_m, faces


def synthetic_info(n: int = 24) -> Any:
    z = np.linspace(0.1, 0.95, n)
    angle = np.arange(n) * np.pi * (3 - np.sqrt(5))
    radius = np.sqrt(1 - z * z)
    xyz = 0.09 * np.column_stack([radius * np.cos(angle), radius * np.sin(angle), z])
    names = [f"EEG{i + 1:03d}" for i in range(n)]
    info = mne.create_info(names, 160, "eeg")
    info.set_montage(
        mne.channels.make_dig_montage(
            ch_pos=dict(zip(names, xyz, strict=True)),
            coord_frame="head",
            nasion=[0, 0.09, 0],
            lpa=[-0.09, 0, 0],
            rpa=[0.09, 0, 0],
        )
    )
    raw = mne.io.RawArray(np.zeros((n, 2)), info, verbose=False)
    raw.set_eeg_reference("average", projection=True, verbose=False)
    return raw.info


def sphere_surfaces(
    subdivisions: int = 2, conductivities: tuple[float, float, float] = (0.3, 0.006, 0.3)
) -> ConductorSurfaces:
    surfaces = []
    # MNE numerical solver consumes scalp -> skull -> brain order.
    for identity, radius, sigma in zip((4, 3, 1), (0.09, 0.085, 0.08), conductivities, strict=True):
        xyz, faces = sphere_mesh(subdivisions, radius)
        surface = {
            "id": identity,
            "sigma": sigma,
            "coord_frame": 5,
            "rr": xyz,
            "tris": faces,
            "np": len(xyz),
            "ntri": len(faces),
        }
        surface = mne.surface.complete_surface_info(surface, copy=True, verbose=False)
        surfaces.append(surface)
    return ConductorSurfaces.from_mne(
        "synthetic-sphere",
        surfaces,
        {
            "origin": "analytic concentric spheres",
            "radii_inner_to_outer_m": [0.08, 0.085, 0.09],
            "subdivisions": subdivisions,
        },
    )


def discrete_sources(points_m: Any) -> Any:
    points = np.asarray(points_m, dtype=float)
    return mne.setup_volume_source_space(
        pos={"rr": points, "nn": np.tile([0.0, 0, 1], (len(points), 1))},
        sphere=(0.0, 0.0, 0.0, 0.08),
        add_interpolator=False,
        verbose=False,
    )


def sphere_forward(
    points_m: Any,
    *,
    subdivisions: int = 2,
    conductivities: tuple[float, float, float] = (0.3, 0.006, 0.3),
    transform: Transform | None = None,
    info: Any = None,
    analytical: bool = False,
) -> tuple[Any, dict[str, Any]]:
    selected = synthetic_info() if info is None else info
    t = transform or Transform(Frame.HEAD, Frame.MRI, np.eye(4))
    src = discrete_sources(points_m)
    if analytical:
        if not np.allclose(t.matrix, np.eye(4)):
            raise ValueError("Analytical sphere reference uses known coincident synthetic frames")
        conductor = mne.make_sphere_model(
            r0=(0.0, 0.0, 0.0),
            head_radius=0.09,
            relative_radii=(0.08 / 0.09, 0.085 / 0.09, 1.0),
            sigmas=tuple(reversed(conductivities)),
            verbose=False,
        )
        receipt = {
            "analytical": True,
            "model": "MNE layered-sphere analytical EEG reference, not BEM",
            "conductivities_scalp_skull_brain": conductivities,
        }
    else:
        surfaces = sphere_surfaces(subdivisions, conductivities)
        parameters = {
            "subdivisions": subdivisions,
            "radii_m": [0.08, 0.085, 0.09],
            "conductivities_scalp_skull_brain": list(conductivities),
            "mne": mne.__version__,
            "code": __import__("soma.core.provenance", fromlist=["sha256"]).sha256(Path(__file__)),
        }
        conductor, receipt = cached_object(
            Path("data/derived/individual-synthetic"),
            "sphere-conductor",
            parameters,
            "-bem-sol.fif",
            lambda: mne.make_bem_solution(list(reversed(surfaces.native)), verbose=False),
            lambda p: mne.read_bem_solution(p, verbose=False),
            lambda p, x: mne.write_bem_solution(p, x, overwrite=False, verbose=False),
        )
    native = mne.make_forward_solution(
        selected,
        trans=t.to_mne(),
        src=src,
        bem=conductor,
        meg=False,
        eeg=True,
        mindist=0,
        n_jobs=1,
        verbose=False,
    )
    expected = np.asarray(points_m)
    returned = native["source_rr"] @ t.matrix[:3, :3].T + t.matrix[:3, 3]
    if not np.allclose(returned, expected, atol=1e-9):
        raise ValueError("Synthetic source correspondence changed")
    cartesian = np.asarray(native["sol"]["data"]).reshape(
        len(selected["ch_names"]), len(points_m), 3
    )
    # Compare physical MRI Cartesian currents, not head bases rotated differently.
    mri_basis = np.einsum("cni,ij->cnj", cartesian, np.linalg.inv(t.matrix[:3, :3]))
    matrix = average_projector(len(selected["ch_names"])) @ mri_basis.reshape(
        len(selected["ch_names"]), -1
    )
    return matrix, {
        "conductor": receipt,
        "source_MRI_m": expected.tolist(),
        "orientation": "free Cartesian MRI x/y/z per identified source",
        "head_to_MRI_m": t.matrix.tolist(),
        "channels": selected["ch_names"],
    }
