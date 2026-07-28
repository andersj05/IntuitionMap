from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from intuition_map_private.policy import ConsentReceipt, timestamp, utc_now
from intuition_map_private.redaction import redact_text
from intuition_map_private.store import PrivateWorkspace


def _rows(
    connection: sqlite3.Connection,
    query: str,
    parameters: tuple[Any, ...],
) -> list[dict[str, Any]]:
    return [dict(row) for row in connection.execute(query, parameters)]


def _decode_fields(row: dict[str, Any], fields: tuple[str, ...]) -> None:
    for field in fields:
        row[field.removesuffix("_json")] = json.loads(row.pop(field))


def export_participant_bundle(
    workspace: PrivateWorkspace,
    *,
    participant_id: str,
    output_path: str | Path,
    purpose: str = "user_portability",
    include_raw: bool = False,
) -> dict[str, Any]:
    workspace.validate()
    if purpose not in {"user_portability", "training"}:
        raise ValueError("purpose must be user_portability or training")
    if purpose == "training" and include_raw:
        raise ValueError("training exports cannot contain raw source text")
    if purpose == "training":
        receipt: ConsentReceipt = workspace.active_consent(
            participant_id,
            purpose="local_retrieval_research",
        )
        if not receipt.allow_training_use:
            raise ValueError("active consent does not allow training use")
    output = workspace.managed_path(output_path)
    if output.exists():
        raise ValueError(f"private export already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)

    with workspace.connect() as connection:
        participant = connection.execute(
            "SELECT created_at FROM participants WHERE participant_id=?",
            (participant_id,),
        ).fetchone()
        if participant is None:
            raise ValueError(f"unknown participant: {participant_id}")
        tracked = connection.execute(
            "SELECT 1 FROM exports WHERE path=?",
            (str(output),),
        ).fetchone()
        if tracked is not None:
            raise ValueError("private export path is already registered")
        manifest_row = connection.execute(
            """
            SELECT definition_sha256, query_ids_json
            FROM protected_manifests
            WHERE participant_id=?
            """,
            (participant_id,),
        ).fetchone()
        protected_ids = (
            set(json.loads(manifest_row["query_ids_json"]))
            if manifest_row is not None
            else set()
        )
        thought_rows = _rows(
            connection,
            """
            SELECT
                thought_id, source_type, source_id, source_version,
                captured_at, raw_text, redacted_text, content_sha256,
                record_sha256, contexts_json, provenance_json,
                redaction_json, imported_at
            FROM thoughts
            WHERE participant_id=?
            ORDER BY captured_at, thought_id
            """,
            (participant_id,),
        )
        if purpose == "training":
            thought_rows = [
                row
                for row in thought_rows
                if row["thought_id"] not in protected_ids
            ]
        thoughts: list[dict[str, Any]] = []
        for row in thought_rows:
            if include_raw and row["raw_text"] is None:
                raise ValueError(
                    "raw export requested but import did not store exact raw text"
                )
            text = (
                row.pop("raw_text")
                if include_raw
                else row.pop("redacted_text")
            )
            if include_raw:
                row.pop("redacted_text")
            else:
                row.pop("raw_text", None)
            row["text"] = text
            row["text_view"] = "raw" if include_raw else "derived-redacted"
            _decode_fields(
                row,
                ("contexts_json", "provenance_json", "redaction_json"),
            )
            if not include_raw:
                row["provenance"] = {
                    key: value
                    for key, value in row["provenance"].items()
                    if key
                    in {"source_artifact_sha256", "source_record_number"}
                }
            if purpose == "training":
                row.pop("provenance", None)
                row["source_id"] = hashlib.sha256(
                    row["source_id"].encode("utf-8")
                ).hexdigest()
            thoughts.append(row)
        included_thought_ids = {row["thought_id"] for row in thoughts}

        weak_labels = _rows(
            connection,
            """
            SELECT
                weak_label_id, source_thought_id, target_thought_id,
                signal_source, confidence, observed_at, provenance_json
            FROM weak_labels
            WHERE participant_id=?
            ORDER BY observed_at, weak_label_id
            """,
            (participant_id,),
        )
        weak_labels = [
            row
            for row in weak_labels
            if row["source_thought_id"] in included_thought_ids
            and row["target_thought_id"] in included_thought_ids
        ]
        for row in weak_labels:
            _decode_fields(row, ("provenance_json",))
            if not include_raw:
                row["provenance"] = {
                    key: value
                    for key, value in row["provenance"].items()
                    if key
                    in {"source_artifact_sha256", "source_record_number"}
                }
            if purpose == "training":
                row.pop("provenance", None)

        judgments = _rows(
            connection,
            """
            SELECT
                judgment_id, source_thought_id, target_thought_id,
                verdict, relation_types_json, rationale, stream,
                sampling_source, exposure_status, response_ms,
                split_role, created_at
            FROM gold_judgments
            WHERE participant_id=?
            ORDER BY created_at, judgment_id
            """,
            (participant_id,),
        )
        if purpose == "training":
            judgments = [
                row for row in judgments if row["split_role"] == "train"
            ]
        judgments = [
            row
            for row in judgments
            if row["source_thought_id"] in included_thought_ids
            and row["target_thought_id"] in included_thought_ids
        ]
        for row in judgments:
            _decode_fields(row, ("relation_types_json",))
            if not include_raw and row["rationale"] is not None:
                row["rationale"] = redact_text(row["rationale"]).text

        explicit_links = _rows(
            connection,
            """
            SELECT
                link_id, source_thought_id, target_source_id,
                target_thought_id, resolution_status, observed_at
            FROM explicit_links
            WHERE participant_id=?
            ORDER BY observed_at, link_id
            """,
            (participant_id,),
        )
        explicit_links = [
            row
            for row in explicit_links
            if row["source_thought_id"] in included_thought_ids
            and (
                row["target_thought_id"] is None
                or row["target_thought_id"] in included_thought_ids
            )
        ]
        consent_rows: list[dict[str, Any]] = []
        if purpose == "user_portability":
            consent_rows = _rows(
                connection,
                """
                SELECT
                    c.receipt_json,
                    r.revoked_at,
                    r.reason AS revocation_reason
                FROM consents c
                LEFT JOIN consent_revocations r
                    ON r.consent_id=c.consent_id
                WHERE c.participant_id=?
                ORDER BY c.granted_at, c.consent_id
                """,
                (participant_id,),
            )
            for row in consent_rows:
                row["receipt"] = json.loads(row.pop("receipt_json"))

    created_at = timestamp(utc_now())
    payload = {
        "schema_version": "0.1.0",
        "purpose": purpose,
        "participant_id": participant_id,
        "created_at": created_at,
        "privacy": {
            "contains_private_data": True,
            "local_only": True,
            "text_view": "raw" if include_raw else "derived-redacted",
            "protected_test_excluded": purpose == "training",
        },
        "protected_manifest_sha256": (
            manifest_row["definition_sha256"]
            if manifest_row is not None
            else None
        ),
        "thoughts": thoughts,
        "explicit_links": explicit_links,
        "weak_labels": weak_labels,
        "gold_judgments": judgments,
        "consents": consent_rows,
        "counts": {
            "thoughts": len(thoughts),
            "explicit_links": len(explicit_links),
            "weak_labels": len(weak_labels),
            "gold_judgments": len(judgments),
            "consents": len(consent_rows),
        },
    }
    temporary = output.with_name(f"{output.name}.tmp-{uuid.uuid4().hex}")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, output)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    export_id = workspace.register_export(
        participant_id=participant_id,
        purpose=purpose,
        path=output,
        includes_raw=include_raw,
        sha256=digest,
    )
    return {
        "export_id": export_id,
        "path": str(output),
        "sha256": digest,
        "purpose": purpose,
        "includes_raw": include_raw,
        "counts": payload["counts"],
    }
