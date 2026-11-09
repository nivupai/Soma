"""Public registry manifests only; never download container layers."""

import json
import urllib.request
from pathlib import Path


def main() -> None:
    root = Path("data/derived/milestone141")
    token = json.load(
        urllib.request.urlopen(
            "https://auth.docker.io/token?service=registry.docker.io&scope=repository:nipreps/fmriprep:pull",
            timeout=30,
        )
    )["token"]
    request = urllib.request.Request(
        "https://registry-1.docker.io/v2/nipreps/fmriprep/manifests/25.2.7",
        headers={
            "Authorization": "Bearer " + token,
            "Accept": (
                "application/vnd.oci.image.index.v1+json, "
                "application/vnd.docker.distribution.manifest.list.v2+json, "
                "application/vnd.docker.distribution.manifest.v2+json"
            ),
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        digest = response.headers.get("Docker-Content-Digest")
        manifest = json.load(response)
    (root / "image-manifest.json").write_text(
        json.dumps(
            {
                "image": "nipreps/fmriprep:25.2.7",
                "digest": digest,
                "manifest": manifest,
                "local_image_available": False,
                "layers_downloaded": False,
            },
            indent=2,
        )
        + "\n"
    )
    print("Pinned public image manifest recorded; no layers downloaded.")


if __name__ == "__main__":
    main()
