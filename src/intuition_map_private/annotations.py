from __future__ import annotations

import hashlib
import json
import math
import os
import random
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from intuition_map_eval.schema import Verdict, parse_timestamp
from intuition_map_models.retrieval import (
    BM25Ranker,
    HashedEmbeddingRanker,
    RetrievalCandidate,
    RetrievalQuery,
    TfIdfRanker,
)
from intuition_map_private.policy import timestamp, utc_now
from intuition_map_private.store import PrivateWorkspace

ANNOTATION_SCHEMA_VERSION = "0.1.0"


def _require_annotation_consent(
    workspace: PrivateWorkspace, participant_id: str
) -> None:
    receipt = workspace.active_consent(
        participant_id,
        purpose="annotation_pilot",
    )
    if not receipt.allow_derived_features:
        raise ValueError(
            "active consent does not allow derived retrieval features"
        )


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _new_item_id() -> str:
    return f"item_{uuid.uuid4().hex}"


def _eligible_sources(
    connection: sqlite3.Connection,
    participant_id: str,
    source_thought_ids: list[str] | None,
) -> list[sqlite3.Row]:
    thoughts = connection.execute(
        """
        SELECT thought_id, captured_at
        FROM thoughts
        WHERE participant_id=?
        ORDER BY captured_at, thought_id
        """,
        (participant_id,),
    ).fetchall()
    eligible = thoughts[1:]
    if source_thought_ids is None:
        return eligible
    requested = set(source_thought_ids)
    known = {row["thought_id"] for row in eligible}
    unknown = requested - known
    if unknown:
        raise ValueError(
            f"unknown or candidate-less source thoughts: {sorted(unknown)}"
        )
    return [row for row in eligible if row["thought_id"] in requested]


