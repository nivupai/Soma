"""Seal and replay a descriptive toy protocol using only installed public SDKs."""

from pathlib import Path
from tempfile import TemporaryDirectory

from soma.sdk.protocol import compare, example_protocol, example_snapshot, seal
from soma.sdk.protocol import run as replay


def run():
    protocol = example_protocol("source")
    sealed = seal(protocol)
    snapshot = example_snapshot(protocol)
    with TemporaryDirectory() as root:
        first = replay(sealed, snapshot, Path(root), sequence=1)
        second = replay(sealed, snapshot, Path(root), sequence=2, reference=first)
        result = compare(first, second)
        assert result["authorized"]
        return {"protocol": protocol.fingerprint, "comparison": result}


if __name__ == "__main__":
    print(run())
