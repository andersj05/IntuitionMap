from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from intuition_map_eval.schema import parse_timestamp
from intuition_map_private.policy import ConsentReceipt, timestamp, utc_now
from intuition_map_private.redaction import redact_text
from intuition_map_private.store import PrivateWorkspace


def _non_empty(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _strings(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    result = tuple(_non_empty(item, field) for item in value)
    if len(result) != len(set(result)):
        raise ValueError(f"{field} must not contain duplicates")
    return result


@dataclass(frozen=True, slots=True)
class ImportRecord:
    source_type: str
    source_id: str
    source_version: str
    captured_at: datetime
    text: str
    contexts: tuple[str, ...]
    explicit_links: tuple[str, ...]
    provenance: dict[str, Any]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ImportRecord:
        required = {
            "source_type",
            "source_id",
            "source_version",
            "captured_at",
            "text",
        }
        optional = {"contexts", "explicit_links", "provenance"}
        missing = required - data.keys()
        unknown = data.keys() - required - optional
        if missing or unknown:
            raise ValueError(
                f"import record fields differ; missing={sorted(missing)}, "
                f"unknown={sorted(unknown)}"
            )
        source_id = _non_empty(data["source_id"], "source_id")
        explicit_links = _strings(
            data.get("explicit_links", []), "explicit_links"
        )
        if source_id in explicit_links:
            raise ValueError("an import record cannot explicitly link to itself")
        provenance = data.get("provenance", {})
        if not isinstance(provenance, dict):
            raise ValueError("provenance must be an object")
        try:
            json.dumps(provenance)
        except (TypeError, ValueError) as exc:
            raise ValueError("provenance must be JSON serializable") from exc
        return cls(
            source_type=_non_empty(data["source_type"], "source_type"),
            source_id=source_id,
            source_version=_non_empty(
                data["source_version"], "source_version"
            ),
            captured_at=parse_timestamp(data["captured_at"]),
            text=_non_empty(data["text"], "text"),
            contexts=_strings(data.get("contexts", []), "contexts"),
            explicit_links=explicit_links,
            provenance=provenance,
        )

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "source_type": self.source_type,
            "source_id": self.source_id,
            "source_version": self.source_version,
            "captured_at": timestamp(self.captured_at),
            "text": self.text,
            "contexts": list(self.contexts),
            "explicit_links": list(self.explicit_links),
            "provenance": self.provenance,
        }

    @property
    def record_sha256(self) -> str:
        return hashlib.sha256(
            json.dumps(
                self.canonical_dict(),
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()


def load_import_jsonl(path: str | Path) -> tuple[ImportRecord, ...]:
    path = Path(path)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as exc:
        raise ValueError(f"missing import file: {path}") from exc
    records: list[ImportRecord] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"{path.name}:{line_number}: invalid JSON: {exc.msg}"
            ) from exc
        if not isinstance(value, dict):
            raise ValueError(
                f"{path.name}:{line_number}: expected a JSON object"
            )
        try:
            records.append(ImportRecord.from_dict(value))
        except ValueError as exc:
            raise ValueError(f"{path.name}:{line_number}: {exc}") from exc
    if not records:
        raise ValueError("import file contains no records")
    keys = [
        (record.source_type, record.source_id, record.source_version)
        for record in records
    ]
    if len(keys) != len(set(keys)):
        raise ValueError("import file contains duplicate source versions")
    return tuple(records)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _thought_id(participant_id: str, record: ImportRecord) -> str:
    payload = "\0".join(
        (
            participant_id,
            record.source_type,
            record.source_id,
            record.source_version,
        )
    ).encode("utf-8")
    return f"th_{hashlib.sha256(payload).hexdigest()[:24]}"


def _weak_label_id(source_id: str, target_id: str) -> str:
    payload = f"{source_id}\0{target_id}\0explicit_link".encode("utf-8")
    return f"weak_{hashlib.sha256(payload).hexdigest()[:24]}"


def _resolve_explicit_links(
    connection: sqlite3.Connection,
    participant_id: str,
) -> tuple[int, int, int]:
    resolved = 0
    unresolved = 0
    not_prior = 0
    links = connection.execute(
        """
        SELECT
            l.link_id,
            l.source_thought_id,
            l.target_source_id,
            l.observed_at,
            l.provenance_json,
            s.source_type,
            s.captured_at
        FROM explicit_links l
        JOIN thoughts s ON s.thought_id = l.source_thought_id
        WHERE l.participant_id=?
        """,
        (participant_id,),
    ).fetchall()
    for link in links:
        candidates = connection.execute(
            """
            SELECT thought_id, captured_at
            FROM thoughts
            WHERE participant_id=?
              AND source_type=?
              AND source_id=?
            ORDER BY captured_at DESC, source_version DESC
            """,
            (
                participant_id,
                link["source_type"],
                link["target_source_id"],
            ),
        ).fetchall()
        earlier = [
            candidate
            for candidate in candidates
            if parse_timestamp(candidate["captured_at"])
            < parse_timestamp(link["captured_at"])
        ]
        if earlier:
            target_id = earlier[0]["thought_id"]
            connection.execute(
                """
                UPDATE explicit_links
                SET target_thought_id=?, resolution_status='resolved'
                WHERE link_id=?
                """,
                (target_id, link["link_id"]),
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO weak_labels(
                    weak_label_id, participant_id, source_thought_id,
                    target_thought_id, signal_source, confidence,
                    observed_at, provenance_json
                ) VALUES(?, ?, ?, ?, 'explicit_link', 1.0, ?, ?)
                """,
                (
                    _weak_label_id(
                        link["source_thought_id"], target_id
                    ),
                    participant_id,
                    link["source_thought_id"],
                    target_id,
                    link["observed_at"],
                    link["provenance_json"],
                ),
            )
            resolved += 1
        elif candidates:
            connection.execute(
                """
                UPDATE explicit_links
                SET target_thought_id=NULL, resolution_status='not_prior'
                WHERE link_id=?
                """,
                (link["link_id"],),
            )
            not_prior += 1
        else:
            connection.execute(
                """
                UPDATE explicit_links
                SET target_thought_id=NULL, resolution_status='unresolved'
                WHERE link_id=?
                """,
                (link["link_id"],),
            )
            unresolved += 1
    return resolved, unresolved, not_prior


def import_jsonl(
    workspace: PrivateWorkspace,
    *,
    participant_id: str,
    path: str | Path,
) -> dict[str, Any]:
    workspace.validate()
    if workspace.has_protected_manifest(participant_id):
        raise ValueError(
            "private imports are frozen after the protected test manifest"
        )
    path = Path(path).resolve()
    records = load_import_jsonl(path)
    source_types = sorted({record.source_type for record in records})
    if len(source_types) != 1:
        raise ValueError(
            "one import file must contain exactly one source_type"
        )
    receipt: ConsentReceipt = workspace.active_consent(
        participant_id,
        purpose="local_retrieval_research",
        source_type=source_types[0],
    )
    if not receipt.allow_derived_features:
        raise ValueError(
            "active consent does not allow the derived redacted view"
        )
    source_hash = _file_sha256(path)
    source_bytes = path.stat().st_size
    import_id = f"import_{uuid.uuid4().hex}"
    imported_at = timestamp(utc_now())
    inserted = 0
    reused = 0

    with workspace.connect() as connection:
        decisions: list[tuple[ImportRecord, str, bool]] = []
        for record in records:
            thought_id = _thought_id(participant_id, record)
            existing = connection.execute(
                """
                SELECT thought_id, record_sha256
                FROM thoughts
                WHERE participant_id=? AND source_type=?
                  AND source_id=? AND source_version=?
                """,
                (
                    participant_id,
                    record.source_type,
                    record.source_id,
                    record.source_version,
                ),
            ).fetchone()
            if existing is not None:
                if existing["record_sha256"] != record.record_sha256:
                    raise ValueError(
                        "immutable source version changed: "
                        f"{record.source_type}/{record.source_id}/"
                        f"{record.source_version}"
                    )
                reused += 1
                decisions.append((record, existing["thought_id"], False))
            else:
                inserted += 1
                decisions.append((record, thought_id, True))

        connection.execute(
            """
            INSERT INTO import_runs(
                import_id, participant_id, consent_id,
                source_artifact_sha256, source_artifact_bytes,
                imported_at, inserted_count, reused_count
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                import_id,
                participant_id,
                receipt.consent_id,
                source_hash,
                source_bytes,
                imported_at,
                inserted,
                reused,
            ),
        )
        for record_index, (record, thought_id, should_insert) in enumerate(
            decisions, start=1
        ):
            if not should_insert:
                continue
            redaction = redact_text(record.text)
            provenance = {
                "source_artifact_sha256": source_hash,
                "source_record_number": record_index,
                "declared": record.provenance,
            }
            connection.execute(
                """
                INSERT INTO thoughts(
                    thought_id, participant_id, consent_id, import_id,
                    source_type, source_id, source_version, captured_at,
                    raw_text, redacted_text, content_sha256, record_sha256,
                    contexts_json, provenance_json, redaction_json, imported_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    thought_id,
                    participant_id,
                    receipt.consent_id,
                    import_id,
                    record.source_type,
                    record.source_id,
                    record.source_version,
                    timestamp(record.captured_at),
                    record.text if receipt.store_raw_content else None,
                    redaction.text,
                    hashlib.sha256(record.text.encode("utf-8")).hexdigest(),
                    record.record_sha256,
                    json.dumps(list(record.contexts)),
                    json.dumps(provenance, sort_keys=True),
                    json.dumps(
                        {
                            "ruleset_version": redaction.ruleset_version,
                            "findings": [
                                finding.to_dict()
                                for finding in redaction.findings
                            ],
                        },
                        sort_keys=True,
                    ),
                    imported_at,
                ),
            )
            for target_source_id in record.explicit_links:
                link_id = (
                    "link_"
                    + hashlib.sha256(
                        f"{thought_id}\0{target_source_id}".encode("utf-8")
                    ).hexdigest()[:24]
                )
                connection.execute(
                    """
                    INSERT INTO explicit_links(
                        link_id, participant_id, source_thought_id,
                        target_source_id, target_thought_id,
                        resolution_status, observed_at, provenance_json
                    ) VALUES(?, ?, ?, ?, NULL, 'unresolved', ?, ?)
                    """,
                    (
                        link_id,
                        participant_id,
                        thought_id,
                        target_source_id,
                        timestamp(record.captured_at),
                        json.dumps(provenance, sort_keys=True),
                    ),
                )
        resolved, unresolved, not_prior = _resolve_explicit_links(
            connection, participant_id
        )
        workspace._audit(
            connection,
            participant_id,
            "private_import_completed",
            {
                "import_id": import_id,
                "source_artifact_sha256": source_hash,
                "source_artifact_bytes": source_bytes,
                "inserted_count": inserted,
                "reused_count": reused,
                "resolved_explicit_links": resolved,
                "unresolved_explicit_links": unresolved,
                "not_prior_explicit_links": not_prior,
            },
        )
    return {
        "import_id": import_id,
        "source_artifact_sha256": source_hash,
        "source_artifact_bytes": source_bytes,
        "inserted_count": inserted,
        "reused_count": reused,
        "resolved_explicit_links": resolved,
        "unresolved_explicit_links": unresolved,
        "not_prior_explicit_links": not_prior,
        "raw_content_stored": receipt.store_raw_content,
        "paid_api_requests": 0,
        "estimated_cost_usd": 0,
    }
