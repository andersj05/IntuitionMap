from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

from intuition_map_private.policy import (
    ConsentReceipt,
    timestamp,
    utc_now,
)

WORKSPACE_SCHEMA_VERSION = "0.1.0"
MARKER_NAME = ".intuitionmap-private.json"
DATABASE_NAME = "intuition-map-private.sqlite3"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS participants (
    participant_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS consents (
    consent_id TEXT PRIMARY KEY,
    participant_id TEXT NOT NULL REFERENCES participants(participant_id)
        ON DELETE CASCADE,
    granted_at TEXT NOT NULL,
    receipt_json TEXT NOT NULL,
    receipt_sha256 TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS consent_revocations (
    consent_id TEXT PRIMARY KEY REFERENCES consents(consent_id)
        ON DELETE CASCADE,
    revoked_at TEXT NOT NULL,
    reason TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS import_runs (
    import_id TEXT PRIMARY KEY,
    participant_id TEXT NOT NULL REFERENCES participants(participant_id)
        ON DELETE CASCADE,
    consent_id TEXT NOT NULL REFERENCES consents(consent_id),
    source_artifact_sha256 TEXT NOT NULL,
    source_artifact_bytes INTEGER NOT NULL CHECK(source_artifact_bytes >= 0),
    imported_at TEXT NOT NULL,
    inserted_count INTEGER NOT NULL CHECK(inserted_count >= 0),
    reused_count INTEGER NOT NULL CHECK(reused_count >= 0)
);

CREATE TABLE IF NOT EXISTS thoughts (
    thought_id TEXT PRIMARY KEY,
    participant_id TEXT NOT NULL REFERENCES participants(participant_id)
        ON DELETE CASCADE,
    consent_id TEXT NOT NULL REFERENCES consents(consent_id),
    import_id TEXT NOT NULL REFERENCES import_runs(import_id)
        ON DELETE CASCADE,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_version TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    raw_text TEXT,
    redacted_text TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    record_sha256 TEXT NOT NULL,
    contexts_json TEXT NOT NULL,
    provenance_json TEXT NOT NULL,
    redaction_json TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    UNIQUE(participant_id, source_type, source_id, source_version)
);

CREATE INDEX IF NOT EXISTS thoughts_participant_time
    ON thoughts(participant_id, captured_at, thought_id);

CREATE TABLE IF NOT EXISTS explicit_links (
    link_id TEXT PRIMARY KEY,
    participant_id TEXT NOT NULL REFERENCES participants(participant_id)
        ON DELETE CASCADE,
    source_thought_id TEXT NOT NULL REFERENCES thoughts(thought_id)
        ON DELETE CASCADE,
    target_source_id TEXT NOT NULL,
    target_thought_id TEXT REFERENCES thoughts(thought_id)
        ON DELETE SET NULL,
    resolution_status TEXT NOT NULL CHECK(
        resolution_status IN ('resolved', 'unresolved', 'not_prior')
    ),
    observed_at TEXT NOT NULL,
    provenance_json TEXT NOT NULL,
    UNIQUE(source_thought_id, target_source_id)
);

CREATE TABLE IF NOT EXISTS weak_labels (
    weak_label_id TEXT PRIMARY KEY,
    participant_id TEXT NOT NULL REFERENCES participants(participant_id)
        ON DELETE CASCADE,
    source_thought_id TEXT NOT NULL REFERENCES thoughts(thought_id)
        ON DELETE CASCADE,
    target_thought_id TEXT NOT NULL REFERENCES thoughts(thought_id)
        ON DELETE CASCADE,
    signal_source TEXT NOT NULL,
    confidence REAL NOT NULL CHECK(confidence >= 0 AND confidence <= 1),
    observed_at TEXT NOT NULL,
    provenance_json TEXT NOT NULL,
    UNIQUE(source_thought_id, target_thought_id, signal_source)
);

CREATE TABLE IF NOT EXISTS protected_manifests (
    manifest_id TEXT PRIMARY KEY,
    participant_id TEXT NOT NULL UNIQUE
        REFERENCES participants(participant_id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    boundary_at TEXT NOT NULL,
    query_ids_json TEXT NOT NULL,
    definition_json TEXT NOT NULL,
    definition_sha256 TEXT NOT NULL UNIQUE,
    sealed INTEGER NOT NULL CHECK(sealed = 1)
);

CREATE TABLE IF NOT EXISTS annotation_items (
    item_id TEXT PRIMARY KEY,
    participant_id TEXT NOT NULL REFERENCES participants(participant_id)
        ON DELETE CASCADE,
    source_thought_id TEXT NOT NULL REFERENCES thoughts(thought_id)
        ON DELETE CASCADE,
    target_thought_id TEXT REFERENCES thoughts(thought_id)
        ON DELETE CASCADE,
    stream TEXT NOT NULL CHECK(stream IN ('discovery', 'proposal')),
    sampling_source TEXT NOT NULL,
    selection_probability REAL CHECK(
        selection_probability IS NULL OR
        (selection_probability > 0 AND selection_probability <= 1)
    ),
    exposure_status TEXT NOT NULL CHECK(
        exposure_status IN ('not_exported', 'prompt_shown', 'candidate_shown')
    ),
    repeat_of_item_id TEXT REFERENCES annotation_items(item_id)
        ON DELETE CASCADE,
    sequence_number INTEGER NOT NULL CHECK(sequence_number >= 0),
    split_role TEXT NOT NULL CHECK(
        split_role IN ('train', 'protected_test')
    ),
    created_at TEXT NOT NULL,
    exported_at TEXT,
    UNIQUE(
        participant_id,
        source_thought_id,
        target_thought_id,
        sampling_source,
        repeat_of_item_id
    )
);

CREATE TABLE IF NOT EXISTS annotation_responses (
    response_id TEXT PRIMARY KEY,
    participant_id TEXT NOT NULL REFERENCES participants(participant_id)
        ON DELETE CASCADE,
    item_id TEXT NOT NULL UNIQUE REFERENCES annotation_items(item_id)
        ON DELETE CASCADE,
    verdict TEXT CHECK(
        verdict IS NULL OR
        verdict IN ('essential', 'valid', 'invalid', 'uncertain')
    ),
    relation_types_json TEXT NOT NULL,
    rationale TEXT,
    response_ms INTEGER NOT NULL CHECK(response_ms >= 0),
    skipped INTEGER NOT NULL CHECK(skipped IN (0, 1)),
    discovered_target_ids_json TEXT NOT NULL,
    submitted_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS gold_judgments (
    judgment_id TEXT PRIMARY KEY,
    participant_id TEXT NOT NULL REFERENCES participants(participant_id)
        ON DELETE CASCADE,
    response_id TEXT NOT NULL REFERENCES annotation_responses(response_id)
        ON DELETE CASCADE,
    source_thought_id TEXT NOT NULL REFERENCES thoughts(thought_id)
        ON DELETE CASCADE,
    target_thought_id TEXT NOT NULL REFERENCES thoughts(thought_id)
        ON DELETE CASCADE,
    verdict TEXT NOT NULL CHECK(
        verdict IN ('essential', 'valid', 'invalid', 'uncertain')
    ),
    relation_types_json TEXT NOT NULL,
    rationale TEXT,
    stream TEXT NOT NULL CHECK(stream IN ('discovery', 'proposal')),
    sampling_source TEXT NOT NULL,
    exposure_status TEXT NOT NULL,
    response_ms INTEGER NOT NULL CHECK(response_ms >= 0),
    split_role TEXT NOT NULL CHECK(
        split_role IN ('train', 'protected_test')
    ),
    created_at TEXT NOT NULL,
    UNIQUE(response_id, target_thought_id)
);

CREATE TABLE IF NOT EXISTS exports (
    export_id TEXT PRIMARY KEY,
    participant_id TEXT NOT NULL REFERENCES participants(participant_id)
        ON DELETE CASCADE,
    purpose TEXT NOT NULL CHECK(
        purpose IN (
            'user_portability',
            'training',
            'annotation_batch',
            'annotation_response'
        )
    ),
    path TEXT NOT NULL UNIQUE,
    includes_raw INTEGER NOT NULL CHECK(includes_raw IN (0, 1)),
    created_at TEXT NOT NULL,
    sha256 TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_events (
    event_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    event_type TEXT NOT NULL,
    participant_sha256 TEXT NOT NULL,
    details_json TEXT NOT NULL
);
"""


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


class PrivateWorkspace:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.marker_path = self.root / MARKER_NAME
        self.database_path = self.root / DATABASE_NAME

    @classmethod
    def initialize(cls, root: str | Path) -> PrivateWorkspace:
        workspace = cls(root)
        workspace._validate_storage_location()
        workspace.root.mkdir(parents=True, exist_ok=True)
        if workspace.marker_path.exists() or workspace.database_path.exists():
            raise ValueError(
                f"private workspace already exists: {workspace.root}"
            )
        marker = {
            "schema_version": WORKSPACE_SCHEMA_VERSION,
            "purpose": "IntuitionMap local private research data",
            "database": DATABASE_NAME,
            "created_at": timestamp(utc_now()),
            "warnings": [
                "This workspace is local-only but not application-level encrypted.",
                "Use operating-system account and full-disk encryption.",
                "Backups and original source files are outside app deletion scope.",
            ],
        }
        workspace.marker_path.write_text(
            json.dumps(marker, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.chmod(workspace.marker_path, 0o600)
        with workspace.connect() as connection:
            connection.executescript(_SCHEMA)
            connection.execute(
                "INSERT INTO metadata(key, value) VALUES(?, ?)",
                ("schema_version", WORKSPACE_SCHEMA_VERSION),
            )
        os.chmod(workspace.database_path, 0o600)
        return workspace

    def _validate_storage_location(self) -> None:
        for candidate in (self.root, *self.root.parents):
            if (candidate / ".git").exists():
                allowed = (candidate / "datasets" / "private").resolve()
                if self.root != allowed and allowed not in self.root.parents:
                    raise ValueError(
                        "a private workspace inside Git must be under "
                        f"the ignored path {allowed}"
                    )
                return

    def validate(self) -> None:
        if not self.marker_path.is_file() or not self.database_path.is_file():
            raise ValueError(
                f"not an initialized private workspace: {self.root}"
            )
        try:
            marker = json.loads(
                self.marker_path.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError as exc:
            raise ValueError("invalid private-workspace marker") from exc
        if marker.get("schema_version") != WORKSPACE_SCHEMA_VERSION:
            raise ValueError("unsupported private-workspace schema version")
        with self.connect() as connection:
            row = connection.execute(
                "SELECT value FROM metadata WHERE key='schema_version'"
            ).fetchone()
        if row is None or row["value"] != WORKSPACE_SCHEMA_VERSION:
            raise ValueError("private database schema marker is invalid")

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA secure_delete = ON")
        connection.execute("PRAGMA journal_mode = DELETE")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def managed_path(self, path: str | Path) -> Path:
        resolved = Path(path)
        if not resolved.is_absolute():
            resolved = self.root / resolved
        resolved = resolved.resolve()
        if resolved == self.root or self.root not in resolved.parents:
            raise ValueError(
                "private output path must remain inside the private workspace"
            )
        if resolved in {self.marker_path, self.database_path}:
            raise ValueError("private output cannot overwrite workspace files")
        return resolved

    def add_consent(self, receipt: ConsentReceipt) -> dict[str, Any]:
        receipt.validate()
        receipt_json = _canonical_json(receipt.to_dict())
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT receipt_sha256 FROM consents WHERE consent_id=?",
                (receipt.consent_id,),
            ).fetchone()
            if existing is not None:
                if existing["receipt_sha256"] != receipt.sha256:
                    raise ValueError(
                        "consent_id already exists with different content"
                    )
                return {
                    "consent_id": receipt.consent_id,
                    "receipt_sha256": receipt.sha256,
                    "status": "verified-existing",
                }
            connection.execute(
                """
                INSERT OR IGNORE INTO participants(participant_id, created_at)
                VALUES(?, ?)
                """,
                (receipt.participant_id, timestamp(utc_now())),
            )
            connection.execute(
                """
                INSERT INTO consents(
                    consent_id, participant_id, granted_at,
                    receipt_json, receipt_sha256
                ) VALUES(?, ?, ?, ?, ?)
                """,
                (
                    receipt.consent_id,
                    receipt.participant_id,
                    timestamp(receipt.granted_at),
                    receipt_json,
                    receipt.sha256,
                ),
            )
            self._audit(
                connection,
                receipt.participant_id,
                "consent_granted",
                {
                    "consent_id": receipt.consent_id,
                    "receipt_sha256": receipt.sha256,
                },
            )
        return {
            "consent_id": receipt.consent_id,
            "receipt_sha256": receipt.sha256,
            "status": "created",
        }

    def active_consent(
        self,
        participant_id: str,
        *,
        purpose: str,
        source_type: str | None = None,
    ) -> ConsentReceipt:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT c.receipt_json
                FROM consents c
                LEFT JOIN consent_revocations r
                    ON r.consent_id = c.consent_id
                WHERE c.participant_id=? AND r.consent_id IS NULL
                ORDER BY c.granted_at DESC, c.consent_id DESC
                """,
                (participant_id,),
            ).fetchall()
        for row in rows:
            receipt = ConsentReceipt.from_dict(
                json.loads(row["receipt_json"])
            )
            if purpose not in receipt.purposes:
                continue
            if source_type is not None and source_type not in receipt.source_types:
                continue
            if utc_now() >= receipt.granted_at + timedelta(
                days=receipt.retention_days
            ):
                continue
            return receipt
        qualifier = f" and source type {source_type}" if source_type else ""
        raise ValueError(
            f"no active consent for purpose {purpose}{qualifier}"
        )

    def revoke_consent(
        self,
        consent_id: str,
        *,
        reason: str,
        revoked_at: datetime | None = None,
    ) -> dict[str, Any]:
        if not reason.strip():
            raise ValueError("revocation reason must be non-empty")
        with self.connect() as connection:
            row = connection.execute(
                "SELECT participant_id FROM consents WHERE consent_id=?",
                (consent_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"unknown consent_id: {consent_id}")
            try:
                connection.execute(
                    """
                    INSERT INTO consent_revocations(
                        consent_id, revoked_at, reason
                    ) VALUES(?, ?, ?)
                    """,
                    (
                        consent_id,
                        timestamp(revoked_at or utc_now()),
                        reason.strip(),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError("consent is already revoked") from exc
            self._audit(
                connection,
                row["participant_id"],
                "consent_revoked",
                {"consent_id": consent_id},
            )
        return {"consent_id": consent_id, "status": "revoked"}

    def has_protected_manifest(self, participant_id: str) -> bool:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT 1 FROM protected_manifests
                WHERE participant_id=? AND sealed=1
                """,
                (participant_id,),
            ).fetchone()
        return row is not None

    def split_role(
        self, connection: sqlite3.Connection, participant_id: str, thought_id: str
    ) -> str:
        row = connection.execute(
            """
            SELECT query_ids_json FROM protected_manifests
            WHERE participant_id=? AND sealed=1
            """,
            (participant_id,),
        ).fetchone()
        if row is None:
            raise ValueError(
                "freeze a protected chronological manifest before queuing labels"
            )
        return (
            "protected_test"
            if thought_id in set(json.loads(row["query_ids_json"]))
            else "train"
        )

    def register_export(
        self,
        *,
        participant_id: str,
        purpose: str,
        path: Path,
        includes_raw: bool,
        sha256: str,
    ) -> str:
        export_id = f"export_{uuid.uuid4().hex}"
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO exports(
                    export_id, participant_id, purpose, path,
                    includes_raw, created_at, sha256
                ) VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    export_id,
                    participant_id,
                    purpose,
                    str(path),
                    int(includes_raw),
                    timestamp(utc_now()),
                    sha256,
                ),
            )
            self._audit(
                connection,
                participant_id,
                "private_export_created",
                {
                    "export_id": export_id,
                    "purpose": purpose,
                    "includes_raw": includes_raw,
                    "sha256": sha256,
                },
            )
        return export_id

    def delete_participant(self, participant_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM participants WHERE participant_id=?",
                (participant_id,),
            ).fetchone()
            if exists is None:
                raise ValueError(f"unknown participant: {participant_id}")
            export_rows = connection.execute(
                "SELECT path FROM exports WHERE participant_id=?",
                (participant_id,),
            ).fetchall()
            table_counts = {
                table: connection.execute(
                    f"SELECT COUNT(*) AS count FROM {table} "
                    "WHERE participant_id=?",
                    (participant_id,),
                ).fetchone()["count"]
                for table in (
                    "consents",
                    "import_runs",
                    "thoughts",
                    "explicit_links",
                    "weak_labels",
                    "protected_manifests",
                    "annotation_items",
                    "annotation_responses",
                    "gold_judgments",
                    "exports",
                )
            }
            self._audit(
                connection,
                participant_id,
                "participant_deletion_started",
                {"row_counts": table_counts},
            )
            connection.execute(
                "DELETE FROM participants WHERE participant_id=?",
                (participant_id,),
            )

        removed_exports: list[str] = []
        for row in export_rows:
            path = self.managed_path(row["path"])
            if path.is_file():
                path.unlink()
                removed_exports.append(str(path))
        with self.connect() as connection:
            connection.execute("VACUUM")
            self._audit(
                connection,
                participant_id,
                "participant_deletion_completed",
                {
                    "deleted_row_counts": table_counts,
                    "removed_export_file_count": len(removed_exports),
                    "original_sources_and_backups_deleted": False,
                },
            )
        return {
            "participant_sha256": hashlib.sha256(
                participant_id.encode("utf-8")
            ).hexdigest(),
            "deleted_row_counts": table_counts,
            "removed_export_files": sorted(removed_exports),
            "original_sources_and_backups_deleted": False,
            "status": "deleted",
        }

    def _audit(
        self,
        connection: sqlite3.Connection,
        participant_id: str,
        event_type: str,
        details: dict[str, Any],
    ) -> None:
        serialized = _canonical_json(details)
        forbidden = {"raw_text", "redacted_text", "rationale", "content"}
        if forbidden & set(details):
            raise ValueError("audit events must not contain private content")
        connection.execute(
            """
            INSERT INTO audit_events(
                event_id, created_at, event_type,
                participant_sha256, details_json
            ) VALUES(?, ?, ?, ?, ?)
            """,
            (
                f"audit_{uuid.uuid4().hex}",
                timestamp(utc_now()),
                event_type,
                hashlib.sha256(participant_id.encode("utf-8")).hexdigest(),
                serialized,
            ),
        )
