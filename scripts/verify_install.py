"""Fresh non-editable core and Explorer installation; output stays local/ignored.

Run: python scripts/verify_install.py dist/soma_neuro-0.16.0-py3-none-any.whl --env .venv-wheel
Repeat for the sdist and source directory. Pip resolves real dependencies; no
system-site-packages, developer .pth files or source PYTHONPATH are inherited.
"""

import argparse
import json
import os
import shutil
import subprocess
import tempfile
import venv
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("artifact", type=Path)
    p.add_argument("--env", required=True, type=Path)
    p.add_argument("--wheelhouse", type=Path)
    args = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    env = args.env.resolve()
    if env.exists():
        raise FileExistsError(env)
    venv.EnvBuilder(with_pip=True).create(env)
    python = env / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    cli = env / ("Scripts/soma.exe" if os.name == "nt" else "bin/soma")
    artifact = str(args.artifact.resolve())
    clean_env = {
        k: v
        for k, v in os.environ.items()
        if k not in {"PYTHONPATH", "SOMA_EXPLORER_CONFIG", "VIRTUAL_ENV"}
    }
    clean_env.update(
        VIRTUAL_ENV=str(env), MPLBACKEND="Agg", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1"
    )
    pip = [str(python), "-m", "pip", "install"]
    if args.wheelhouse:
        pip += ["--no-index", "--find-links", str(args.wheelhouse.resolve())]
    with tempfile.TemporaryDirectory(prefix="soma-sdk-install-") as d:
        cwd = Path(d)

        def run(cmd):
            subprocess.run([str(x) for x in cmd], cwd=cwd, env=clean_env, check=True)

        run([*pip, artifact])
        run([python, "-I", root / "scripts/installed_smoke.py"])
        run([cli, "--help"])
        run([cli, "datasets", "list"])
        run([*pip, artifact + "[explorer]"])
        run([python, "-I", root / "scripts/installed_smoke.py", "--explorer"])
        shutil.copytree(
            root / "examples", cwd / "examples", ignore=shutil.ignore_patterns("__pycache__")
        )
        shutil.copy(root / "scripts/run_sdk_examples.py", cwd / "run_examples.py")
        run([python, cwd / "run_examples.py", "--output", cwd / "results.json"])
        run([python, "-m", "pip", "check"])
        resolved = subprocess.check_output(
            [str(python), "-m", "pip", "freeze"], cwd=cwd, env=clean_env, text=True
        )
        output = root / "reports/milestone16"
        output.mkdir(parents=True, exist_ok=True)
        # Store paths only in ignored local receipts, never in release documentation.
        (output / (env.name + "-resolved.txt")).write_text(resolved)
        (output / (env.name + "-examples.json")).write_text((cwd / "results.json").read_text())
        (output / (env.name + "-installation.json")).write_text(
            json.dumps(
                {
                    "environment": env.name,
                    "artifact": args.artifact.name,
                    "core_and_explorer": True,
                    "noneditable": True,
                    "isolated_cwd": True,
                },
                indent=2,
            )
            + "\n"
        )


if __name__ == "__main__":
    main()
