"""SimpleITK rigid/affine registration with explicit fixed→moving RAS metres."""

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

import numpy as np
import SimpleITK as sitk

from soma.geometry import Frame, Transform
from soma.imaging.resampling import resample
from soma.imaging.volumes import Volume

_FLIP = np.diag([-1.0, -1, 1])


def to_sitk(volume: Volume, *, normalize: bool = False) -> Any:
    spacing = volume.spacing_m
    direction = volume.affine_m[:3, :3] / spacing
    if not np.allclose(direction.T @ direction, np.eye(3), atol=1e-6):
        raise ValueError(
            "SimpleITK grids require orthogonal directions; explicitly resample sheared grids"
        )
    data = volume.array(np.float32 if normalize else None)
    if not data.dtype.isnative:
        data = data.astype(data.dtype.newbyteorder("="))
    if not np.isfinite(data).all():
        raise ValueError("Registration data must be finite")
    if normalize:
        std = float(np.std(data))
        if std < 1e-8:
            raise ValueError("Constant/ambiguous intensity image cannot be registered")
        data = (data - np.mean(data)) / std
    image = sitk.GetImageFromArray(data.transpose(2, 1, 0))
    image.SetSpacing(tuple(spacing * 1000))
    image.SetOrigin(tuple(_FLIP @ volume.affine_m[:3, 3] * 1000))
    image.SetDirection(tuple((_FLIP @ direction).ravel()))
    return image


def from_sitk(image: Any) -> Volume:
    if image.GetDimension() != 3:
        raise ValueError("Only scalar 3D SimpleITK images are supported")
    affine = np.eye(4)
    affine[:3, :3] = (
        _FLIP @ np.array(image.GetDirection()).reshape(3, 3) @ np.diag(image.GetSpacing()) / 1000
    )
    affine[:3, 3] = _FLIP @ np.array(image.GetOrigin()) / 1000
    return Volume(sitk.GetArrayFromImage(image).transpose(2, 1, 0), affine)


def sitk_transform_to_ras(transform: Any, *, rigid: bool) -> Transform:
    """Recover a global affine from transformed origin and basis points, including center."""
    origin = np.array(transform.TransformPoint((0.0, 0.0, 0.0)))
    matrix = np.eye(4)
    matrix[:3, :3] = (
        _FLIP
        @ np.column_stack(
            [np.array(transform.TransformPoint(tuple(np.eye(3)[i]))) - origin for i in range(3)]
        )
        @ _FLIP
    )
    matrix[:3, 3] = _FLIP @ origin / 1000
    result = Transform(Frame.RAS, Frame.RAS, matrix, rigid=rigid)
    probes = np.array([[0.02, -0.01, 0.03], [-0.04, 0.03, -0.02]])
    expected = np.array(
        [_FLIP @ np.array(transform.TransformPoint(tuple(_FLIP @ p * 1000))) / 1000 for p in probes]
    )
    if not np.allclose(expected, probes @ matrix[:3, :3].T + matrix[:3, 3], atol=1e-10):
        raise ValueError("Registration returned a non-affine transform")
    return result


@dataclass(frozen=True)
class RegistrationConfig:
    mode: Literal["rigid", "affine"] = "rigid"
    metric: Literal["meansquares", "correlation", "mutual_information"] = "meansquares"
    iterations: int = 300
    learning_rate_mm: float = 1.0
    min_step_mm: float = 0.0001
    shrink_factors: tuple[int, ...] = (4, 2, 1)
    smoothing_sigmas_mm: tuple[float, ...] = (2.0, 1.0, 0.0)
    initialization: Literal["geometry", "moments", "identity"] = "geometry"
    threads: int = 1

    def __post_init__(self) -> None:
        if self.mode not in ("rigid", "affine") or self.metric not in (
            "meansquares",
            "correlation",
            "mutual_information",
        ):
            raise ValueError("Unsupported registration mode or metric")
        if self.initialization not in ("geometry", "moments", "identity"):
            raise ValueError("Unsupported initialization")
        if (
            self.iterations < 1
            or self.threads != 1
            or self.learning_rate_mm <= 0
            or self.min_step_mm <= 0
        ):
            raise ValueError("Invalid optimizer configuration; one thread is required")
        if len(self.shrink_factors) != len(self.smoothing_sigmas_mm) or not self.shrink_factors:
            raise ValueError("Multiresolution schedules differ")
        if any(n < 1 for n in self.shrink_factors) or any(n < 0 for n in self.smoothing_sigmas_mm):
            raise ValueError("Invalid pyramid schedule")


