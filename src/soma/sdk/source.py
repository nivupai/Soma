"""Existing forward/inverse operators; synthetic diagnostics do not validate anatomy."""

from soma.experiments.bem_discrepancy import run_diagnostics as _run_bem_diagnostics
from soma.experiments.fem_reference import design as _fem_design
from soma.experiments.fem_reference import protocol as _fem_protocol
from soma.experiments.fem_reference import run as _run_fem_reference
from soma.experiments.mesh_grid import design as _mesh_grid_design
from soma.experiments.mesh_grid import protocol as _mesh_grid_protocol
from soma.experiments.mesh_grid import run as _run_mesh_grid
from soma.experiments.nonspherical import run_nonspherical as run_nonspherical
from soma.experiments.source_uncertainty import run_uncertainty as run_uncertainty
from soma.source.bem_discrepancy import design as _bem_design
from soma.source.bem_discrepancy import protocol as _bem_protocol
from soma.source.fem_reference import full_subtraction as _fem_forward
from soma.source.fem_reference import layered_sphere_series as _layered_sphere
from soma.source.forward import ForwardModel as ForwardModel
from soma.source.forward import build_forward as build_forward
from soma.source.inverse import CorticalInverse as CorticalInverse
from soma.source.inverse import Tikhonov as Tikhonov
from soma.source.mesh_replication import candidate_grid as _convergence_grid
from soma.source.noise import NoiseModel as NoiseModel
from soma.source.noise import average_projector as average_projector
from soma.source.nonspherical import design as _nonspherical_design
from soma.source.nonspherical import head_parameters as _synthetic_head
from soma.source.nonspherical import protocol as _nonspherical_protocol
from soma.source.nonspherical import validate_meshes as _validate_head_meshes
from soma.source.prior_calibration import PriorInverse as PriorInverse
from soma.source.prior_calibration import SourcePrior as SourcePrior
from soma.source.resolution import Resolution as Resolution
from soma.source.template import Template as Template
from soma.source.uncertainty import design as _uncertainty_design
from soma.source.uncertainty import protocol as _uncertainty_protocol

uncertainty_design = _uncertainty_design
uncertainty_protocol = _uncertainty_protocol

nonspherical_design = _nonspherical_design
nonspherical_protocol = _nonspherical_protocol
synthetic_head = _synthetic_head
validate_head_meshes = _validate_head_meshes

bem_diagnostic_design = _bem_design
bem_diagnostic_protocol = _bem_protocol

run_bem_diagnostics = _run_bem_diagnostics


fem_reference_design = _fem_design
fem_reference_protocol = _fem_protocol
run_fem_reference = _run_fem_reference
fem_forward = _fem_forward
layered_sphere_reference = _layered_sphere

mesh_grid_design = _mesh_grid_design
mesh_grid_protocol = _mesh_grid_protocol
run_mesh_grid = _run_mesh_grid
convergence_grid = _convergence_grid
