"""Audit current files and every reachable blob/message; no unsanitized sources."""

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

from inspect_distributions import FORBIDDEN, PERSONAL


def git(*args):
    return subprocess.check_output(["git", *args])


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--gitleaks", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    review = json.loads(Path("scripts/security_reviewed.json").read_text())
    approved = review["files"]
    reviewed_binary_hashes = set(review["synthetic_png_sha256"].values())
    names = git("ls-files", "--cached", "--others", "--exclude-standard", "-z").decode().split("\0")
    current = {n: Path(n).read_bytes() for n in names if n and Path(n).is_file()}
    for n, data in current.items():
        # Six previously inspected synthetic Explorer screenshots are retained.
        if FORBIDDEN.search(n) and not (n.endswith("/.gitkeep") and data == b""):
            raise ValueError("Sensitive tracked path: " + n)
        if PERSONAL.search(data):
            raise ValueError("Personal home path in " + n)
        if len(data) > 5 * 1024**2:
            raise ValueError("Large tracked file: " + n)
        if b"\0" in data[:8192] and hashlib.sha256(data).hexdigest() not in reviewed_binary_hashes:
            raise ValueError("Unreviewed tracked binary: " + n)
    historical_paths = git("log", "--all", "--pretty=format:", "--name-only").decode().splitlines()
    for name in set(historical_paths):
        if FORBIDDEN.search(name) and not name.endswith("/.gitkeep"):
            raise ValueError("Sensitive historical tree path: " + name)
    objects = git("rev-list", "--objects", "--all").decode().splitlines()
    raw = {}
    metadata = []
    commits = 0
    for line in objects:
        oid = line.split()[0]
        kind = git("cat-file", "-t", oid).strip()
        if kind not in {b"blob", b"commit", b"tag"}:
            continue
        data = git("cat-file", "-p", oid)
        if PERSONAL.search(data):
            raise ValueError("Personal home path in reachable Git object " + oid)
        if kind == b"blob":
            if (
                b"\0" in data[:8192]
                and hashlib.sha256(data).hexdigest() not in reviewed_binary_hashes
            ):
                raise ValueError("Unreviewed historical binary: " + oid)
            raw[oid] = data
            name = line.partition(" ")[2]
            if FORBIDDEN.search(name) and not (name.endswith("/.gitkeep") and data == b""):
                raise ValueError("Sensitive historical path: " + name)
            if len(data) > 5 * 1024**2:
                raise ValueError("Large historical blob: " + oid)
        else:
            metadata.append(data)
            commits += int(kind == b"commit")
    summaries = {}
    with tempfile.TemporaryDirectory(prefix="soma-security-") as d:
        temp = Path(d)
        blobs = temp / "blobs"
        blobs.mkdir()
        tree = temp / "tree"
        tree.mkdir()
        for oid, data in raw.items():
            (blobs / oid).write_bytes(data)
        for name, data in current.items():
            target = tree / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        config = temp / "gitleaks.toml"
        config.write_text("[extend]\nuseDefault = true\n")
        scopes = {
            "history": ["git", ".", "--log-opts=--all --full-history --root"],
            "blobs": ["dir", str(blobs)],
            "tree": ["dir", str(tree)],
            "metadata": ["stdin"],
        }
        for scope, command in scopes.items():
            report = args.output / ("gitleaks-" + scope + ".json")
            result = subprocess.run(
                [
                    str(args.gitleaks.resolve()),
                    *command,
                    "--config",
                    str(config),
                    "--redact=100",
                    "--ignore-gitleaks-allow",
                    "--report-format",
                    "json",
                    "--report-path",
                    str(report),
                    "--no-banner",
                ],
                input=b"\n".join(metadata) if scope == "metadata" else None,
                capture_output=True,
            )
            (args.output / ("gitleaks-" + scope + ".log")).write_bytes(result.stderr)
            if result.returncode not in (0, 1):
                raise RuntimeError("Scanner failed: " + scope)
            findings = json.loads(report.read_text())
            for finding in findings:
                if finding["RuleID"] != "generic-api-key":
                    raise ValueError("Unreviewed scanner rule")
                name = finding["File"]
                if scope == "history":
                    if name not in approved:
                        raise ValueError("Unreviewed history scanner finding")
                    payload = git("show", finding["Commit"] + ":" + name)
                elif scope == "tree":
                    name = (
                        Path(name).relative_to(tree).as_posix()
                        if Path(name).is_absolute()
                        else name
                    )
                    # Gitleaks versions may use paths relative to their scan root.
                    if name not in approved:
                        raise ValueError("Unreviewed tree scanner finding: " + name)
                    payload = current[name]
                elif scope == "blobs":
                    payload = raw[Path(name).name]
                    if hashlib.sha256(payload).hexdigest() not in approved.values():
                        raise ValueError("Unreviewed blob scanner finding")
                    continue
                else:
                    raise ValueError("Unreviewed metadata scanner finding")
                if hashlib.sha256(payload).hexdigest() != approved[name]:
                    raise ValueError("Changed reviewed false-positive content")
            summaries[scope] = {
                "raw_findings": len(findings),
                "scanner_exit": result.returncode,
                "reviewed_false_positives": len(findings),
            }
    output = {
        "scanner": "Gitleaks 8.30.1",
        "rules_suppressed": False,
        "current_files": len(current),
        "commits": commits,
        "blobs": len(raw),
        "material_secrets": 0,
        "restricted_data_files": 0,
        "personal_home_paths": 0,
        "scopes": summaries,
        "limitation": (
            "Manual review plus pattern scanners cannot prove the absence "
            "of all sensitive information"
        ),
    }
    (args.output / "summary.json").write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(output))


if __name__ == "__main__":
    main()
