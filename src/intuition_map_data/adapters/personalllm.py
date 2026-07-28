from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator

RESPONSE_COUNT = 8
REWARD_PATTERN = re.compile(r"^response_([1-8])_(.+)$")


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    return value


@dataclass(frozen=True, slots=True)
class PersonalLLMCandidate:
    index: int
    text: str
    model: str


@dataclass(frozen=True, slots=True)
class PersonalLLMRecord:
    id: int
    prompt_id: int
    subset: str
    prompt: str
    candidates: tuple[PersonalLLMCandidate, ...]
    rewards: dict[str, tuple[float, ...]]

    def preferred_candidate(self, profile: str) -> PersonalLLMCandidate:
        try:
            scores = self.rewards[profile]
        except KeyError as exc:
            raise ValueError(f"unknown PersonalLLM profile: {profile}") from exc
        best_index = max(range(RESPONSE_COUNT), key=lambda index: (scores[index], -index))
        return self.candidates[best_index]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PersonalLLMRecord:
        required = {"id", "prompt_id", "subset", "prompt"}
        candidates: list[PersonalLLMCandidate] = []
        for index in range(1, RESPONSE_COUNT + 1):
            response_field = f"response_{index}"
            model_field = f"response_{index}_model"
            required.update({response_field, model_field})
            candidates.append(
                PersonalLLMCandidate(
                    index=index,
                    text=_string(data.get(response_field), response_field),
                    model=_string(data.get(model_field), model_field),
                )
            )
        missing = required - data.keys()
        if missing:
            raise ValueError(f"PersonalLLM record missing fields: {sorted(missing)}")

        reward_values: dict[str, dict[int, float]] = {}
        unknown: list[str] = []
        for field, value in data.items():
            if field in required:
                continue
            match = REWARD_PATTERN.fullmatch(field)
            if match is None or match.group(2) == "model":
                unknown.append(field)
                continue
            index = int(match.group(1))
            profile = match.group(2)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{field} must be numeric")
            score = float(value)
            if not math.isfinite(score):
                raise ValueError(f"{field} must be finite")
            reward_values.setdefault(profile, {})[index] = score
        if unknown:
            raise ValueError(f"PersonalLLM record has unknown fields: {sorted(unknown)}")
        if not reward_values:
            raise ValueError("PersonalLLM record must include a reward profile")
        rewards: dict[str, tuple[float, ...]] = {}
        expected_indices = set(range(1, RESPONSE_COUNT + 1))
        for profile, values in reward_values.items():
            if values.keys() != expected_indices:
                missing_indices = expected_indices - values.keys()
                raise ValueError(
                    f"PersonalLLM profile {profile} missing response scores: "
                    f"{sorted(missing_indices)}"
                )
            rewards[profile] = tuple(values[index] for index in range(1, 9))
        return cls(
            id=_integer(data["id"], "id"),
            prompt_id=_integer(data["prompt_id"], "prompt_id"),
            subset=_string(data["subset"], "subset"),
            prompt=_string(data["prompt"], "prompt"),
            candidates=tuple(candidates),
            rewards=dict(sorted(rewards.items())),
        )


def iter_personalllm_jsonl(path: str | Path) -> Iterable[PersonalLLMRecord]:
    seen_ids: set[int] = set()
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"{Path(path).name}:{line_number}: invalid JSON: {exc.msg}"
                ) from exc
            if not isinstance(value, dict):
                raise ValueError(
                    f"{Path(path).name}:{line_number}: expected an object"
                )
            try:
                record = PersonalLLMRecord.from_dict(value)
            except ValueError as exc:
                raise ValueError(f"{Path(path).name}:{line_number}: {exc}") from exc
            if record.id in seen_ids:
                raise ValueError(f"duplicate PersonalLLM id: {record.id}")
            seen_ids.add(record.id)
            yield record


def inspect_parquet_container(path: str | Path) -> dict[str, object]:
    parquet_path = Path(path)
    size = parquet_path.stat().st_size
    if size < 8:
        raise ValueError("Parquet artifact is too small")
    with parquet_path.open("rb") as handle:
        prefix = handle.read(4)
        handle.seek(-4, 2)
        suffix = handle.read(4)
    if prefix != b"PAR1" or suffix != b"PAR1":
        raise ValueError("artifact does not have a valid Parquet container signature")
    return {"format": "parquet", "size_bytes": size, "container_signature": "PAR1"}


def iter_personalllm_parquet(path: str | Path) -> Iterator[PersonalLLMRecord]:
    inspect_parquet_container(path)
    try:
        import pyarrow.parquet as parquet
    except ImportError as exc:
        raise RuntimeError(
            "Reading native PersonalLLM Parquet rows requires the optional "
            "'public-data' dependency."
        ) from exc
    table = parquet.read_table(path)
    for batch in table.to_batches(max_chunksize=256):
        for value in batch.to_pylist():
            yield PersonalLLMRecord.from_dict(value)