def create_discovery_queue(
    workspace: PrivateWorkspace,
    *,
    participant_id: str,
    source_thought_ids: list[str] | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    workspace.validate()
    _require_annotation_consent(workspace, participant_id)
    if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
        raise ValueError("limit must be a positive integer")
    created_ids: list[str] = []
    with workspace.connect() as connection:
        sources = _eligible_sources(
            connection, participant_id, source_thought_ids
        )
        for source in sources:
            if len(created_ids) >= limit:
                break
            split_role = workspace.split_role(
                connection, participant_id, source["thought_id"]
            )
            exists = connection.execute(
                """
                SELECT 1 FROM annotation_items
                WHERE participant_id=? AND source_thought_id=?
                  AND stream='discovery'
                """,
                (participant_id, source["thought_id"]),
            ).fetchone()
            if exists is not None:
                continue
            item_id = _new_item_id()
            connection.execute(
                """
                INSERT INTO annotation_items(
                    item_id, participant_id, source_thought_id,
                    target_thought_id, stream, sampling_source,
                    selection_probability, exposure_status,
                    repeat_of_item_id, sequence_number, split_role, created_at
                ) VALUES(
                    ?, ?, ?, NULL, 'discovery', 'user_recall',
                    NULL, 'not_exported', NULL, 0, ?, ?
                )
                """,
                (
                    item_id,
                    participant_id,
                    source["thought_id"],
                    split_role,
                    timestamp(utc_now()),
                ),
            )
            created_ids.append(item_id)
        workspace._audit(
            connection,
            participant_id,
            "discovery_queue_created",
            {"created_count": len(created_ids)},
        )
    return {
        "created_count": len(created_ids),
        "item_ids": created_ids,
        "candidate_content_exposed": False,
    }


def _retrieval_query(
    connection: sqlite3.Connection,
    participant_id: str,
    source_thought_id: str,
) -> tuple[RetrievalQuery, dict[str, sqlite3.Row]]:
    source = connection.execute(
        """
        SELECT thought_id, redacted_text, captured_at, contexts_json
        FROM thoughts
        WHERE participant_id=? AND thought_id=?
        """,
        (participant_id, source_thought_id),
    ).fetchone()
    if source is None:
        raise ValueError(f"unknown source thought: {source_thought_id}")
    prior = connection.execute(
        """
        SELECT thought_id, redacted_text, captured_at, contexts_json
        FROM thoughts
        WHERE participant_id=? AND captured_at < ?
        ORDER BY captured_at, thought_id
        """,
        (participant_id, source["captured_at"]),
    ).fetchall()
    explicit_rows = connection.execute(
        """
        SELECT target_thought_id
        FROM explicit_links
        WHERE source_thought_id=? AND resolution_status='resolved'
        ORDER BY target_thought_id
        """,
        (source_thought_id,),
    ).fetchall()
    rows_by_id = {row["thought_id"]: row for row in prior}
    query = RetrievalQuery(
        query_id=source_thought_id,
        text=source["redacted_text"],
        contexts=tuple(json.loads(source["contexts_json"])),
        explicit_target_ids=tuple(
            row["target_thought_id"] for row in explicit_rows
        ),
        candidates=tuple(
            RetrievalCandidate(
                candidate_id=row["thought_id"],
                text=row["redacted_text"],
                order=index,
                timestamp=parse_timestamp(row["captured_at"]),
                contexts=tuple(json.loads(row["contexts_json"])),
            )
            for index, row in enumerate(prior)
        ),
    )
    return query, rows_by_id


def _rank_map(ranking: tuple[Any, ...]) -> dict[str, int]:
    return {item.candidate_id: item.rank for item in ranking}


def _stable_random(
    participant_id: str,
    source_thought_id: str,
    seed: int,
) -> random.Random:
    digest = hashlib.sha256(
        f"{seed}\0{participant_id}\0{source_thought_id}".encode("utf-8")
    ).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def create_standard_proposal_queue(
    workspace: PrivateWorkspace,
    *,
    participant_id: str,
    source_thought_id: str,
    seed: int = 1729,
    max_proposals: int = 5,
    random_min_age_days: int = 30,
) -> dict[str, Any]:
    workspace.validate()
    _require_annotation_consent(workspace, participant_id)
    if max_proposals != 5:
        raise ValueError(
            "the preregistered standard queue requires max_proposals=5"
        )
    if (
        isinstance(random_min_age_days, bool)
        or not isinstance(random_min_age_days, int)
        or random_min_age_days < 0
    ):
        raise ValueError("random_min_age_days must be a non-negative integer")

    created: list[dict[str, Any]] = []
    with workspace.connect() as connection:
        discovery = connection.execute(
            """
            SELECT r.response_id
            FROM annotation_items i
            JOIN annotation_responses r ON r.item_id=i.item_id
            WHERE i.participant_id=? AND i.source_thought_id=?
              AND i.stream='discovery'
            """,
            (participant_id, source_thought_id),
        ).fetchone()
        if discovery is None:
            raise ValueError(
                "a completed discovery response is required before proposals"
            )
        existing_proposals = connection.execute(
            """
            SELECT COUNT(*) AS count FROM annotation_items
            WHERE participant_id=? AND source_thought_id=?
              AND stream='proposal' AND repeat_of_item_id IS NULL
            """,
            (participant_id, source_thought_id),
        ).fetchone()["count"]
        if existing_proposals:
            raise ValueError(
                "standard proposals already exist for this source thought"
            )

        query, rows_by_id = _retrieval_query(
            connection, participant_id, source_thought_id
        )
        if not query.candidates:
            return {
                "created_count": 0,
                "item_ids": [],
                "selection_details_exposed": False,
            }
        already_judged = {
            row["target_thought_id"]
            for row in connection.execute(
                """
                SELECT target_thought_id FROM gold_judgments
                WHERE participant_id=? AND source_thought_id=?
                """,
                (participant_id, source_thought_id),
            ).fetchall()
        }
        eligible_ids = {
            candidate.candidate_id for candidate in query.candidates
        } - already_judged
        if not eligible_ids:
            return {
                "created_count": 0,
                "item_ids": [],
                "selection_details_exposed": False,
            }

        tfidf = TfIdfRanker().rank(query)
        bm25 = BM25Ranker(k1=1.2, b=0.75).rank(query)
        diversity = HashedEmbeddingRanker(
            dimensions=512, seed=seed
        ).rank(query)
        selected: list[tuple[str, str, float | None]] = []
        selected_ids: set[str] = set()

        def add(
            target_id: str,
            sampling_source: str,
            probability: float | None = None,
        ) -> None:
            if (
                target_id in eligible_ids
                and target_id not in selected_ids
                and len(selected) < max_proposals
            ):
                selected.append((target_id, sampling_source, probability))
                selected_ids.add(target_id)

        tfidf_eligible = [
            item for item in tfidf if item.candidate_id in eligible_ids
        ]
        for index, item in enumerate(tfidf_eligible[:2], start=1):
            add(item.candidate_id, f"tfidf_top_{index}")

        tfidf_ranks = _rank_map(tfidf)
        bm25_ranks = _rank_map(bm25)
        disagreement_ids = sorted(
            eligible_ids - selected_ids,
            key=lambda candidate_id: (
                -abs(
                    tfidf_ranks[candidate_id] - bm25_ranks[candidate_id]
                ),
                candidate_id,
            ),
        )
        if disagreement_ids:
            add(disagreement_ids[0], "tfidf_bm25_disagreement")

        for item in diversity:
            if item.candidate_id in eligible_ids - selected_ids:
                add(item.candidate_id, "hash_diversity")
                break

        source_time = parse_timestamp(
            connection.execute(
                "SELECT captured_at FROM thoughts WHERE thought_id=?",
                (source_thought_id,),
            ).fetchone()["captured_at"]
        )
        random_pool = [
            candidate_id
            for candidate_id in sorted(eligible_ids - selected_ids)
            if (
                source_time
                - parse_timestamp(rows_by_id[candidate_id]["captured_at"])
            ).days
            >= random_min_age_days
        ]
        sampling_source = f"random_temporal_{random_min_age_days}d_plus"
        if not random_pool:
            random_pool = sorted(eligible_ids - selected_ids)
            sampling_source = "random_temporal_fallback_all_prior"
        if random_pool:
            add(
                _stable_random(
                    participant_id, source_thought_id, seed
                ).choice(random_pool),
                sampling_source,
                1.0 / len(random_pool),
            )

        split_role = workspace.split_role(
            connection, participant_id, source_thought_id
        )
        for sequence, (
            target_id,
            sampling_source,
            probability,
        ) in enumerate(selected, start=1):
            item_id = _new_item_id()
            connection.execute(
                """
                INSERT INTO annotation_items(
                    item_id, participant_id, source_thought_id,
                    target_thought_id, stream, sampling_source,
                    selection_probability, exposure_status,
                    repeat_of_item_id, sequence_number, split_role, created_at
                ) VALUES(
                    ?, ?, ?, ?, 'proposal', ?, ?, 'not_exported',
                    NULL, ?, ?, ?
                )
                """,
                (
                    item_id,
                    participant_id,
                    source_thought_id,
                    target_id,
                    sampling_source,
                    probability,
                    sequence,
                    split_role,
                    timestamp(utc_now()),
                ),
            )
            created.append(
                {
                    "item_id": item_id,
                    "sampling_source": sampling_source,
                    "selection_probability": probability,
                }
            )
        workspace._audit(
            connection,
            participant_id,
            "proposal_queue_created",
            {
                "source_thought_id": source_thought_id,
                "created_count": len(created),
                "sampling_sources": [
                    item["sampling_source"] for item in created
                ],
            },
        )
    return {
        "created_count": len(created),
        "item_ids": [item["item_id"] for item in created],
        "selection_details_exposed": False,
    }


def create_blind_repeats(
    workspace: PrivateWorkspace,
    *,
    participant_id: str,
    rate: float = 0.10,
    minimum_delay_days: int = 7,
    now: datetime | None = None,
) -> dict[str, Any]:
    workspace.validate()
    _require_annotation_consent(workspace, participant_id)
    if not 0 < rate <= 0.10:
        raise ValueError("blind repeat rate must be in (0, 0.10]")
    if minimum_delay_days < 0:
        raise ValueError("minimum_delay_days must be non-negative")
    now = now or utc_now()
    created: list[str] = []
    with workspace.connect() as connection:
        rows = connection.execute(
            """
            SELECT
                i.item_id,
                i.source_thought_id,
                i.target_thought_id,
                i.split_role,
                r.submitted_at
            FROM annotation_items i
            JOIN annotation_responses r ON r.item_id=i.item_id
            WHERE i.participant_id=?
              AND i.stream='proposal'
              AND i.repeat_of_item_id IS NULL
              AND r.skipped=0
              AND NOT EXISTS (
                  SELECT 1 FROM annotation_items repeat
                  WHERE repeat.repeat_of_item_id=i.item_id
              )
            """,
            (participant_id,),
        ).fetchall()
        eligible = [
            row
            for row in rows
            if parse_timestamp(row["submitted_at"])
            <= now - timedelta(days=minimum_delay_days)
        ]
        count = math.ceil(len(eligible) * rate) if eligible else 0
        selected = sorted(
            eligible,
            key=lambda row: hashlib.sha256(
                f"{participant_id}\0{row['item_id']}".encode("utf-8")
            ).hexdigest(),
        )[:count]
        realized_probability = count / len(eligible) if eligible else None
        for row in selected:
            item_id = _new_item_id()
            connection.execute(
                """
                INSERT INTO annotation_items(
                    item_id, participant_id, source_thought_id,
                    target_thought_id, stream, sampling_source,
                    selection_probability, exposure_status,
                    repeat_of_item_id, sequence_number, split_role, created_at
                ) VALUES(
                    ?, ?, ?, ?, 'proposal', 'blind_repeat', ?,
                    'not_exported', ?, 0, ?, ?
                )
                """,
                (
                    item_id,
                    participant_id,
                    row["source_thought_id"],
                    row["target_thought_id"],
                    realized_probability,
                    row["item_id"],
                    row["split_role"],
                    timestamp(now),
                ),
            )
            created.append(item_id)
        workspace._audit(
            connection,
            participant_id,
            "blind_repeats_created",
            {
                "eligible_count": len(eligible),
                "created_count": len(created),
                "rate": rate,
                "minimum_delay_days": minimum_delay_days,
            },
        )
    return {
        "eligible_count": len(eligible),
        "created_count": len(created),
        "item_ids": created,
        "repeat_identity_exposed_in_export": False,
    }


def export_annotation_batch(
    workspace: PrivateWorkspace,
    *,
    participant_id: str,
    stream: str,
    output_path: str | Path,
    limit: int = 20,
) -> dict[str, Any]:
    workspace.validate()
    _require_annotation_consent(workspace, participant_id)
    if stream not in {"discovery", "proposal"}:
        raise ValueError("stream must be discovery or proposal")
    if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
        raise ValueError("limit must be a positive integer")
    output = workspace.managed_path(output_path)
    if output.exists():
        raise ValueError(f"annotation export already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with workspace.connect() as connection:
        rows = connection.execute(
            """
            SELECT
                i.item_id,
                i.source_thought_id,
                i.target_thought_id,
                s.redacted_text AS source_text,
                s.captured_at AS source_captured_at,
                t.redacted_text AS target_text,
                t.captured_at AS target_captured_at
            FROM annotation_items i
            JOIN thoughts s ON s.thought_id=i.source_thought_id
            LEFT JOIN thoughts t ON t.thought_id=i.target_thought_id
            WHERE i.participant_id=?
              AND i.stream=?
              AND i.exposure_status='not_exported'
            ORDER BY s.captured_at, i.sequence_number, i.item_id
            LIMIT ?
            """,
            (participant_id, stream, limit),
        ).fetchall()
        if not rows:
            raise ValueError(f"no unexported {stream} annotation items")
        batch_id = f"batch_{uuid.uuid4().hex}"
        created_at = timestamp(utc_now())
        items: list[dict[str, Any]] = []
        for row in rows:
            item: dict[str, Any] = {
                "item_id": row["item_id"],
                "stream": stream,
                "source": {
                    "thought_id": row["source_thought_id"],
                    "text": row["source_text"],
                    "captured_at": row["source_captured_at"],
                },
                "relation_types_optional": True,
                "rationale_optional": True,
                "response_time_unit": "milliseconds",
            }
            if stream == "discovery":
                item["prompt"] = (
                    "Before viewing suggestions, record any earlier thought "
                    "you independently remember as essential; an empty list "
                    "is a valid response."
                )
                item["candidate"] = None
            else:
                item["prompt"] = (
                    "Choose one verdict for the directed relationship from "
                    "the source thought to this earlier candidate."
                )
                item["candidate"] = {
                    "thought_id": row["target_thought_id"],
                    "text": row["target_text"],
                    "captured_at": row["target_captured_at"],
                }
                item["choices"] = [
                    verdict.value for verdict in Verdict
                ]
            items.append(item)
        payload = {
            "schema_version": ANNOTATION_SCHEMA_VERSION,
            "batch_id": batch_id,
            "participant_id": participant_id,
            "stream": stream,
            "created_at": created_at,
            "privacy": {
                "content_view": "derived-redacted",
                "local_only": True,
                "contains_private_data": True,
            },
            "items": items,
        }
        temporary = output.with_name(
            f"{output.name}.tmp-{uuid.uuid4().hex}"
        )
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, output)
        exported_at = timestamp(utc_now())
        exposure_status = (
            "prompt_shown" if stream == "discovery" else "candidate_shown"
        )
        connection.executemany(
            """
            UPDATE annotation_items
            SET exposure_status=?, exported_at=?
            WHERE item_id=?
            """,
            [
                (exposure_status, exported_at, row["item_id"])
                for row in rows
            ],
        )
    digest = _file_sha256(output)
    export_id = workspace.register_export(
        participant_id=participant_id,
        purpose="annotation_batch",
        path=output,
        includes_raw=False,
        sha256=digest,
    )
    return {
        "batch_id": batch_id,
        "export_id": export_id,
        "path": str(output),
        "sha256": digest,
        "item_count": len(items),
        "stream": stream,
        "repeat_identity_exposed": False,
    }


def _response_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
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
        rows.append(value)
    if not rows:
        raise ValueError("annotation response file contains no responses")
    return rows


def _response_value(
    value: Any,
    field: str,
    expected_type: type,
) -> Any:
    if not isinstance(value, expected_type):
        raise ValueError(f"{field} must be {expected_type.__name__}")
    return value


def import_annotation_responses(
    workspace: PrivateWorkspace,
    *,
    participant_id: str,
    response_path: str | Path,
) -> dict[str, Any]:
    workspace.validate()
    _require_annotation_consent(workspace, participant_id)
    path = workspace.managed_path(response_path)
    if not path.is_file():
        raise ValueError(f"missing annotation response file: {path}")
    rows = _response_rows(path)
    imported = 0
    gold_created = 0
    with workspace.connect() as connection:
        tracked = connection.execute(
            "SELECT 1 FROM exports WHERE path=?",
            (str(path),),
        ).fetchone()
        if tracked is not None:
            raise ValueError(
                "annotation response file is already managed/imported"
            )
        for row_number, value in enumerate(rows, start=1):
            required = {
                "item_id",
                "response_ms",
                "skipped",
                "submitted_at",
            }
            optional = {
                "verdict",
                "relation_types",
                "rationale",
                "discovered_target_ids",
            }
            missing = required - value.keys()
            unknown = value.keys() - required - optional
            if missing or unknown:
                raise ValueError(
                    f"response {row_number} fields differ; "
                    f"missing={sorted(missing)}, unknown={sorted(unknown)}"
                )
            item_id = _response_value(
                value["item_id"], "item_id", str
            ).strip()
            if not item_id:
                raise ValueError("item_id must be non-empty")
            response_ms = value["response_ms"]
            if (
                isinstance(response_ms, bool)
                or not isinstance(response_ms, int)
                or response_ms < 0
            ):
                raise ValueError("response_ms must be a non-negative integer")
            skipped = value["skipped"]
            if not isinstance(skipped, bool):
                raise ValueError("skipped must be a boolean")
            submitted_at = parse_timestamp(value["submitted_at"])
            relation_types = value.get("relation_types", [])
            if (
                not isinstance(relation_types, list)
                or any(
                    not isinstance(item, str) or not item.strip()
                    for item in relation_types
                )
                or len(relation_types) != len(set(relation_types))
            ):
                raise ValueError(
                    "relation_types must contain unique non-empty strings"
                )
            rationale = value.get("rationale")
            if rationale is not None and not isinstance(rationale, str):
                raise ValueError("rationale must be a string or null")
            item = connection.execute(
                """
                SELECT * FROM annotation_items
                WHERE item_id=? AND participant_id=?
                """,
                (item_id, participant_id),
            ).fetchone()
            if item is None:
                raise ValueError(f"unknown annotation item: {item_id}")
            if item["exported_at"] is None:
                raise ValueError(
                    f"annotation item was never exported: {item_id}"
                )
            existing = connection.execute(
                "SELECT 1 FROM annotation_responses WHERE item_id=?",
                (item_id,),
            ).fetchone()
            if existing is not None:
                raise ValueError(
                    f"annotation response cannot be overwritten: {item_id}"
                )

            discovered = value.get("discovered_target_ids", [])
            if (
                not isinstance(discovered, list)
                or any(
                    not isinstance(target_id, str) or not target_id.strip()
                    for target_id in discovered
                )
                or len(discovered) != len(set(discovered))
            ):
                raise ValueError(
                    "discovered_target_ids must contain unique non-empty strings"
                )
            verdict_value = value.get("verdict")
            if item["stream"] == "discovery":
                if verdict_value is not None:
                    raise ValueError(
                        "discovery responses must not set verdict"
                    )
                if skipped and discovered:
                    raise ValueError(
                        "a skipped discovery response cannot contain targets"
                    )
            else:
                if discovered:
                    raise ValueError(
                        "proposal responses cannot contain discovered targets"
                    )
                if skipped:
                    if verdict_value is not None:
                        raise ValueError(
                            "a skipped proposal must not set verdict"
                        )
                else:
                    try:
                        verdict = Verdict(verdict_value)
                    except (TypeError, ValueError) as exc:
                        raise ValueError(
                            "a completed proposal requires a valid verdict"
                        ) from exc
                    if verdict is Verdict.INVALID and relation_types:
                        raise ValueError(
                            "invalid verdicts must not assert relation types"
                        )

            source = connection.execute(
                """
                SELECT captured_at FROM thoughts
                WHERE thought_id=? AND participant_id=?
                """,
                (item["source_thought_id"], participant_id),
            ).fetchone()
            for target_id in discovered:
                target = connection.execute(
                    """
                    SELECT captured_at FROM thoughts
                    WHERE thought_id=? AND participant_id=?
                    """,
                    (target_id, participant_id),
                ).fetchone()
                if target is None:
                    raise ValueError(
                        f"unknown discovered target thought: {target_id}"
                    )
                if target_id == item["source_thought_id"]:
                    raise ValueError(
                        "a discovery response cannot link a thought to itself"
                    )
                if parse_timestamp(target["captured_at"]) >= parse_timestamp(
                    source["captured_at"]
                ):
                    raise ValueError(
                        "temporal leakage: discovered targets must predate source"
                    )

            response_id = f"response_{uuid.uuid4().hex}"
            connection.execute(
                """
                INSERT INTO annotation_responses(
                    response_id, participant_id, item_id, verdict,
                    relation_types_json, rationale, response_ms, skipped,
                    discovered_target_ids_json, submitted_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    response_id,
                    participant_id,
                    item_id,
                    verdict_value,
                    json.dumps(relation_types),
                    rationale,
                    response_ms,
                    int(skipped),
                    json.dumps(discovered),
                    timestamp(submitted_at),
                ),
            )
            if not skipped and item["stream"] == "discovery":
                for target_id in discovered:
                    connection.execute(
                        """
                        INSERT INTO gold_judgments(
                            judgment_id, participant_id, response_id,
                            source_thought_id, target_thought_id, verdict,
                            relation_types_json, rationale, stream,
                            sampling_source, exposure_status, response_ms,
                            split_role, created_at
                        ) VALUES(
                            ?, ?, ?, ?, ?, 'essential', ?, ?, 'discovery',
                            'user_recall', 'unexposed', ?, ?, ?
                        )
                        """,
                        (
                            f"gold_{uuid.uuid4().hex}",
                            participant_id,
                            response_id,
                            item["source_thought_id"],
                            target_id,
                            json.dumps(relation_types),
                            rationale,
                            response_ms,
                            item["split_role"],
                            timestamp(submitted_at),
                        ),
                    )
                    gold_created += 1
            elif not skipped:
                connection.execute(
                    """
                    INSERT INTO gold_judgments(
                        judgment_id, participant_id, response_id,
                        source_thought_id, target_thought_id, verdict,
                        relation_types_json, rationale, stream,
                        sampling_source, exposure_status, response_ms,
                        split_role, created_at
                    ) VALUES(
                        ?, ?, ?, ?, ?, ?, ?, ?, 'proposal',
                        ?, 'candidate_shown', ?, ?, ?
                    )
                    """,
                    (
                        f"gold_{uuid.uuid4().hex}",
                        participant_id,
                        response_id,
                        item["source_thought_id"],
                        item["target_thought_id"],
                        verdict_value,
                        json.dumps(relation_types),
                        rationale,
                        response_ms,
                        item["sampling_source"],
                        item["split_role"],
                        timestamp(submitted_at),
                    ),
                )
                gold_created += 1
            imported += 1
        workspace._audit(
            connection,
            participant_id,
            "annotation_responses_imported",
            {
                "response_file_sha256": _file_sha256(path),
                "response_count": imported,
                "gold_judgment_count": gold_created,
            },
        )
    digest = _file_sha256(path)
    export_id = workspace.register_export(
        participant_id=participant_id,
        purpose="annotation_response",
        path=path,
        includes_raw=False,
        sha256=digest,
    )
    return {
        "response_count": imported,
        "gold_judgment_count": gold_created,
        "response_file_sha256": digest,
        "managed_file_id": export_id,
    }
