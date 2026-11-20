import numpy as np
import pytest

from soma.benchmarks.segmentation import intensity_baseline, masked_intensity_baseline
from soma.imaging.volumes import Volume
from soma.pipeline.synthseg import (
    SYNTHSEG_TO_SOMA,
    intracranial_mask,
    map_synthseg,
    to_native_grid,
)

AFFINE = np.diag([0.001, 0.001, 0.001, 1.0])


def _labels(data: np.ndarray, affine: np.ndarray = AFFINE) -> Volume:
    return Volume(data.astype(np.int16), affine, "labels", {"subject": "s"})


def test_ontology_map_is_disjoint_and_complete_for_soma_tissues() -> None:
    assert set(SYNTHSEG_TO_SOMA.values()) == {0, 1, 2, 3}
    assert SYNTHSEG_TO_SOMA[24] == 1  # extracerebral CSF is conductor CSF
    assert SYNTHSEG_TO_SOMA[3] == SYNTHSEG_TO_SOMA[42] == 2
    assert SYNTHSEG_TO_SOMA[2] == SYNTHSEG_TO_SOMA[16] == 3


def test_map_synthseg_values_and_refuses_unknown_codes() -> None:
    data = np.zeros((4, 4, 4))
    data[0, 0, 0], data[1, 1, 1], data[2, 2, 2], data[3, 3, 3] = 24, 42, 41, 4
    mapped = map_synthseg(_labels(data)).array()
    assert (mapped[0, 0, 0], mapped[1, 1, 1], mapped[2, 2, 2], mapped[3, 3, 3]) == (1, 2, 3, 1)
    assert mapped.sum() == 7
    data[0, 1, 0] = 1002  # a parcellation code: --parc must be off
    with pytest.raises(ValueError, match="frozen ontology"):
        map_synthseg(_labels(data))


def test_native_grid_return_is_nearest_neighbour_and_noop_on_same_grid() -> None:
    fine = _labels(np.ones((4, 4, 4)) * 2)
    same, receipt = to_native_grid(fine, fine)
    assert same is fine and receipt == {"resampled": False}
    coarse = Volume(np.zeros((2, 2, 2), np.float32), np.diag([0.002, 0.002, 0.002, 1.0]))
    out, receipt = to_native_grid(fine, coarse)
    assert receipt["resampled"] and receipt["order"] == 0
    assert set(np.unique(out.array()).tolist()) <= {0, 2}


def test_masked_baseline_excludes_extracranial_and_leaves_control_unchanged() -> None:
    rng = np.random.default_rng(0)
    image = np.zeros((20, 20, 20), np.float32)
    image[5:15, 5:15, 5:15] = rng.choice([30.0, 60.0, 90.0], size=(10, 10, 10))
    image[0:3] = rng.choice([30.0, 60.0, 90.0], size=(3, 20, 20))  # "scalp"
    volume = Volume(image, AFFINE, "intensity", {"subject": "s", "space": "x"})
    seg = np.zeros((20, 20, 20))
    seg[5:15, 5:15, 5:15] = 3
    mask = intracranial_mask(_labels(seg), dilation_voxels=1)
    control = intensity_baseline(volume).array()
    masked = masked_intensity_baseline(volume, mask).array()
    assert control[0:3].any() and not masked[0:3].any()
    assert masked[5:15, 5:15, 5:15].all()
    assert intensity_baseline(volume).metadata["extracranial_voxels_excluded"] is False
