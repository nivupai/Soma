"""Strict explicit-root import manifest around existing M14 preprocessing/QC audits.

This module never executes fMRIPrep, registers images, fits a GLM or changes data.
"""

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import nibabel as nib
import numpy as np
import pandas as pd

from soma.core.provenance import sha256
from soma.fmri.confounds import configure_confounds
from soma.fmri.preprocessing_audit import PreprocessingBundle, audit_preprocessing, load_audited_run
from soma.human.adapters import Selection
from soma.human.evidence import local_file
from soma.human.model import checksum, token
from soma.protocol.model import ProtocolError, closed
from soma.results.contracts import canonical
from soma.workflow.privacy import redact_export

ROLES = {
    "raw_bold",
    "bold",
    "mask",
    "confounds",
    "confound_json",
    "t1",
    "raw_t1",
    "raw_description",
    "derivative_description",
    "bold_json",
    "acquisition",
    "events",
}


def validate_root(root: Path) -> None:
    """Bounded explicit dataset root; reject escaped symlinks before legacy indexers."""
    base = root.resolve(strict=True)
    count = 0
    for directory, folders, files in os.walk(base, followlinks=False):
        for name in folders + files:
            count += 1
            if count > 20000:
                raise ProtocolError("Explicit preprocessing root exceeds bounded inventory")
            p = Path(directory) / name
            if not p.resolve(strict=True).is_relative_to(base):
                raise ProtocolError("Preprocessing root contains escaped symlink")


@dataclass(frozen=True)
class PreprocessingManifest:
    _canonical: bytes

    def __post_init__(self) -> None:
        if len(self._canonical) > 1024**2:
            raise ProtocolError("Bounded preprocessing manifest required")
        d = json.loads(self._canonical)
        if canonical(d) != self._canonical:
            raise ProtocolError("Canonical preprocessing manifest required")
        closed(
            d,
            {
                "schema",
                "identity_fingerprint",
                "assets",
                "software",
                "configuration",
                "environment",
                "identity",
                "space",
                "transforms",
                "evidence",
                "distortion_correction",
                "bids_validation",
            },
        )
        if d["schema"] != "soma.preprocessing.manifest/1.0.0":
            raise ProtocolError("Unsupported preprocessing manifest")
        checksum(d["identity_fingerprint"])
        if not ROLES.issubset(d["assets"]) or len(d["assets"]) > 128:
            raise ProtocolError("Required input/output identity assets missing")
        for a in d["assets"].values():
            closed(a, {"root", "path", "sha256"})
            checksum(a["sha256"])
            if (
                a["root"] not in {"raw", "derivatives"}
                or Path(a["path"]).is_absolute()
                or (".." in Path(a["path"]).parts or "\\" in a["path"])
            ):
                raise ProtocolError("Relative root-bound preprocessing asset required")
        closed(d["software"], {"name", "version", "container_digest"})
        if d["software"]["name"].lower() != "fmriprep" or not d["software"]["version"]:
            raise ProtocolError("Explicit pipeline software/version required")
        if d["software"]["container_digest"] is not None:
            checksum(d["software"]["container_digest"])
        if not isinstance(d["configuration"], dict) or not isinstance(d["environment"], dict):
            raise ProtocolError("Configuration/environment provenance required")
        if d["distortion_correction"] not in {"APPLIED", "NOT_REQUIRED", "UNKNOWN"}:
            raise ProtocolError("Explicit distortion correction evidence required")
        closed(d["identity"], {"subject", "session", "task", "run"})
        for value in d["identity"].values():
            if value is not None:
                token(value)
        token(d["space"])
        if not isinstance(d["transforms"], list) or len(d["transforms"]) > 16:
            raise ProtocolError("Bounded explicit transforms required")
        for transform in d["transforms"]:
            closed(
                transform,
                {
                    "path",
                    "subject",
                    "from_space",
                    "to_space",
                    "kind",
                    "point_direction",
                    "reference",
                    "source_image",
                },
                {"landmarks_source_RAS_m", "landmarks_target_RAS_m", "landmark_tolerance_mm"},
            )
            for field in ["path", "source_image", "reference"]:
                if transform[field] not in d["assets"]:
                    raise ProtocolError("Transform asset reference is not bound")
            token(transform["subject"])
        public = {k: d[k] for k in ["configuration", "environment", "evidence", "software"]}
        if redact_export(public) != public:
            raise ProtocolError("Private absolute paths/credentials forbidden in import manifest")

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "PreprocessingManifest":
        return cls(canonical(value))

    def document(self) -> dict[str, Any]:
        return dict(json.loads(self._canonical))

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self._canonical).hexdigest()


