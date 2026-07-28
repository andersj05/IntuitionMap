from __future__ import annotations

import hashlib
import json
import math
import uuid
from typing import Any

from intuition_map_private.policy import timestamp, utc_now
from intuition_map_private.store import PrivateWorkspace


def freeze_chronological_test_manifest(
    workspace: PrivateWorkspace,
    *,
    participant_id: str,
    test_fraction: float = 0.20,
    minimum_test_queries: int = 2,
) -> dict[str, Any]:
    workspace.validate()
    receipt = workspace.active_consent(
        participant_id,
        purpose="annotation_pilot",
    )
    if not receipt.allow_derived_features:
        raise ValueError(
            "active consent does not allow derived annotation features"
        )
    if not 0 < test_fraction < 1:
        raise ValueError("test_fraction must be between 0 and 1")
    if (
        isinstance(minimum_test_queries, bool)
        or not isinstance(minimum_test_queries, int)
        or minimum_test_queries <= 0
    ):
        raise ValueError("minimum_test_queries must be a positive integer")
    with workspace.connect() as connection:
        existing = connection.execute(
            """
            SELECT definition_json FROM protected_manifests
            WHERE participant_id=?
            """,
            (participant_id,),
        ).fetchone()
        if existing is not None:
            raise ValueError(
                "a sealed protected manifest already exists for this participant"
            )
        thoughts = connection.execute(
            """
            SELECT thought_id, captured_at, content_sha256
            FROM thoughts
            WHERE participant_id=?
            ORDER BY captured_at, thought_id
            """,
            (participant_id,),
        ).fetchall()
        eligible = thoughts[1:]
        if len(eligible) < minimum_test_queries + 1:
            raise ValueError(
                "not enough chronological queries to preserve both train and test"
            )
        test_count = max(
            minimum_test_queries,
            math.ceil(len(eligible) * test_fraction),
        )
        if test_count >= len(eligible):
            raise ValueError(
                "protected test selection would leave no training queries"
            )
        test_rows = eligible[-test_count:]
        query_ids = [row["thought_id"] for row in test_rows]
        definition = {
            "schema_version": "0.1.0",
            "participant_id": participant_id,
            "policy": "last chronological query block",
            "test_fraction_requested": test_fraction,
            "minimum_test_queries": minimum_test_queries,
            "corpus_thought_count": len(thoughts),
            "eligible_query_count": len(eligible),
            "protected_test_query_count": len(test_rows),
            "boundary_at": test_rows[0]["captured_at"],
            "protected_queries": [
                {
                    "thought_id": row["thought_id"],
                    "captured_at": row["captured_at"],
                    "content_sha256": row["content_sha256"],
                }
                for row in test_rows
            ],
        }
        canonical = json.dumps(
            definition, sort_keys=True, separators=(",", ":")
        )
        definition_sha256 = hashlib.sha256(
            canonical.encode("utf-8")
        ).hexdigest()
        manifest_id = f"split_{uuid.uuid4().hex}"
        created_at = timestamp(utc_now())
        connection.execute(
            """
            INSERT INTO protected_manifests(
                manifest_id, participant_id, created_at, boundary_at,
                query_ids_json, definition_json, definition_sha256, sealed
            ) VALUES(?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                manifest_id,
                participant_id,
                created_at,
                definition["boundary_at"],
                json.dumps(query_ids),
                canonical,
                definition_sha256,
            ),
        )
        workspace._audit(
            connection,
            participant_id,
            "protected_test_manifest_frozen",
            {
                "manifest_id": manifest_id,
                "definition_sha256": definition_sha256,
                "protected_test_query_count": len(test_rows),
                "eligible_query_count": len(eligible),
            },
        )
    return {
        "manifest_id": manifest_id,
        "created_at": created_at,
        "definition_sha256": definition_sha256,
        "boundary_at": definition["boundary_at"],
        "eligible_query_count": len(eligible),
        "protected_test_query_count": len(test_rows),
        "sealed": True,
    }
