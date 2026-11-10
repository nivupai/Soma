"""Path-free provenance exports; pseudonyms still require controlled access."""

import re
from typing import Any

_LOCATION = re.compile(
    r"""(^|[\s=(:"'])(?:/(?!/)[^\s,;]+|[A-Za-z]:[\\/][^\s,;]+|file://[^\s,;]+)"""
)
_PRIVATE = {
    "root",
    "roots",
    "path",
    "paths",
    "private",
    "secret",
    "credentials",
    "token",
    "home",
    "input_root",
    "cache_root",
    "subject",
    "subject_id",
    "subject_name",
    "participant",
    "participants",
    "participant_id",
    "participant_name",
}


def redact_export(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            k: redact_export(v)
            for k, v in value.items()
            if k.lower() not in _PRIVATE
            and not _LOCATION.search(k)
            and not k.lower().endswith(("_path", "_paths", "_root"))
        }
    if isinstance(value, (list, tuple)):
        return [redact_export(v) for v in value]
    if isinstance(value, str):
        return _LOCATION.sub(lambda match: match.group(1) + "[redacted private location]", value)
    return value
