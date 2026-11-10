"""Four bounded controlled histories, scientific amendments and explicit failure evidence."""

from pathlib import Path
from typing import Any

from soma.protocol.binding import example_protocol, example_snapshot
from soma.protocol.model import Protocol, amend, anatomy, methods, seal
from soma.protocol.replay import compare, run, write_execution


def method_amendment(protocol: Protocol, family: str) -> Protocol:
    d = protocol.document()
    d["version"] = "2.0.0"
    if family == "eeg":
        d["requirements"]["stages"]["reference"]["parameters"]["reference"] = "none"
        for a in d["requirements"]["artifacts"].values():
            if a["producer"] in {"reference", "psd", "bands"}:
                a["metadata"]["reference"] = "none"
        d["scientific"]["preprocessing"]["reference"]["reference"] = "none"
    elif family == "mri":
        d["requirements"]["stages"]["segment"]["parameters"]["threshold"] = 1.2
    elif family == "fmri":
        d["requirements"]["stages"]["model"]["parameters"].update(
            hrf_model="glover", noise_model="ar1"
        )
    else:
        d["requirements"]["stages"]["inverse"]["parameters"]["lambda2"] = 0.2
    d["scientific"]["analysis_methods"] = methods(d["requirements"])
    d["scientific"]["anatomical_conventions"] = anatomy(d["requirements"])
    return amend(
        protocol,
        d,
        reason="Explicit exploratory sensitivity; no prospective/confirmatory promotion",
        authorization_reference="local-synthetic-amendment-" + family,
        outcome_inspection="yes",
    )


def demonstrations(root: Path, *, persist: bool = True) -> dict[str, Any]:
    results = {}
    for family in ["eeg", "mri", "fmri", "source"]:
        protocol = example_protocol(family)
        sealed = seal(protocol)
        snapshot = example_snapshot(protocol, count=2 if family == "eeg" else 1)
        first = run(sealed, snapshot, root / family / "cache", sequence=1)
        exact = run(sealed, snapshot, root / family / "exact-cache", sequence=2, reference=first)
        new = example_snapshot(
            protocol,
            count=3 if family == "eeg" else 1,
            identity="snapshot-2",
            session="session-1" if family == "eeg" else "session-2",
        )
        controlled = run(
            sealed, new, root / family / "cache", sequence=3, mode="CONTROLLED", reference=first
        )
        revised = seal(method_amendment(protocol, family))
        exploratory = run(
            revised,
            snapshot,
            root / family / "cache",
            sequence=4,
            mode="EXPLORATORY",
            reference=first,
        )
        records = [first, exact, controlled, exploratory]
        cases = {
            "exact": compare(first, exact),
            "controlled_data": compare(first, controlled, mode="CONTROLLED"),
            "exploratory_method": compare(first, exploratory, mode="EXPLORATORY"),
            "false_controlled_method": compare(first, exploratory, mode="CONTROLLED"),
        }
        if (
            not cases["exact"]["authorized"]
            or not cases["controlled_data"]["authorized"]
            or not cases["exploratory_method"]["authorized"]
            or cases["false_controlled_method"]["authorized"]
        ):
            raise ValueError("Unexpected replay authorization decision: " + family)
        if family == "source":
            physical = protocol.document()
            physical["version"] = "2.0.0"
            physical["scientific"]["source_conductivity"] = {
                "S_m": [0.3, 0.006, 0.3],
                "status": "proposed physical model; toy unsupported",
            }
            proposed = seal(
                amend(
                    protocol,
                    physical,
                    reason="Changed conductivity assumptions require a physical forward model",
                    authorization_reference="local-source-physical-proposal",
                    outcome_inspection="yes",
                )
            )
            blocked = run(
                proposed,
                snapshot,
                root / family / "cache",
                sequence=5,
                mode="EXPLORATORY",
                reference=first,
            )
            records.append(blocked)
            cases["unsupported_conductivity"] = compare(first, blocked, mode="EXPLORATORY")
            if blocked.record()["status"] == "COMPLETE":
                raise ValueError("Unsupported conductivity silently executed")
        if persist:
            for record in records:
                write_execution(
                    record, root / family / ("execution-" + str(record.record()["sequence"]))
                )
        baseline = first.record()
        results[family] = {
            "baseline_execution": baseline,
            "protocol_fingerprint": protocol.fingerprint,
            "scientific_fingerprint": protocol.scientific_fingerprint,
            "cases": cases,
            "baseline_numerical_summaries": {
                m["unit_id"] + "--" + m["session"]: m["numerical_summary"]
                for m in baseline["members"]
            },
            "baseline_workflow_semantics": {
                m["unit_id"]: m["workflow_semantics"] for m in baseline["members"]
            },
            "baseline_file_fingerprints": {
                m["unit_id"]: m["artifact_file_fingerprints"] for m in baseline["members"]
            },
            "baseline_input_fingerprints": {
                m["unit_id"]: m["input_content_fingerprints"] for m in baseline["members"]
            },
            "baseline_artifact_fingerprints": {
                m["unit_id"]: m["artifact_content_fingerprints"] for m in baseline["members"]
            },
            "independent_reference": [m.get("independent_reference") for m in baseline["members"]],
            "execution_count": len(records),
            "unit_counts": [len(r.record()["members"]) for r in records],
            "environment": baseline["environment"],
            "tolerances": protocol.document()["tolerances"],
            "interpretation": "synthetic descriptive histories, not human longitudinal validation",
        }
    return {
        "schema": "soma.protocol.demonstrations/1.0.0",
        "families": results,
        "all_passed": True,
        "cache_interchangeability": False,
        "confirmatory_replication_authorized": False,
    }
