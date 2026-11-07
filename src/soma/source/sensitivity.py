"""Small, physically recomputed spherical conductor sensitivity control.

This is not a fsaverage BEM recomputation. Conductivity changes are passed to
MNE's conductor constructor and each forward is computed independently.
"""

from typing import Any

import mne
import numpy as np
from scipy.linalg import subspace_angles

from soma.source.noise import average_projector


def sphere_sensitivity() -> tuple[dict[str, Any], dict[str, Any]]:
    names = ["Fp1", "Fp2", "F3", "F4", "C3", "C4", "P3", "P4", "O1", "O2", "Fz", "Cz", "Pz"]
    info = mne.create_info(names, 160, "eeg")
    info.set_montage(mne.channels.make_standard_montage("fsaverage_1005"))
    positions = np.array(
        [[-0.025, 0.02, 0.065], [0.025, 0.02, 0.065], [-0.02, 0.02, 0.03], [0.02, -0.02, 0.04]]
    )
    src = mne.setup_volume_source_space(
        pos={"rr": positions, "nn": np.tile([0.0, 0, 1], (4, 1))},
        sphere=(0.0, 0.0, 0.04, 0.09),
        add_interpolator=False,
        verbose=False,
    )
    leads = []
    for skull in (0.004, 0.012):
        sphere = mne.make_sphere_model(
            r0=(0.0, 0.0, 0.04),
            head_radius=0.09,
            relative_radii=(0.9, 0.92, 0.97, 1.0),
            sigmas=(0.33, 1.0, skull, 0.33),
            verbose=False,
        )
        fwd = mne.make_forward_solution(
            info,
            trans=None,
            src=src,
            bem=sphere,
            meg=False,
            eeg=True,
            mindist=0,
            n_jobs=1,
            verbose=False,
        )
        leads.append(average_projector(len(names)) @ fwd["sol"]["data"])
    a, b = leads
    singular_a = np.linalg.svd(a, compute_uv=False)
    singular_b = np.linalg.svd(b, compute_uv=False)
    from soma.source.inverse import Tikhonov

    truth = np.zeros(a.shape[1])
    truth[2] = 1e-8
    # Fixed dimensionless relative regularization, not truth selected.
    scale = singular_a[0]
    matched = Tikhonov(a / scale, 0.001).solve(a @ truth / scale)
    mismatched = Tikhonov(b / scale, 0.001).solve(a @ truth / scale)
    norm_per_vertex = np.linalg.norm(mismatched.reshape(-1, 3), axis=1)
    peak = int(np.argmax(norm_per_vertex))
    return (
        {
            "model": "freshly recomputed four-shell analytical MNE sphere, not template BEM",
            "skull_conductivity_S_per_m": [0.004, 0.012],
            "relative_matrix_perturbation": float(np.linalg.norm(b - a) / np.linalg.norm(a)),
            "singular_values_baseline": singular_a.tolist(),
            "singular_values_changed": singular_b.tolist(),
            "column_subspace_angles_rad": subspace_angles(a, b).tolist(),
            "relative_estimate_change": float(
                np.linalg.norm(mismatched - matched) / np.linalg.norm(matched)
            ),
            "mismatched_peak_displacement_m": float(np.linalg.norm(positions[peak] - positions[0])),
            "orientation": "free Cartesian",
            "source_count": 4,
        },
        {
            "baseline": a,
            "changed": b,
            "source_head_m": positions,
            "truth_Am": truth,
            "matched_Am": matched,
            "mismatched_Am": mismatched,
        },
    )
