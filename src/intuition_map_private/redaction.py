from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

REDACTION_RULESET_VERSION = "0.1.0"

_RULES = (
    (
        "OPENAI_API_KEY",
        re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
    ),
    (
        "EMAIL",
        re.compile(
            r"\b[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
            r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+\b"
        ),
    ),
    (
        "US_SSN",
        re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)"),
    ),
    (
        "PHONE",
        re.compile(
            r"(?<!\w)(?:\+?1[-.\s]?)?"
            r"(?:\(\d{3}\)|\d{3})[-.\s]?\d{3}[-.\s]?\d{4}(?!\w)"
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class RedactionFinding:
    kind: str
    match_sha256: str

    def to_dict(self) -> dict[str, str]:
        return {
            "kind": self.kind,
            "match_sha256": self.match_sha256,
        }


@dataclass(frozen=True, slots=True)
class RedactionResult:
    text: str
    findings: tuple[RedactionFinding, ...]
    ruleset_version: str = REDACTION_RULESET_VERSION


def redact_text(text: str) -> RedactionResult:
    if not isinstance(text, str):
        raise ValueError("redaction input must be a string")
    findings: list[RedactionFinding] = []
    redacted = text
    for kind, pattern in _RULES:
        def replace(match: re.Match[str]) -> str:
            findings.append(
                RedactionFinding(
                    kind=kind,
                    match_sha256=hashlib.sha256(
                        match.group(0).encode("utf-8")
                    ).hexdigest(),
                )
            )
            return f"<REDACTED:{kind}>"

        redacted = pattern.sub(replace, redacted)
    return RedactionResult(text=redacted, findings=tuple(findings))
