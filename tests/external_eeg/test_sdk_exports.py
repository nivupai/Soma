"""Documented SDK surface must delegate to the audited implementation."""

from soma.external_eeg import contracts, data, models, runtime
from soma.sdk import eeg_benchmark as sdk


def test_external_sdk_exports(tmp_path):
    for name, implementation in {
        "external_audit": contracts.candidate_audit,
        "external_inventory": data.inventory,
        "external_plan": contracts.plan,
        "seal_external_plan": contracts.seal_plan,
        "external_compatibility": contracts.compatibility,
        "import_external_model": models.import_model,
        "predict_frozen_external": models.predict,
        "run_external": runtime.run,
        "verify_external": runtime.read_receipt,
        "compare_external": runtime.compare,
    }.items():
        assert getattr(sdk, name) is implementation
    audit = sdk.external_audit()
    runtime.write_receipt(audit, tmp_path / "receipt")
    assert sdk.external_domain_shift(tmp_path / "receipt" / "result.json") == audit["domain_shift"]
