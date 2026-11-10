"""Small generated NIfTI/BIDS fixtures; no actual participant files enter CI."""

import gzip
import hashlib
import json

import nibabel as nib
import numpy as np
import pytest

from soma.human.adapters import Selection, bids_fmri, identity, mri, role_file
from soma.human.model import Identity, chronology
from soma.human.permissions import evidence
from soma.human.workflow import freeze_cohort, read_execution, run, template
from soma.protocol.model import ProtocolError

KEY = bytes(range(32))


def save(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    image = nib.Nifti1Image(np.asarray(values), np.diag([1.0, 1.0, 1.5, 1.0]))
    image.set_sform(image.affine, code=1)
    image.set_qform(image.affine, code=1)
    image.header.set_xyzt_units("mm", "sec")
    nib.save(image, path)


def bids(root):
    (root / "dataset_description.json").write_text(
        json.dumps(
            {
                "Name": "Explicit synthetic fixture",
                "BIDSVersion": "1.8.0",
                "License": "CC0",
                "DatasetDOI": "doi:10.18112/openneuro.ds000114.v1.0.2",
            }
        )
    )
    (root / "task-fingerfootlips_bold.json").write_text(
        json.dumps({"TaskName": "finger_foot_lips", "RepetitionTime": 2.0})
    )
    (root / "task-fingerfootlips_events.tsv").write_text(
        "onset\tduration\ttrial_type\n0\t5\tFinger\n"
    )
    for session in ["alpha", "beta"]:
        save(
            root
            / f"sub-fiction/ses-{session}/func"
            / f"sub-fiction_ses-{session}_task-fingerfootlips_bold.nii.gz",
            np.ones((4, 4, 4, 20), np.float32),
        )
        save(
            root / f"sub-fiction/ses-{session}/anat/sub-fiction_ses-{session}_T1w.nii.gz",
            np.ones((4, 4, 4), np.float32),
        )


def test_real_bids_adapter_validates_synthetic_two_sessions_without_inventing_runs(tmp_path):
    bids(tmp_path)
    rows = bids_fmri(tmp_path, "fiction", KEY)
    assert len(rows) == 2
    assert {r.identity.document()["session"] for r in rows} == {"alpha", "beta"}
    assert all(r.identity.document()["run"] is None for r in rows)
    assert all(not r.facts()["compatible_preprocessing_evidence"] for r in rows)
    assert all(r.facts()["events_count"] == 1 for r in rows)


@pytest.mark.parametrize("bad", ["task", "TR", "events", "directory", "duplicate"])
def test_invalid_bids_metadata_or_identity_rejected(tmp_path, bad):
    bids(tmp_path)
    if bad == "task":
        (tmp_path / "task-fingerfootlips_bold.json").write_text(
            '{"TaskName":"unrelated","RepetitionTime":2.0}'
        )
    elif bad == "TR":
        (tmp_path / "task-fingerfootlips_bold.json").write_text(
            '{"TaskName":"fingerfootlips","RepetitionTime":0}'
        )
    elif bad == "events":
        (tmp_path / "task-fingerfootlips_events.tsv").write_text(
            "onset\tduration\ttrial_type\n100\t5\tFinger\n"
        )
    else:
        original = (
            tmp_path
            / "sub-fiction/ses-alpha/func/sub-fiction_ses-alpha_task-fingerfootlips_bold.nii.gz"
        )
        destination = (
            original.with_name("sub-wrong_ses-alpha_task-fingerfootlips_bold.nii.gz")
            if bad == "directory"
            else original.with_suffix("")
        )
        if bad == "directory":
            original.rename(destination)
        else:
            with gzip.open(original, "rb") as f:
                destination.write_bytes(f.read())
    with pytest.raises((ValueError, KeyError)):
        bids_fmri(tmp_path, "fiction" if bad != "directory" else "wrong", KEY)


def test_role_duplicates_require_identical_decompressed_content(tmp_path):
    raw = tmp_path / "image.nii"
    compressed = tmp_path / "image.nii.gz"
    raw.write_bytes(b"explicit synthetic file bytes")
    with gzip.open(compressed, "wb") as f:
        f.write(raw.read_bytes())
    assert role_file(tmp_path, "image") == compressed
    raw.write_bytes(b"changed")
    with pytest.raises(ProtocolError):
        role_file(tmp_path, "image")


def test_actual_registered_mri_pipeline_uses_independent_fixture_reference(tmp_path):
    root = tmp_path / "dataset"
    folder = root / "IBSR_01"
    folder.mkdir(parents=True)
    labels = np.zeros((16, 16, 16), np.int16)
    labels[2:7, 2:14, 2:14] = 1
    labels[7:11, 2:14, 2:14] = 2
    labels[11:14, 2:14, 2:14] = 3
    intensity = np.take(np.array([0, 20, 80, 160], np.float32), labels)
    save(folder / "IBSR_01_ana_strip.nii.gz", intensity)
    save(folder / "IBSR_01_segTRI_ana.nii.gz", labels)
    notice = tmp_path / "notice.txt"
    notice.write_text("Synthetic fixture notice: Torsten Rohlfing public domain")
    selected = mri(root, "ibsr-v2", "IBSR_01", KEY)
    use = evidence(
        "ibsr-v2",
        "v2-stripped",
        notice.read_bytes(),
        source="explicit-synthetic-notice",
        license="LOCAL-ROHLFING-NOTICE",
        supported=True,
    )
    protocol = freeze_cohort(template("ibsr-v2", "v2-stripped"), [selected.identity])
    result = run(
        protocol,
        [selected],
        use,
        notice,
        cache=tmp_path / "cache",
        output=tmp_path / "result",
        sequence=1,
    )
    assert result["status"] == "COMPLETE"
    unit = result["units"][0]
    assert not unit["outcome"]["truth_used_for_prediction"]
    assert len(unit["outcome"]["values"]["labels"]) == 3
    for row in unit["outcome"]["values"]["labels"]:
        assert 0 <= row["Dice"] <= 1 and 0 <= row["Jaccard"] <= 1
    assert (
        read_execution(tmp_path / "result/result.json")["record_sha256"] == result["record_sha256"]
    )
    assert str(tmp_path) not in json.dumps(result)
    assert unit["graph"]["artifacts"][0]["metadata"]["subject_identity"].startswith("subject-")
    repeat = run(
        protocol,
        [selected],
        use,
        notice,
        cache=tmp_path / "cache",
        output=tmp_path / "repeat",
        sequence=2,
    )
    assert repeat["units"][0]["workflow"]["stages"][0]["cached"]
    from soma.human.workflow import compare

    assert compare(result, repeat)["authorized"]
    from soma.human.permissions import PermissionEvidence

    changed = use.document()
    changed["agreement_version"] = "new-explicit-review"
    revised = PermissionEvidence.from_dict(changed)
    third = run(
        protocol,
        [selected],
        revised,
        notice,
        cache=tmp_path / "cache",
        output=tmp_path / "revised",
        sequence=3,
    )
    assert not third["units"][0]["workflow"]["stages"][0]["cached"]
    assert (
        third["units"][0]["workflow"]["stages"][0]["cache_key"]
        != unit["workflow"]["stages"][0]["cache_key"]
    )
    assert not compare(result, third)["authorized"]


def test_private_input_symlink_and_content_changes_block_execution(tmp_path):
    file = tmp_path / "input"
    file.write_bytes(b"fiction")
    who = identity(
        "ibsr-v2",
        "v2-stripped",
        "fixture",
        KEY,
        modality="MRI",
        task="structural",
        hashes=[hashlib.sha256(b"fiction").hexdigest()],
    )
    s = Selection(
        who,
        tmp_path,
        "fixture",
        (("image", file),),
        (("image", hashlib.sha256(b"fiction").hexdigest()),),
        b"{}",
        key=KEY,
    )
    s.verify_inputs()
    file.write_bytes(b"changed")
    with pytest.raises(ValueError):
        s.verify_inputs()


def test_acquisition_chronology_requires_matching_source_not_session_names():
    records = []
    sources = {}
    for session, date in [
        ("test", "2021-01-02T00:00:00+00:00"),
        ("retest", "2021-01-01T00:00:00+00:00"),
    ]:
        raw = json.dumps({"AcquisitionDateTime": date}).encode()
        h = hashlib.sha256(raw).hexdigest()
        sources[h] = raw
        d = identity(
            "fixture",
            "1",
            "person",
            KEY,
            modality="fMRI",
            task="motor",
            session=session,
            hashes=[h],
        ).document()
        d["chronology"] = {"acquired_at": date, "source_sha256": h}
        records.append(Identity.from_dict(d))
    assert chronology(*records, sources)["order"] == "right-before-left"
    d = records[0].document()
    d["chronology"]["acquired_at"] = "2020-01-01T00:00:00+00:00"
    with pytest.raises(ValueError):
        chronology(Identity.from_dict(d), records[1], sources)
