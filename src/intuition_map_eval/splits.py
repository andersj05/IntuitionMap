from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable


@dataclass(frozen=True, slots=True)
class QueryObservation:
    query_id: str
    captured_at: datetime


@dataclass(frozen=True, slots=True)
class RollingOriginSplit:
    index: int
    train_query_ids: tuple[str, ...]
    validation_query_ids: tuple[str, ...]
    test_query_ids: tuple[str, ...]
    train_end: str
    validation_end: str
    definition_sha256: str

    def to_dict(self) -> dict[str, object]:
        return {
            "index": self.index,
            "train_query_ids": list(self.train_query_ids),
            "validation_query_ids": list(self.validation_query_ids),
            "test_query_ids": list(self.test_query_ids),
            "train_end": self.train_end,
            "validation_end": self.validation_end,
            "definition_sha256": self.definition_sha256,
        }


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("split timestamps must include a timezone")
    return value.isoformat()


def rolling_origin_splits(
    observations: Iterable[QueryObservation],
    *,
    initial_train_blocks: int,
    validation_blocks: int,
    test_blocks: int,
    step_blocks: int | None = None,
) -> tuple[RollingOriginSplit, ...]:
    for name, value in {
        "initial_train_blocks": initial_train_blocks,
        "validation_blocks": validation_blocks,
        "test_blocks": test_blocks,
    }.items():
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{name} must be a positive integer")
    if step_blocks is None:
        step_blocks = test_blocks
    if (
        isinstance(step_blocks, bool)
        or not isinstance(step_blocks, int)
        or step_blocks <= 0
    ):
        raise ValueError("step_blocks must be a positive integer")

    timestamp_by_query: dict[str, datetime] = {}
    for observation in observations:
        if not observation.query_id:
            raise ValueError("query_id must be non-empty")
        _timestamp(observation.captured_at)
        previous = timestamp_by_query.setdefault(
            observation.query_id, observation.captured_at
        )
        if previous != observation.captured_at:
            raise ValueError(
                f"query {observation.query_id} spans multiple timestamps"
            )
    if not timestamp_by_query:
        raise ValueError("rolling splits require at least one query")

    blocks: list[tuple[datetime, tuple[str, ...]]] = []
    for captured_at in sorted(set(timestamp_by_query.values())):
        query_ids = tuple(
            sorted(
                query_id
                for query_id, timestamp in timestamp_by_query.items()
                if timestamp == captured_at
            )
        )
        blocks.append((captured_at, query_ids))

    splits: list[RollingOriginSplit] = []
    train_end_index = initial_train_blocks
    while (
        train_end_index + validation_blocks + test_blocks
        <= len(blocks)
    ):
        train = blocks[:train_end_index]
        validation = blocks[
            train_end_index : train_end_index + validation_blocks
        ]
        test = blocks[
            train_end_index
            + validation_blocks : train_end_index
            + validation_blocks
            + test_blocks
        ]
        payload = {
            "index": len(splits),
            "train_query_ids": [
                query_id for _, query_ids in train for query_id in query_ids
            ],
            "validation_query_ids": [
                query_id
                for _, query_ids in validation
                for query_id in query_ids
            ],
            "test_query_ids": [
                query_id for _, query_ids in test for query_id in query_ids
            ],
            "train_end": _timestamp(train[-1][0]),
            "validation_end": _timestamp(validation[-1][0]),
        }
        canonical = json.dumps(
            payload, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        splits.append(
            RollingOriginSplit(
                index=payload["index"],
                train_query_ids=tuple(payload["train_query_ids"]),
                validation_query_ids=tuple(payload["validation_query_ids"]),
                test_query_ids=tuple(payload["test_query_ids"]),
                train_end=payload["train_end"],
                validation_end=payload["validation_end"],
                definition_sha256=hashlib.sha256(canonical).hexdigest(),
            )
        )
        train_end_index += step_blocks
    if not splits:
        raise ValueError(
            "not enough timestamp blocks for the requested rolling split"
        )
    return tuple(splits)