def manifest_from_bundle(
    bundle: PreprocessingBundle,
    identity_fingerprint: str,
    *,
    configuration: dict[str, Any],
    environment: dict[str, Any],
    distortion_correction: str = "UNKNOWN",
    bids_validation: str = "NOT_AVAILABLE",
) -> PreprocessingManifest:
    """Import existing explicitly selected M14 assets; does not manufacture provenance."""
    roots = {"raw": bundle.raw_root.resolve(), "derivatives": bundle.derivative_root.resolve()}
    paths = {
        k: getattr(bundle, k)
        for k in ["raw_bold", "bold", "mask", "confounds", "confound_json", "t1"]
    }
    paths.update(
        raw_description=bundle.raw_root / "dataset_description.json",
        derivative_description=bundle.derivative_root / "dataset_description.json",
        raw_t1=Path(bundle.evidence["T1_sources"][0]),
        bold_json=Path(str(bundle.bold).removesuffix(".nii.gz").removesuffix(".nii") + ".json"),
    )
    from bids import BIDSLayout

    for root in roots.values():
        validate_root(root)
    layout = BIDSLayout(bundle.raw_root, validate=False)
    for role, suffix, extension in [("events", "events", ".tsv"), ("acquisition", "bold", ".json")]:
        nearest = layout.get_nearest(
            str(bundle.raw_bold),
            suffix=suffix,
            extension=extension,
            strict=True,
            ignore_strict_entities=["extension", "suffix"],
            task=bundle.identity["task"],
        )
        if not nearest:
            raise ProtocolError("Missing explicit inherited acquisition/event metadata")
        paths[role] = Path(nearest)
    transforms = []
    for i, original in enumerate(bundle.transforms):
        spec = dict(original)
        for k in ["path", "source_image", "reference"]:
            role = f"transform-{i}-{k}"
            paths[role] = Path(spec[k])
            spec[k] = role
        transforms.append(spec)
    for i, path in enumerate(bundle.qc_reports):
        paths[f"qc-{i}"] = path
    assets = {}
    for role, path in paths.items():
        resolved = path.resolve(strict=True)
        keys = [k for k, root in roots.items() if resolved.is_relative_to(root)]
        if len(keys) != 1:
            raise ProtocolError("Ambiguous/escaped preprocessing asset")
        key = keys[0]
        assets[role] = {
            "root": key,
            "path": resolved.relative_to(roots[key]).as_posix(),
            "sha256": sha256(resolved),
        }
    desc = json.loads(paths["derivative_description"].read_text())
    generated = [g for g in desc.get("GeneratedBy", []) if g.get("Name", "").lower() == "fmriprep"]
    if len(generated) != 1:
        raise ProtocolError("Unique fMRIPrep software provenance required")
    evidence = {k: v for k, v in bundle.evidence.items() if k not in {"T1_sources", "transforms"}}
    return PreprocessingManifest.from_dict(
        {
            "schema": "soma.preprocessing.manifest/1.0.0",
            "identity_fingerprint": identity_fingerprint,
            "assets": assets,
            "software": {
                "name": "fMRIPrep",
                "version": generated[0].get("Version"),
                "container_digest": None,
            },
            "configuration": configuration,
            "environment": environment,
            "identity": bundle.identity,
            "space": bundle.space,
            "transforms": transforms,
            "evidence": evidence,
            "distortion_correction": distortion_correction,
            "bids_validation": bids_validation,
        }
    )


