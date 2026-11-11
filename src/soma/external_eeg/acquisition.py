"""Opt-in bounded acquisition using M20/M21 evidence; no implicit approval or terms."""

import hashlib
import os
import tempfile
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from soma.core.provenance import sha256
from soma.datasets.human_mri import safe_local_output
from soma.human.evidence import EvidenceBundle, local_file, verify_bundle
from soma.human.model import checksum
from soma.human.permissions import PermissionEvidence, permission_readiness
from soma.model_archive.acquisition import acquisition_plan
from soma.model_archive.archive import numerical_receipt
from soma.results.io import read_json
from soma.workflow.model import digest

DATASETS = {
    "bnci2014-001": ("upstream-001-2014-unversioned", "CC-BY-ND-4.0", 18),
    "cho2017": ("gigadb-100295-unversioned", "CC0-1.0", 52),
    "bnci2014-004": ("upstream-004-2014-unversioned", "CC-BY-ND-4.0", 18),
}
HOSTS = {"bnci-horizon-2020.eu", "gigadb.org", "s3.ap-northeast-1.wasabisys.com"}
MAX_FILE = 1024**3


def acquisition_template(dataset: str = "bnci2014-001") -> dict[str, Any]:
    if dataset not in DATASETS:
        raise ValueError("Unsupported dataset distribution")
    version, license, count = DATASETS[dataset]
    prefix = "A" if dataset == "bnci2014-001" else "B"
    names = (
        [f"{prefix}{s:02d}{session}.mat" for s in range(1, 10) for session in ["T", "E"]]
        if dataset != "cho2017"
        else [f"s{s:02d}.mat" for s in range(1, 53)]
    )
    return {
        "schema": "soma.acquisition.manifest/1",
        "dataset": dataset,
        "version": version,
        "license": license,
        "expected_files": count,
        "files": [
            {
                "file": name,
                "url": (
                    "https://bnci-horizon-2020.eu/database/data-sets/"
                    f"{'001-2014' if prefix == 'A' else '004-2014'}/{name}"
                )
                if dataset != "cho2017"
                else None,
                "sha256": None,
                "bytes": None,
            }
            for name in names
        ],
        "authorization": "REQUIRES_REVIEWED_HUMAN_APPROVAL",
        "root_policy": "explicit ignored local root; no raw Git export",
    }


def validate_manifest(m: dict[str, Any], *, complete: bool = True) -> str:
    expected = acquisition_template(m.get("dataset", ""))
    if set(m) != set(expected) or any(m[k] != expected[k] for k in expected if k != "files"):
        raise ValueError("Changed acquisition identity, license or distribution contract")
    if [r.get("file") for r in m["files"]] != [r["file"] for r in expected["files"]]:
        raise ValueError("Incomplete, duplicated or reordered expected file manifest")
    for row in m["files"]:
        if set(row) != {"file", "url", "sha256", "bytes"}:
            raise ValueError("Explicit file URL, checksum and size required")
        if complete and row["url"] is None:
            raise ValueError("Original-distribution file URL not yet verified")
        if complete or row["url"] is not None:
            u = urlsplit(row["url"] or "")
            host_ok = (
                u.hostname == "bnci-horizon-2020.eu"
                if m["dataset"].startswith("bnci")
                else u.hostname in HOSTS - {"bnci-horizon-2020.eu"}
            )
            if (
                u.scheme != "https"
                or not host_ok
                or u.username
                or u.password
                or u.port not in (None, 443)
                or u.query
                or u.fragment
                or not u.path.endswith("/" + row["file"])
            ):
                raise ValueError("Unapproved URL, credentials or insecure distribution")
            if m["dataset"].startswith("bnci") and row["url"] != next(
                r["url"] for r in expected["files"] if r["file"] == row["file"]
            ):
                raise ValueError("Unexpected original BNCI distribution URL")
        if complete:
            checksum(row["sha256"])
            if type(row["bytes"]) is not int or not 0 < row["bytes"] <= MAX_FILE:
                raise ValueError("Verified bounded file size required before approval")
    return digest(m)


def gate(
    m: dict[str, Any],
    protocol: str,
    permission: PermissionEvidence | None,
    notice: bytes | None,
    bundle: EvidenceBundle | None,
    references: dict[str, tuple[Path, str]] | None,
    *,
    acquisition: bool,
) -> dict[str, Any]:
    fingerprint = validate_manifest(m)
    reasons = []
    if permission is None or notice is None or bundle is None or references is None:
        reasons.append("Current M20/M21 permission and explicit acquisition evidence unavailable")
    else:
        b = bundle.document()
        if (b["dataset"], b["version"], b["protocol_fingerprint"]) != (
            m["dataset"],
            m["version"],
            protocol,
        ):
            reasons.append("Evidence dataset/version/protocol mismatch")
        else:
            integrity = verify_bundle(bundle, references)
            if integrity["status"] != "READY":
                reasons.append("Evidence missing, revoked, expired, corrupt or unreviewed")
            for action in ["analyze", "export_aggregate"]:
                readiness = permission_readiness(
                    permission, notice, bundle, references, action=action
                )
                if readiness["status"] != "READY":
                    reasons.extend(readiness["reasons"])
            if permission.document()["license"] != m["license"]:
                reasons.append("Reviewed permission license does not match selected distribution")
            approved = False
            for entry in b["entries"]:
                if entry["kind"] != "agreement" or "acquire" not in entry["actions"]:
                    continue
                if entry["purpose"] != "methods_research" or entry["id"] not in references:
                    continue
                root, relative = references[entry["id"]]
                try:
                    a = read_json(local_file(root, relative))
                    approved = (
                        a
                        == {
                            "schema": "soma.acquisition.approval/1",
                            "dataset": m["dataset"],
                            "version": m["version"],
                            "manifest_fingerprint": fingerprint,
                            "approved": True,
                            "terms_acceptance_delegated": False,
                        }
                        and entry["review"]["status"] == "APPROVED"
                    )
                except (OSError, ValueError):
                    pass
            if not approved:
                reasons.append(
                    "Explicit reviewed acquisition approval is absent or manifest-mismatched"
                )
    return {
        "status": "READY" if not reasons else "BLOCKED",
        "reasons": sorted(set(reasons)),
        "manifest_fingerprint": fingerprint,
        "operation": "acquire" if acquisition else "analyze",
        "consent_verified": False,
        "legal_authorization_established": False,
    }