@dataclass
class RegistrationResult:
    transform: Transform
    fixed_grid: str
    moving_grid: str
    diagnostics: dict[str, Any]
    native: Any = field(repr=False)

    def warp(
        self, moving: Volume, fixed: Volume, *, order: int = 1, allow_repeated: bool = False
    ) -> Volume:
        if moving.grid_id != self.moving_grid or fixed.grid_id != self.fixed_grid:
            raise ValueError("Registration result belongs to different image grids")
        return resample(
            moving,
            fixed,
            reference_to_source=self.transform,
            order=order,
            allow_repeated=allow_repeated,
        )

    def save(self, output: Path) -> None:
        import json

        output.mkdir(parents=True, exist_ok=False)
        sitk.WriteTransform(self.native, str(output / "fixed-to-moving-LPS-mm.tfm"))
        (output / "transform.json").write_text(
            json.dumps(
                {
                    "fixed_to_moving_RAS_m": self.transform.matrix.tolist(),
                    "fixed_grid": self.fixed_grid,
                    "moving_grid": self.moving_grid,
                    "diagnostics": self.diagnostics,
                },
                indent=2,
                allow_nan=False,
            )
        )


DEFAULT_REGISTRATION = RegistrationConfig()


def register(
    fixed: Volume, moving: Volume, config: RegistrationConfig = DEFAULT_REGISTRATION
) -> RegistrationResult:
    import time

    if fixed.kind != "intensity" or moving.kind != "intensity":
        raise ValueError("Registration metrics require intensity images, not label identities")
    started = time.perf_counter()
    f, m = to_sitk(fixed, normalize=True), to_sitk(moving, normalize=True)
    initial = sitk.Euler3DTransform() if config.mode == "rigid" else sitk.AffineTransform(3)
    if config.initialization != "identity":
        method = (
            sitk.CenteredTransformInitializerFilter.GEOMETRY
            if config.initialization == "geometry"
            else sitk.CenteredTransformInitializerFilter.MOMENTS
        )
        init_fixed, init_moving = f, m
        if config.initialization == "moments":
            if np.min(fixed.array()) < 0 or np.min(moving.array()) < 0:
                raise ValueError("Moment initialization requires nonnegative raw intensities")
            # Normalized metric images have zero total intensity, so their
            # intensity moments are not meaningful initialization coordinates.
            init_fixed, init_moving = to_sitk(fixed), to_sitk(moving)
        initial = sitk.CenteredTransformInitializer(init_fixed, init_moving, initial, method)
    registration = sitk.ImageRegistrationMethod()
    registration.SetNumberOfThreads(config.threads)
    if config.metric == "meansquares":
        registration.SetMetricAsMeanSquares()
    elif config.metric == "correlation":
        registration.SetMetricAsCorrelation()
    else:
        registration.SetMetricAsMattesMutualInformation(40)
    registration.SetMetricSamplingStrategy(registration.NONE)
    registration.SetInterpolator(sitk.sitkLinear)
    registration.SetOptimizerAsRegularStepGradientDescent(
        learningRate=config.learning_rate_mm,
        minStep=config.min_step_mm,
        numberOfIterations=config.iterations,
        relaxationFactor=0.5,
        gradientMagnitudeTolerance=1e-8,
    )
    registration.SetOptimizerScalesFromPhysicalShift()
    registration.SetShrinkFactorsPerLevel(config.shrink_factors)
    registration.SetSmoothingSigmasPerLevel(config.smoothing_sigmas_mm)
    registration.SmoothingSigmasAreSpecifiedInPhysicalUnitsOn()
    registration.SetInitialTransform(initial, inPlace=False)
    trace = []
    registration.AddCommand(
        sitk.sitkIterationEvent,
        lambda: trace.append(
            {
                "level": registration.GetCurrentLevel(),
                "iteration": registration.GetOptimizerIteration(),
                "metric": registration.GetMetricValue(),
            }
        ),
    )
    try:
        final = registration.Execute(f, m)
    except RuntimeError as exc:
        raise ValueError(f"Registration failed (check overlap and initialization): {exc}") from exc
    transform = sitk_transform_to_ras(final, rigid=config.mode == "rigid")
    valid = registration.GetMetricNumberOfValidPoints()
    if valid / np.prod(fixed.shape) < 0.1:
        raise ValueError("Insufficient final overlap (<10% valid fixed voxels)")
    # Optimizer convergence is reported separately from anatomical correctness.
    stop = registration.GetOptimizerStopConditionDescription()
    diagnostics = {
        "config": asdict(config),
        "direction": "fixed_RAS_m_to_moving_RAS_m",
        "native_direction": "fixed_LPS_mm_to_moving_LPS_mm",
        "metric_value": float(registration.GetMetricValue()),
        "last_level_iteration": registration.GetOptimizerIteration(),
        "total_recorded_iterations": len(trace),
        "optimizer_stop": stop,
        "iteration_limit_reached": "maximum number" in stop.lower(),
        "valid_fixed_voxels": int(valid),
        "valid_fraction": float(valid / np.prod(fixed.shape)),
        "trace": trace,
        "runtime_s": time.perf_counter() - started,
        "anatomical_success_claim": False,
        "simpleitk_version": sitk.Version_VersionString(),
    }
    return RegistrationResult(transform, fixed.grid_id, moving.grid_id, diagnostics, final)
