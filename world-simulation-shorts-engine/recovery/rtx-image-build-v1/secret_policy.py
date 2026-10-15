"""One byte-bound public metadata exception for the pinned Gitleaks scanner.

This does not suppress a file or a rule: both the canonical file path and the
complete public cache-fingerprint field must match. All default rules remain
enabled. The original metadata must pass its byte digest before configuration
is written; an altered source requires a separate review, not a wider policy.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat


METADATA_RELATIVE = "repo/world-simulation-shorts-engine/assets/flat/SOURCES.json"
METADATA_SHA256 = "20e51ab95c7d524d8a8f2f34769deb3d59e5b446eafa633068381b99a04e6b17"
PUBLIC_CONTENT_DIGEST = "99a6ebfafb2f78a29cea244d9a20cf732c619c4c97db868bf98255f34ec26624"
SCANNER_VERSION = "8.24.3"
MAX_METADATA_BYTES = 64 * 1024


class PolicyError(RuntimeError):
    """A fixed reason code, without source contents or scanner findings."""


def _metadata_bytes(scanroot: Path) -> bytes:
    path = scanroot
    for part in METADATA_RELATIVE.split("/"):
        path = path / part
        if path.is_symlink():
            raise PolicyError("PUBLIC_METADATA_SYMLINK")
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_METADATA_BYTES:
                raise PolicyError("PUBLIC_METADATA_TYPE_OR_SIZE")
            body = stream.read(MAX_METADATA_BYTES + 1)
    except OSError as error:
        raise PolicyError("PUBLIC_METADATA_UNREADABLE") from error
    if len(body) > MAX_METADATA_BYTES:
        raise PolicyError("PUBLIC_METADATA_TYPE_OR_SIZE")
    return body


def write_config(scanroot: str | os.PathLike[str], dest: str | os.PathLike[str]) -> dict:
    """Validate pinned metadata and create a narrow Gitleaks 8.24.3 config.

    ``scanroot`` is the copied /opt/rtx-package directory, containing ``repo``.
    ``dest`` must be a new file; it should live outside the scanned directory.
    The returned receipt contains only public hashes and fixed policy details.
    """
    root = Path(scanroot).absolute()
    if root.is_symlink() or not root.is_dir():
        raise PolicyError("PUBLIC_METADATA_ROOT_INVALID")
    # Bind the path to the actual copied tree, avoiding a symlinked root alias.
    if root.resolve(strict=True) != root:
        raise PolicyError("PUBLIC_METADATA_ROOT_INVALID")
    body = _metadata_bytes(root)
    if hashlib.sha256(body).hexdigest() != METADATA_SHA256:
        raise PolicyError("PUBLIC_METADATA_SHA_MISMATCH")
    try:
        metadata = json.loads(body)
        valid = (isinstance(metadata, list) and len(metadata) > 1
                 and isinstance(metadata[1], dict)
                 and metadata[1].get("cache_key") == PUBLIC_CONTENT_DIGEST)
    except (ValueError, UnicodeError):
        valid = False
    if not valid:
        raise PolicyError("PUBLIC_METADATA_FIELD_MISMATCH")

    relative = re.escape(METADATA_RELATIVE)
    absolute_prefix = re.escape(root.as_posix() + "/")
    path_pattern = "^(?:" + absolute_prefix + ")?" + relative + "$"
    field_pattern = (r'^\s*"cache_key"\s*:\s*"' + PUBLIC_CONTENT_DIGEST
                     + r'"\s*,?\s*$')
    # In 8.24.3 the global [allowlist] ignores condition="AND". The legacy
    # rule-scoped table honors it, and this id-only extension retains the
    # original default rule's detector rather than replacing its regex.
    config = ("[extend]\nuseDefault = true\n\n"
              "[[rules]]\nid = \"generic-api-key\"\n"
              "[rules.allowlist]\n"
              'description = "Pinned public request fingerprint field"\n'
              'condition = "AND"\nregexTarget = "line"\n'
              "paths = [" + json.dumps(path_pattern) + "]\n"
              "regexes = [" + json.dumps(field_pattern) + "]\n")
    encoded = config.encode("utf-8")
    try:
        with Path(dest).open("xb") as stream:
            stream.write(encoded)
    except OSError as error:
        raise PolicyError("PUBLIC_POLICY_DESTINATION_INVALID") from error
    return {
        "schema": "rtx-public-metadata-secret-policy-v1",
        "metadataFile": METADATA_RELATIVE,
        "metadataSha256": METADATA_SHA256,
        "publicContentDigest": PUBLIC_CONTENT_DIGEST,
        "field": "JSON[1].cache_key",
        "gitleaksVersion": SCANNER_VERSION,
        "ruleId": "generic-api-key",
        "allowlistScope": "rules.allowlist",
        "condition": "AND",
        "configSha256": hashlib.sha256(encoded).hexdigest(),
    }
