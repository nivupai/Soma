"""Inspect every distribution member and payload; fail closed on private artifacts."""

import argparse
import hashlib
import json
import re
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

FORBIDDEN = re.compile(
    r"(?:^|/)(?:data|reports|derivatives|node_modules|\.git|\.venv[^/]*|[^/]*backup)(?:/|$)|\.(?:nii(?:\.gz)?|edf|bdf|fif|dcm|mgz|npz|npy|pt|pth|ckpt|onnx|safetensors|pem|key)$|(?:^|/)(?:\.env[^/]*|credentials[^/]*|secrets[^/]*|[^/]*\.local\.json)$",
    re.I,
)
PERSONAL = re.compile(
    rb"(?:/Users/(?!private/)[A-Za-z0-9_.-]+/|/home/[A-Za-z0-9_.-]+/"
    rb"|[A-Za-z]:\\Users\\[A-Za-z0-9_.-]+\\)"
)


def inspect(path):
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            files = {n: archive.read(n) for n in archive.namelist() if not n.endswith("/")}
        assert "soma/sdk/imaging.py" in files and "services/explorer_api/app.py" in files
        assert "soma/py.typed" in files
        assert "soma/resources/fmri-inference-policy.yaml" in files
    else:
        with tarfile.open(path, "r:gz") as archive:
            assert all(not n.issym() and not n.islnk() for n in archive.getmembers())
            files = {
                n.name: archive.extractfile(n).read() for n in archive.getmembers() if n.isfile()
            }
        assert any(n.endswith("examples/fmri_contrast.py") for n in files)
    for name, data in files.items():
        parts = PurePosixPath(name)
        assert not parts.is_absolute() and ".." not in parts.parts, name
        assert not FORBIDDEN.search(name), name
        assert not PERSONAL.search(data), name
        assert not re.search(rb"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----", data), name
        assert len(data) < 5 * 1024**2, name
    return {
        "artifact": path.name,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "bytes": path.stat().st_size,
        "files": sorted(files),
        "privacy_passed": True,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("paths", nargs="+", type=Path)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    result = [inspect(x) for x in args.paths]
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    else:
        print(text)


if __name__ == "__main__":
    main()