def audit_manifest(
    manifest: PreprocessingManifest, selection: Selection, roots: dict[str, Path]
) -> dict[str, Any]:
    """Recheck content, private subject mapping, direction, geometry and measured QC."""
    d = manifest.document()
    checks: list[dict[str, Any]] = []
    receipt: dict[str, Any] = {
        "schema": "soma.preprocessing.audit/1.0.0",
        "manifest_fingerprint": manifest.fingerprint,
        "identity_fingerprint": selection.identity.fingerprint,
        "technical_status": "INDETERMINATE",
        "qc_status": "INDETERMINATE",
        "scientific_adequacy": "INDETERMINATE",
        "inference_authorized": False,
        "checks": checks,
        "qc": {},
        "limitations": [
            "local provenance assertions are not independent pipeline attestation",
            "passed technical/motion QC does not validate anatomy, noise model or human inference",
        ],
    }

    def check(name: str, passed: bool, reason: str) -> None:
        checks.append({"gate": name, "status": "READY" if passed else "BLOCKED", "reason": reason})

    try:
        if set(roots) != {"raw", "derivatives"}:
            raise ProtocolError("Explicit raw and derivatives roots required")
        for root in roots.values():
            validate_root(root)
        selection.verify_inputs()
        who = selection.identity.document()
        if d["identity_fingerprint"] != selection.identity.fingerprint:
            raise ProtocolError("Preprocessing identity fingerprint mismatch")
        fields = ["session", "task", "run"]
        if (
            who["modality"] != "fMRI"
            or d["identity"]["subject"] != selection.subject
            or any(d["identity"][k] != who[k] for k in fields)
        ):
            raise ProtocolError("Preprocessing participant/session/task/run mismatch")
        paths = {k: local_file(roots[a["root"]], a["path"]) for k, a in d["assets"].items()}
        if any(sha256(paths[k]) != a["sha256"] for k, a in d["assets"].items()):
            raise ProtocolError("Changed preprocessing/input evidence")
        source_files = dict(selection.files)
        if paths["raw_bold"] != source_files["image"].resolve() or (
            "structural" in source_files and paths["raw_t1"] != source_files["structural"].resolve()
        ):
            raise ProtocolError("Wrong source BOLD/anatomical reference")
        desc = json.loads(paths["derivative_description"].read_text())
        g = [g for g in desc.get("GeneratedBy", []) if g.get("Name", "").lower() == "fmriprep"]
        if len(g) != 1 or g[0].get("Version") != d["software"]["version"]:
            raise ProtocolError("Conflicting software identity/version")
        transforms = []
        for original in d["transforms"]:
            spec = dict(original)
            for k in ["path", "source_image", "reference"]:
                spec[k] = str(paths[spec[k]])
            if (
                spec["from_space"] == "boldref"
                and spec["to_space"] == "T1w"
                and (Path(spec["reference"]) != paths["t1"])
            ):
                raise ProtocolError("Transform references wrong anatomy")
            if spec["from_space"] == "boldref":
                for field, prefix in [
                    ("subject", "sub"),
                    ("session", "ses"),
                    ("task", "task"),
                    ("run", "run"),
                ]:
                    found = re.findall(
                        r"(?:^|_)" + prefix + r"-([A-Za-z0-9]+)", Path(spec["source_image"]).name
                    )
                    expected = d["identity"][field]
                    if (expected is None and found) or (
                        expected is not None and found != [expected]
                    ):
                        raise ProtocolError("Transform source belongs to a different recording")
            if spec["from_space"] == "T1w" and Path(spec["source_image"]) != paths["t1"]:
                raise ProtocolError("Transform source anatomical reference mismatch")
            transforms.append(spec)
        evidence = {**d["evidence"], "T1_sources": [str(paths["raw_t1"])]}
        bundle = PreprocessingBundle(
            roots["raw"],
            roots["derivatives"],
            paths["raw_bold"],
            paths["bold"],
            paths["mask"],
            paths["confounds"],
            paths["confound_json"],
            paths["t1"],
            d["identity"],
            d["space"],
            tuple(transforms),
            tuple(p for k, p in paths.items() if k.startswith("qc-")),
            evidence,
        )
        base = audit_preprocessing(bundle)
        receipt["legacy_audit_identity"] = base.get("identity")
        check(
            "existing_M14_geometry_transform_provenance",
            base["eligible"],
            "existing audit passes" if base["eligible"] else "existing audit incomplete or failed",
        )
        check(
            "configuration_environment",
            bool(d["configuration"]) and bool(d["environment"]),
            "explicit provenance required; never inferred from output existence",
        )
        check(
            "distortion_correction",
            d["distortion_correction"] in {"APPLIED", "NOT_REQUIRED"}
            and bool(d["evidence"].get("distortion_correction_source")),
            "explicit SDC method/justification evidence required",
        )
        check(
            "BIDS_validation",
            d["bids_validation"] == "PASS" and "bids-report" in paths,
            "actual validation report with PASS and bound content required",
        )
        if "bids-report" in paths:
            report = json.loads(paths["bids-report"].read_text())
            if (
                report.get("status") != "PASS"
                or not report.get("validator")
                or not report.get("version")
                or report.get("input_snapshot_sha256")
                != hashlib.sha256(
                    canonical(
                        {k: a["sha256"] for k, a in d["assets"].items() if a["root"] == "raw"}
                    )
                ).hexdigest()
            ):
                raise ProtocolError("BIDS validation report does not pass")
        if not base["eligible"]:
            receipt["technical_status"] = "BLOCKED"
            return receipt
        run = load_audited_run(bundle, base)
        _, qc = configure_confounds(
            run, json.loads(paths["confound_json"].read_text()), strategy="minimal"
        )
        conf = pd.read_csv(paths["confounds"], sep="\t")
        if conf.columns.duplicated().any() or any(str(c).endswith(".1") for c in conf.columns):
            raise ProtocolError("Duplicate/conflicting confound columns")
        md = json.loads(paths["confound_json"].read_text())
        if (
            "dvars" not in conf
            or not isinstance(md.get("dvars"), dict)
            or not any(md["dvars"].get(k) for k in ["Description", "Method", "LongName"])
        ):
            raise ProtocolError("DVARS values/definitions unavailable")
        dv = conf.dvars.to_numpy(float)
        if not np.isfinite(dv[1:]).all() or np.any(dv[np.isfinite(dv)] < 0):
            raise ProtocolError("DVARS invalid; only first undefined value supported")
        nss = conf.filter(like="non_steady_state_outlier").to_numpy(float)
        if nss.shape[1] and (
            not np.isin(nss, [0, 1]).all()
            or not np.all(nss.sum(axis=0) == 1)
            or np.any(nss.sum(axis=1) > 1)
        ):
            raise ProtocolError("Conflicting or nonbinary nonsteady-state indicators")
        check(
            "nonsteady_state_detection",
            bool(nss.shape[1])
            or d["evidence"].get("nonsteady_state_detection") == "NO_OUTLIERS_DETECTED",
            "detected indicators or explicit no-outlier provenance required",
        )
        motion = conf[["trans_x", "trans_y", "trans_z", "rot_x", "rot_y", "rot_z"]].to_numpy(float)
        if not np.isfinite(motion).all():
            raise ProtocolError("Nonfinite measured motion")
        mask: Any = nib.load(paths["mask"])
        receipt["qc"] = {
            **qc,
            "mask_grid_coverage_fraction": float(np.mean(mask.get_fdata() > 0)),
            "coverage_threshold": None,
            "DVARS_threshold": None,
            "threshold_source": "existing M14 FD>0.5mm, high-motion fraction>0.2, residualDOF<20",
            "nonsteady_state_volumes": int(
                conf.filter(like="non_steady_state_outlier").sum().sum()
            ),
        }
        receipt["technical_status"] = (
            "READY" if all(c["status"] == "READY" for c in checks) else "BLOCKED"
        )
        receipt["qc_status"] = "READY" if qc["eligible"] else "BLOCKED"
        if any(sha256(paths[k]) != a["sha256"] for k, a in d["assets"].items()):
            raise ProtocolError("Preprocessing content changed during audit")
        selection.verify_inputs()
    except (ValueError, OSError, KeyError, TypeError, RuntimeError):
        receipt.update(technical_status="BLOCKED", qc_status="INDETERMINATE")
        check(
            "consistency", False, "missing, changed, incompatible or unsafe preprocessing evidence"
        )
    return receipt
