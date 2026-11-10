"""Refresh only the new inventory; do not modify historical declarations or receipts."""

import hashlib
import json
from pathlib import Path


def main():
    inventory = Path("experiments/milestone19/protocol-inventory.json")
    rows = json.loads(inventory.read_text())
    for row in rows:
        receipt = row["freeze_receipt"]
        if not receipt:
            continue
        value = json.loads(Path(receipt).read_text())
        checks = dict(row.get("recorded_file_hash_checks", {}))
        for field, key in [
            ("configuration", "configuration_file_sha256"),
            ("document", "document_sha256"),
        ]:
            if key in value:
                actual = hashlib.sha256(Path(row[field]).read_bytes()).hexdigest()
                checks[row[field]] = "MATCH" if actual == value[key] else "MISMATCH"
        row["recorded_file_hash_checks"] = checks
        row["receipt_observed_sha256"] = hashlib.sha256(Path(receipt).read_bytes()).hexdigest()
    inventory.write_text(json.dumps(rows, indent=2) + "\n")
    print({"historical_systems": len(rows), "files_modified": "M19 inventory only"})


if __name__ == "__main__":
    main()
