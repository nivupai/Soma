"""Typed focused EEG benchmark APIs, backed by existing Soma scientific contracts."""

from soma.eeg_benchmark.data import inventory as inventory
from soma.eeg_benchmark.protocol import benchmark_protocol as benchmark_protocol
from soma.eeg_benchmark.protocol import design as design
from soma.eeg_benchmark.protocol import inspect_protocol as inspect_protocol
from soma.eeg_benchmark.protocol import validate_design as validate_design
from soma.eeg_benchmark.report import aggregate_export as aggregate_export
from soma.eeg_benchmark.report import compare as compare
from soma.eeg_benchmark.report import read_aggregate as read_aggregate
from soma.eeg_benchmark.report import save_aggregate as save_aggregate
from soma.eeg_benchmark.report import verify_execution as verify_execution
from soma.eeg_benchmark.runner import run_benchmark as run_benchmark
