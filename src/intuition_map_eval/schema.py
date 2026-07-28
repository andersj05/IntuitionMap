from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


class Verdict(StrEnum):
    ESSENTIAL = "essential"
    VALID = "valid"
    INVALID = "invalid"
    UNCERTAIN = "uncertain"

    @property
    def is_relevant(self) -> bool:
        return self in {Verdict.ESSENTIAL, Verdict.VALID}


def parse_timestamp(value: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError("created_at must be a non-empty ISO-8601 string")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("created_at must include a timezone")
    return parsed.astimezone(timezone.utc)


def _validate_keys(
    data: dict[str, Any], required: set[str], optional: set[str], record: str
) -> None:
    missing = required - data.keys()
    unknown = data.keys() - required - optional
    if missing:
        raise ValueError(f"{record} is missing required fields: {sorted(missing)}")
    if unknown:
        raise ValueError(f"{record} has unknown fields: {sorted(unknown)}")


def _non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _string_tuple(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list of strings")
    result = tuple(_non_empty_string(item, field) for item in value)
    if len(result) != len(set(result)):
        raise ValueError(f"{field} must not contain duplicates")
    return result


@dataclass(frozen=True, slots=True)
class Thought:
    id: str
    text: str
    created_at: datetime
    contexts: tuple[str, ...]
    explicit_links: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Thought:
        _validate_keys(
            data,
            required={"id", "text", "created_at"},
            optional={"contexts", "explicit_links"},
            record="thought",
        )
        return cls(
            id=_non_empty_string(data["id"], "id"),
            text=_non_empty_string(data["text"], "text"),
            created_at=parse_timestamp(data["created_at"]),
            contexts=_string_tuple(data.get("contexts", []), "contexts"),
            explicit_links=_string_tuple(
                data.get("explicit_links", []), "explicit_links"
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "created_at": self.created_at.isoformat().replace("+00:00", "Z"),
            "contexts": list(self.contexts),
            "explicit_links": list(self.explicit_links),
        }


@dataclass(frozen=True, slots=True)
class LinkJudgment:
    source_id: str
    target_id: str
    verdict: Verdict
    relation_types: tuple[str, ...]
    strength: float
    rationale: str
    annotator: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LinkJudgment:
        _validate_keys(
            data,
            required={
                "source_id",
                "target_id",
                "verdict",
                "relation_types",
                "strength",
                "rationale",
                "annotator",
            },
            optional=set(),
            record="judgment",
        )
        try:
            verdict = Verdict(data["verdict"])
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"verdict must be one of {[item.value for item in Verdict]}"
            ) from exc
        strength = data["strength"]
        if isinstance(strength, bool) or not isinstance(strength, (int, float)):
            raise ValueError("strength must be a number between 0 and 1")
        strength = float(strength)
        if not 0.0 <= strength <= 1.0:
            raise ValueError("strength must be between 0 and 1")
        source_id = _non_empty_string(data["source_id"], "source_id")
        target_id = _non_empty_string(data["target_id"], "target_id")
        if source_id == target_id:
            raise ValueError("a judgment cannot link a thought to itself")
        relation_types = _string_tuple(data["relation_types"], "relation_types")
        if verdict is Verdict.INVALID and relation_types:
            raise ValueError("invalid judgments must not assert relation types")
        return cls(
            source_id=source_id,
            target_id=target_id,
            verdict=verdict,
            relation_types=relation_types,
            strength=strength,
            rationale=_non_empty_string(data["rationale"], "rationale"),
            annotator=_non_empty_string(data["annotator"], "annotator"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "verdict": self.verdict.value,
            "relation_types": list(self.relation_types),
            "strength": self.strength,
            "rationale": self.rationale,
            "annotator": self.annotator,
        }


@dataclass(frozen=True, slots=True)
class AnnotationPolicy:
    candidate_pool: str
    exhaustive: bool
    unlabeled_pairs_are: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AnnotationPolicy:
        _validate_keys(
            data,
            required={"candidate_pool", "exhaustive", "unlabeled_pairs_are"},
            optional=set(),
            record="annotation policy",
        )
        if data["candidate_pool"] != "all_prior_thoughts":
            raise ValueError("candidate_pool must be 'all_prior_thoughts'")
        if not isinstance(data["exhaustive"], bool):
            raise ValueError("annotation.exhaustive must be a boolean")
        if data["unlabeled_pairs_are"] != "unknown":
            raise ValueError("unlabeled_pairs_are must be 'unknown'")
        return cls(
            candidate_pool=data["candidate_pool"],
            exhaustive=data["exhaustive"],
            unlabeled_pairs_are=data["unlabeled_pairs_are"],
        )


@dataclass(frozen=True, slots=True)
class DatasetManifest:
    schema_version: str
    name: str
    description: str
    provenance: str
    contains_personal_data: bool
    annotation: AnnotationPolicy

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DatasetManifest:
        _validate_keys(
            data,
            required={
                "schema_version",
                "name",
                "description",
                "provenance",
                "contains_personal_data",
                "annotation",
            },
            optional=set(),
            record="dataset manifest",
        )
        if data["schema_version"] != "0.1.0":
            raise ValueError("unsupported dataset schema_version")
        if not isinstance(data["contains_personal_data"], bool):
            raise ValueError("contains_personal_data must be a boolean")
        if not isinstance(data["annotation"], dict):
            raise ValueError("annotation must be an object")
        return cls(
            schema_version=data["schema_version"],
            name=_non_empty_string(data["name"], "name"),
            description=_non_empty_string(data["description"], "description"),
            provenance=_non_empty_string(data["provenance"], "provenance"),
            contains_personal_data=data["contains_personal_data"],
            annotation=AnnotationPolicy.from_dict(data["annotation"]),
        )
