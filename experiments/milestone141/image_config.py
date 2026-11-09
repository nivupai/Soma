"""Read only public container configuration (no layer download)."""

import json
import urllib.request
from pathlib import Path

p = Path("data/derived/milestone141/image-manifest.json")
record = json.loads(p.read_text())
token = json.load(
    urllib.request.urlopen(
        "https://auth.docker.io/token?service=registry.docker.io&scope=repository:nipreps/fmriprep:pull",
        timeout=30,
    )
)["token"]
digest = record["manifest"]["config"]["digest"]
request = urllib.request.Request(
    "https://registry-1.docker.io/v2/nipreps/fmriprep/blobs/" + digest,
    headers={"Authorization": "Bearer " + token},
)
with urllib.request.urlopen(request, timeout=30) as response:
    metadata = json.load(response)
record["architecture"] = metadata.get("architecture")
record["os"] = metadata.get("os")
record["compressed_layer_bytes"] = sum(layer["size"] for layer in record["manifest"]["layers"])
record["config_digest"] = digest
p.write_text(json.dumps(record, indent=2) + "\n")
print("Pinned image configuration architecture recorded; no layers downloaded.")
