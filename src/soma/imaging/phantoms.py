"""Analytic physical-coordinate phantoms; independent of registration and meshing."""

import numpy as np
from scipy.spatial.transform import Rotation

from soma.geometry import Frame, Transform
from soma.imaging.volumes import Volume

LANDMARKS_M = np.array(
    [
        [-0.018, -0.009, 0.012],
        [0.013, 0.016, -0.008],
        [0.018, -0.017, 0.016],
        [-0.006, 0.019, 0.019],
    ]
)


def grid(
    spacing_m: tuple[float, float, float] = (0.002, 0.002, 0.002), extent_m: float = 0.096
) -> Volume:
    shape = tuple(round(extent_m / step) + 1 for step in spacing_m)
    a = np.diag([*spacing_m, 1.0])
    a[:3, 3] = -(np.array(shape) - 1) * np.array(spacing_m) / 2
    return Volume(np.zeros(shape, dtype=np.float32), a, metadata={"origin": "synthetic"})


def coordinates(volume: Volume) -> np.ndarray:
    indices = np.moveaxis(np.indices(volume.shape, dtype=float), 0, -1)
    return indices @ volume.affine_m[:3, :3].T + volume.affine_m[:3, 3]


def asymmetric(
    spacing_m: tuple[float, float, float] = (0.002, 0.002, 0.002),
    *,
    seed: int = 42,
    noise: float = 0,
    bias: float = 0,
    blur_sigma_m: float = 0,
) -> Volume:
    reference = grid(spacing_m)
    xyz = coordinates(reference)
    data = np.zeros(reference.shape)
    for center, widths, intensity in zip(
        LANDMARKS_M,
        (
            (0.008, 0.005, 0.007),
            (0.006, 0.009, 0.005),
            (0.004, 0.005, 0.008),
            (0.005, 0.004, 0.006),
        ),
        (1.0, 0.7, 0.45, 0.9),
        strict=True,
    ):
        data += intensity * np.exp(-0.5 * np.sum(((xyz - center) / widths) ** 2, axis=-1))
    if blur_sigma_m < 0:
        raise ValueError("Blur must be nonnegative metres")
    if blur_sigma_m:
        from scipy.ndimage import gaussian_filter

        data = gaussian_filter(data, blur_sigma_m / np.asarray(spacing_m))
    data *= 1 + bias * xyz[..., 0] / 0.048
    data += np.random.default_rng(seed).normal(0, noise, data.shape)
    return Volume(
        data.astype(np.float32),
        reference.affine_m,
        metadata={
            "origin": "synthetic_asymmetric_Gaussians",
            "seed": seed,
            "noise": noise,
            "bias": bias,
            "blur_sigma_m": blur_sigma_m,
            "landmarks_m": LANDMARKS_M.tolist(),
        },
    )


def sphere(radius_m: float = 0.03, spacing_m: float = 0.002) -> Volume:
    reference = grid((spacing_m,) * 3, extent_m=0.12)
    mask = np.linalg.norm(coordinates(reference), axis=-1) <= radius_m
    return Volume(
        mask.astype(np.uint8),
        reference.affine_m,
        "labels",
        {"origin": "synthetic_sphere", "radius_m": radius_m},
    )


def ellipsoid(spacing_m: float = 0.002) -> Volume:
    reference = grid((spacing_m,) * 3, extent_m=0.12)
    rotation = Rotation.from_euler("xyz", [13, -17, 24], degrees=True).as_matrix()
    xyz = coordinates(reference) @ rotation
    mask = np.sum((xyz / [0.035, 0.025, 0.018]) ** 2, axis=-1) <= 1
    return Volume(
        mask.astype(np.uint8),
        reference.affine_m,
        "labels",
        {"origin": "synthetic_rotated_ellipsoid", "radii_m": [0.035, 0.025, 0.018]},
    )


def known_transform(mode: str = "rigid", magnitude: float = 1) -> Transform:
    a = np.eye(4)
    a[:3, :3] = Rotation.from_euler(
        "xyz", np.array([2.0, -3.0, 4.0]) * magnitude, degrees=True
    ).as_matrix()
    if mode == "affine":
        a[:3, :3] = a[:3, :3] @ np.array(
            [
                [1 + 0.03 * magnitude, 0.02 * magnitude, 0],
                [0, 1 - 0.025 * magnitude, 0.01 * magnitude],
                [0, 0, 1 + 0.02 * magnitude],
            ]
        )
    elif mode != "rigid":
        raise ValueError("Unknown phantom transform")
    a[:3, 3] = np.array([0.002, -0.0015, 0.001]) * magnitude
    return Transform(Frame.RAS, Frame.RAS, a, rigid=mode == "rigid")


def analytic_sphere_field(spacing_m: float = 0.002, radius_m: float = 0.03) -> Volume:
    reference = grid((spacing_m,) * 3, extent_m=0.12)
    return Volume(
        (radius_m - np.linalg.norm(coordinates(reference), axis=-1)).astype(np.float32),
        reference.affine_m,
        metadata={"origin": "analytic_sphere_signed_distance", "radius_m": radius_m},
    )


def transformed_asymmetric(reference: Volume, truth: Transform) -> Volume:
    """Sample the analytic moving field directly, without the production resampler."""
    xyz = coordinates(reference)
    fixed_xyz = (xyz - truth.matrix[:3, 3]) @ np.linalg.solve(truth.matrix[:3, :3], np.eye(3)).T
    data = np.zeros(reference.shape)
    for center, widths, intensity in zip(
        LANDMARKS_M,
        (
            (0.008, 0.005, 0.007),
            (0.006, 0.009, 0.005),
            (0.004, 0.005, 0.008),
            (0.005, 0.004, 0.006),
        ),
        (1.0, 0.7, 0.45, 0.9),
        strict=True,
    ):
        data += intensity * np.exp(-0.5 * np.sum(((fixed_xyz - center) / widths) ** 2, axis=-1))
    return Volume(
        data.astype(np.float32),
        reference.affine_m,
        metadata={
            "origin": "independently_evaluated_transformed_Gaussians",
            "truth_fixed_to_moving_RAS_m": truth.matrix.tolist(),
        },
    )
