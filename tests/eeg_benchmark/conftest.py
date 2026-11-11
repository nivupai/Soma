"""Deterministic fictional EEG only; external sockets forbidden."""

import pytest

from soma.decoding.synthetic import simulate_decoding
from soma.eeg_benchmark.evaluation import bank
from soma.eeg_benchmark.protocol import configuration, design


@pytest.fixture(scope="module")
def synthetic():
    d, _ = simulate_decoding(seed=22042, n_subjects=6, n_trials=6, effect=0.8, noise=0.1)
    p = configuration(design(4, 2), "primary")
    return d, p, bank(d, p)


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    import socket

    def denied(*args, **kwargs):
        raise AssertionError("Benchmark tests must be offline")

    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)
