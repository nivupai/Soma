"""Real PyBIDS/schema indexing and cache invalidation on small synthetic files."""

import json
from dataclasses import replace

import nibabel as nib
import pytest
from typer.testing import CliRunner

from soma.cli import app
from soma.experiments.fmri_simulation import simulate
from soma.fmri.design import Contrast, ModelConfig
from soma.fmri.ingestion import inspect_functional, select_run
from soma.fmri.records import load_run
from soma.fmri.workflows import analyze
from soma.imaging.nifti import save_nifti


@pytest.fixture
def dataset(tmp_path):
    run, _ = simulate()
    root = tmp_path / "raw"
    root.mkdir()
    (root / "dataset_description.json").write_text(
        json.dumps({"Name": "Synthetic fMRI", "BIDSVersion": "1.11.2"})
    )
    (root / "task-task_bold.json").write_text(
        json.dumps({"RepetitionTime": 2.0, "TaskName": "task"})
    )
    folder = root / "sub-01/ses-A/func"
    folder.mkdir(parents=True)
    name = "sub-01_ses-A_task-task_run-1"
    image = folder / (name + "_bold.nii.gz")
    nib.save(run.image, image)
    run.events.to_csv(root / "task-task_events.tsv", sep="\t", index=False)
    mask = tmp_path / "mask.nii.gz"
    save_nifti(run.mask, mask)
    deriv = tmp_path / "external-derivatives"
    deriv.mkdir()
    (deriv / "dataset_description.json").write_text(
        json.dumps(
            {
                "Name": "Synthetic external preprocessing",
                "BIDSVersion": "1.11.2",
                "DatasetType": "derivative",
                "GeneratedBy": [{"Name": "test", "Version": "1"}],
            }
        )
    )
    target = deriv / "sub-01/ses-A/func"
    target.mkdir(parents=True)
    pre = target / (name + "_space-synthetic_desc-preproc_bold.nii.gz")
    nib.save(run.image, pre)
    save_nifti(run.mask, target / (name + "_space-synthetic_desc-brain_mask.nii.gz"))
    run.confounds.to_csv(target / (name + "_desc-confounds_timeseries.tsv"), sep="\t", index=False)
    return root, deriv, mask, image


def test_bids_inheritance_and_preprocessing_boundary(dataset):
    root, deriv, mask, _ = dataset
    info = inspect_functional(root)
    assert len(info["BOLD"]) == 1 and info["BOLD"][0]["metadata"]["RepetitionTime"] == 2
    with pytest.raises(ValueError, match="Raw"):
        select_run(root, subject="01", task="task", mask=mask)
    r = select_run(root, subject="01", task="task", mask=mask, exploratory_raw=True)
    assert r.preprocessing == "unvalidated-educational" and len(r.events) > 0
    r = select_run(
        root,
        subject="01",
        task="task",
        session="A",
        run="1",
        space="synthetic",
        derivatives=deriv,
        preprocessing_evidence={"pipeline": "explicit synthetic test"},
    )
    assert r.preprocessing == "validated" and r.identity == ("01", "A", "task", "1", "synthetic")
    assert list(r.confounds) == ["motion", "trend"]


def test_missing_events_and_ambiguous_runs(dataset):
    root, _, mask, image = dataset
    other = image.with_name(image.name.replace("run-1", "run-2"))
    nib.save(nib.load(image), other)
    with pytest.raises(ValueError, match="ambiguous"):
        select_run(root, subject="01", task="task", mask=mask, exploratory_raw=True)
    (root / "task-task_events.tsv").unlink()
    with pytest.raises(ValueError, match="events"):
        select_run(root, subject="01", task="task", run="1", mask=mask, exploratory_raw=True)


def test_missing_confounds_evidence_and_TR(dataset):
    root, deriv, mask, _ = dataset
    with pytest.raises(ValueError, match="evidence"):
        select_run(root, subject="01", task="task", space="synthetic", derivatives=deriv)
    next(deriv.rglob("*timeseries.tsv")).unlink()
    with pytest.raises(ValueError, match="confounds"):
        select_run(
            root,
            subject="01",
            task="task",
            space="synthetic",
            derivatives=deriv,
            preprocessing_evidence={"test": True},
        )
    (root / "task-task_bold.json").write_text(json.dumps({"RepetitionTime": 3.0}))
    with pytest.raises(ValueError, match="TR"):
        select_run(root, subject="01", task="task", mask=mask, exploratory_raw=True)


def test_coded_qform_conflict_rejected(dataset):
    root, _, mask, image = dataset
    bold = nib.load(image)
    affine = bold.affine.copy()
    affine[0, 3] += 10
    bold.set_qform(affine, code=2)
    nib.save(bold, image)
    with pytest.raises(ValueError, match="Ambiguous"):
        load_run(
            image,
            tr=2,
            subject="01",
            session="A",
            task="task",
            run="1",
            space="native",
            events=root / "task-task_events.tsv",
            confounds=None,
            mask=mask,
            preprocessing="unvalidated-educational",
            provenance={"source": str(image)},
        )


def test_pipeline_schema_resume_and_hash_invalidation(tmp_path):
    run, _ = simulate()
    cfg = ModelConfig(noise_model="ols", drift_model=None, confound_columns=("motion", "trend"))
    c = Contrast("task", {"task": 1})
    output = tmp_path / "analysis"
    result = analyze(run, cfg, c, output)
    assert result["export"]["schema_status"] == "PASS"
    assert (
        output
        / "soma-reports/sub-synthetic_ses-development_task-task_run-1_task_effect_size.nii.gz"
    ).exists()
    assert analyze(run, cfg, c, output, resume=True)["verified_output_reuse"] is True
    with pytest.raises(ValueError, match="Stale"):
        analyze(run, replace(cfg, q=0.01), c, output, resume=True)
    with pytest.raises(FileExistsError):
        analyze(run, cfg, c, output)
    data = run.image.get_fdata().copy()
    data[0, 0, 0, 0] += 1
    changed = replace(run, image=nib.Nifti1Image(data, run.image.affine, run.image.header))
    with pytest.raises(ValueError, match="Stale"):
        analyze(changed, cfg, c, output, resume=True)
    (output / "roi.json").write_text("corruption")
    with pytest.raises(ValueError, match="Corrupt"):
        analyze(run, cfg, c, output, resume=True)


def test_cli_inspection_and_optional_retest_no_false_success(dataset, tmp_path):
    root, *_ = dataset
    r = CliRunner().invoke(app, ["fmri", "inspect", "--input", str(root)])
    assert r.exit_code == 0 and "Raw BIDS" in r.stdout
    config = tmp_path / "retest.yaml"
    config.write_text("dataset: ds000114\n")
    r = CliRunner().invoke(
        app, ["fmri", "retest", "--config", str(config), "--output", str(tmp_path / "unavailable")]
    )
    assert r.exit_code == 1 and "preprocessed" in r.stdout
    assert not (tmp_path / "unavailable").exists()


def test_wrong_task_events_never_substituted(dataset):
    root, _, mask, _ = dataset
    path = root / "task-task_events.tsv"
    path.rename(root / "task-other_events.tsv")
    with pytest.raises(ValueError, match="events"):
        select_run(root, subject="01", task="task", mask=mask, exploratory_raw=True)


def test_wrong_subject_mask_identity(dataset):
    root, _, mask, _ = dataset
    wrong = mask.with_name("sub-02_desc-brain_mask.nii.gz")
    wrong.write_bytes(mask.read_bytes())
    with pytest.raises(ValueError, match="identity"):
        select_run(root, subject="01", task="task", mask=wrong, exploratory_raw=True)
