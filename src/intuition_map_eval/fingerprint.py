from __future__ import annotations

import hashlib
from pathlib import Path


def canonical_text_bytes(path: Path) -> bytes:
    """Return UTF-8 text with physical newlines canonicalized to LF."""

    with path.open("r", encoding="utf-8", newline=None) as handle:
        return handle.read().encode("utf-8")


def canonical_text_sha256(path: Path) -> str:
    return hashlib.sha256(canonical_text_bytes(path)).hexdigest()
