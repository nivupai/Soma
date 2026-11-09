"""Pinned official Linux x64 scanner download with hard-coded archive SHA256."""

import hashlib
import io
import sys
import tarfile
import urllib.request
from pathlib import Path

url = "https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_linux_x64.tar.gz"
expected = "551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb"
data = urllib.request.urlopen(url, timeout=90).read()
assert hashlib.sha256(data).hexdigest() == expected
with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
    member = archive.getmember("gitleaks")
    assert member.isfile()
    target = Path(sys.argv[1])
    target.write_bytes(archive.extractfile(member).read())
    target.chmod(0o700)