def snapshot(root: Path, m: dict[str, Any]) -> dict[str, Any]:
    fingerprint = validate_manifest(m)
    rows = []
    base = root.resolve(strict=True)
    for row in m["files"]:
        p = base / row["file"]
        valid = p.is_file() and not p.is_symlink() and p.resolve().is_relative_to(base)
        valid = valid and p.stat().st_size == row["bytes"] and sha256(p) == row["sha256"]
        rows.append({"file": row["file"], "status": "VERIFIED" if valid else "MISSING_OR_CHANGED"})
    return {
        "schema": "soma.acquisition.snapshot/1",
        "format_validation": "CHECKSUMS_ONLY; scientific parser/QC remains separate",
        "dataset": m["dataset"],
        "version": m["version"],
        "manifest_fingerprint": fingerprint,
        "snapshot_fingerprint": digest({"manifest": fingerprint, "files": rows}),
        "files": rows,
        "verified_files": sum(r["status"] == "VERIFIED" for r in rows),
        "complete": all(r["status"] == "VERIFIED" for r in rows),
    }


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> None:
        raise ValueError("Redirect requires separate distribution review")


def _transfer(url: str) -> Any:
    return urllib.request.build_opener(NoRedirect()).open(url, timeout=60)


def acquire(
    m: dict[str, Any],
    protocol: str,
    root: Path,
    output: Path,
    permission: PermissionEvidence | None = None,
    notice: bytes | None = None,
    bundle: EvidenceBundle | None = None,
    references: dict[str, tuple[Path, str]] | None = None,
) -> dict[str, Any]:
    ready = gate(m, protocol, permission, notice, bundle, references, acquisition=True)
    if ready["status"] != "READY":
        raise ValueError("Unauthorized acquisition: " + "; ".join(ready["reasons"]))
    safe_local_output(root)
    safe_local_output(output)
    if output.resolve().is_relative_to(root.resolve()) or root.is_symlink():
        raise ValueError("Separate ignored raw and receipt roots required")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(root, 0o700)
    downloads = 0
    for row in m["files"]:
        if (
            gate(m, protocol, permission, notice, bundle, references, acquisition=True)["status"]
            != "READY"
        ):
            raise ValueError("Acquisition authorization changed or expired")
        path = root / row["file"]
        if path.exists() or path.is_symlink():
            if (
                path.is_symlink()
                or path.stat().st_size != row["bytes"]
                or sha256(path) != row["sha256"]
            ):
                raise ValueError("Existing file differs; acquisition never overwrites inputs")
            continue
        fd, temporary = tempfile.mkstemp(prefix=".acquire-", dir=root)
        try:
            h = hashlib.sha256()
            size = 0
            with os.fdopen(fd, "wb") as out, _transfer(row["url"]) as response:
                if response.geturl() != row["url"] or response.status != 200:
                    raise ValueError("Unexpected distribution response")
                while chunk := response.read(1024**2):
                    size += len(chunk)
                    if size > row["bytes"]:
                        raise ValueError("Download exceeds approved size")
                    out.write(chunk)
                    h.update(chunk)
                out.flush()
                os.fsync(out.fileno())
            if size != row["bytes"] or h.hexdigest() != row["sha256"]:
                raise ValueError("Downloaded file checksum/size mismatch")
            os.link(temporary, path)
            downloads += 1
        finally:
            Path(temporary).unlink(missing_ok=True)
    checked = snapshot(root, m)
    if not checked["complete"]:
        raise ValueError("Snapshot changed before acquisition receipt")
    result = {
        **checked,
        "downloaded_files": downloads,
        "approval": ready,
        "raw_exported": False,
    }
    numerical_receipt(result, {}, output, "soma.external-acquisition")
    return result


def selection_audit() -> dict[str, Any]:
    return {
        **acquisition_plan(),
        "schema": "soma.external-selection/1",
        "selection": (
            "BNCI001 primary feasibility candidate; Cho2017 rights-review "
            "alternative; BNCI004 incompatible"
        ),
        "selection_basis": (
            "task, nominal montage, actual sessions and permission evidence; no classifier outcomes"
        ),
        "selected_for_execution": None,
        "preferred_acquisition_review_candidate": "cho2017",
        "priority_reason": "Primary CC0 needs distribution review; no consent/approval inferred",
        "source_release": "8ce2e0952dce6f770a15ae70b99863d8712ec3017de951bba37bf3ef070afe85",
        "limitations": [
            "No new acquisition authorization",
            "Unknown source checksums and sizes require verified manifest",
            "No independent consent inference from public accessibility",
            "No reviewed complete scientific target/source contract",
        ],
    }
