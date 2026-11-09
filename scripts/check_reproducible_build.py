"""Two independent builds, fixed timestamp, identical wheel and sdist bytes."""

import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

env = dict(os.environ, SOURCE_DATE_EPOCH="1704067200")
with tempfile.TemporaryDirectory(prefix="soma-repro-") as directory:
    roots = [Path(directory) / str(n) for n in range(2)]
    for root in roots:
        subprocess.run([sys.executable, "-m", "build", "--outdir", str(root)], env=env, check=True)
    hashes = [
        {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir()}
        for root in roots
    ]
    assert hashes[0] == hashes[1], hashes
    print(hashes[0])
