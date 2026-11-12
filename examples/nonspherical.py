"""Small core-only geometry example; the full BEM sweep requires [conductor]."""

from soma.sdk.source import nonspherical_design, nonspherical_protocol, synthetic_head
from soma.source.nonspherical import meshes, validate_meshes


def run():
    head = synthetic_head(0)
    q = validate_meshes(meshes(head, 0))
    assert q["minimum_thickness_mm"] > nonspherical_design()["min_thickness_mm"]
    return dict(
        synthetic_only=True,
        human_subjects=0,
        minimum_thickness_mm=q["minimum_thickness_mm"],
        protocol=nonspherical_protocol().protocol.fingerprint,
        independent_four_layer_validation="NOT_ESTABLISHED",
    )
