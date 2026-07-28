from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from intuition_map_eval.schema import parse_timestamp

POLICY_VERSION = "0.1.0"
ALLOWED_PURPOSES = frozenset(
    {"local_retrieval_research", "annotation_pilot"}
)
REQUIRED_ACKNOWLEDGEMENTS = frozenset(
    {
        "owns_or_controls_content",
        "understands_sensitive_data_risk",
        "understands_deletion_limits",
        "understands_local_storage_is_not_app_encryption",
    }
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("timestamps must include a timezone")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _non_empty(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _unique_strings(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    result = tuple(_non_empty(item, field) for item in value)
    if len(result) != len(set(result)):
        raise ValueError(f"{field} must not contain duplicates")
    return result


@dataclass(frozen=True, slots=True)
class ConsentReceipt:
    consent_id: str
    participant_id: str
    granted_at: datetime
    purposes: tuple[str, ...]
    source_types: tuple[str, ...]
    local_only: bool
    store_raw_content: bool
    allow_derived_features: bool
    allow_training_use: bool
    retention_days: int
    acknowledgements: tuple[str, ...]
    policy_version: str = POLICY_VERSION

    @classmethod
    def create(
        cls,
        *,
        participant_id: str,
        purposes: Iterable[str],
        source_types: Iterable[str],
        retention_days: int,
        acknowledgements: Iterable[str],
        store_raw_content: bool = True,
        allow_derived_features: bool = True,
        allow_training_use: bool = False,
        local_only: bool = True,
        granted_at: datetime | None = None,
        consent_id: str | None = None,
    ) -> ConsentReceipt:
        value = cls(
            consent_id=consent_id or f"consent_{uuid.uuid4().hex}",
            participant_id=participant_id,
            granted_at=granted_at or utc_now(),
            purposes=tuple(purposes),
            source_types=tuple(source_types),
            local_only=local_only,
            store_raw_content=store_raw_content,
            allow_derived_features=allow_derived_features,
            allow_training_use=allow_training_use,
            retention_days=retention_days,
            acknowledgements=tuple(acknowledgements),
        )
        value.validate()
        return value

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConsentReceipt:
        expected = {
            "schema_version",
            "consent_id",
            "participant_id",
            "granted_at",
            "purposes",
            "source_types",
            "local_only",
            "store_raw_content",
            "allow_derived_features",
            "allow_training_use",
            "retention_days",
            "acknowledgements",
        }
        if data.keys() != expected:
            raise ValueError(
                "consent fields differ; "
                f"missing={sorted(expected - data.keys())}, "
                f"unknown={sorted(data.keys() - expected)}"
            )
        receipt = cls(
            policy_version=_non_empty(
                data["schema_version"], "schema_version"
            ),
            consent_id=_non_empty(data["consent_id"], "consent_id"),
            participant_id=_non_empty(
                data["participant_id"], "participant_id"
            ),
            granted_at=parse_timestamp(data["granted_at"]),
            purposes=_unique_strings(data["purposes"], "purposes"),
            source_types=_unique_strings(
                data["source_types"], "source_types"
            ),
            local_only=data["local_only"],
            store_raw_content=data["store_raw_content"],
            allow_derived_features=data["allow_derived_features"],
            allow_training_use=data["allow_training_use"],
            retention_days=data["retention_days"],
            acknowledgements=_unique_strings(
                data["acknowledgements"], "acknowledgements"
            ),
        )
        receipt.validate()
        return receipt

    def validate(self) -> None:
        _non_empty(self.consent_id, "consent_id")
        _non_empty(self.participant_id, "participant_id")
        timestamp(self.granted_at)
        if self.policy_version != POLICY_VERSION:
            raise ValueError("unsupported consent policy version")
        if not self.purposes or not set(self.purposes) <= ALLOWED_PURPOSES:
            raise ValueError(
                f"purposes must be selected from {sorted(ALLOWED_PURPOSES)}"
            )
        if len(self.purposes) != len(set(self.purposes)):
            raise ValueError("purposes must not contain duplicates")
        if (
            not self.source_types
            or any(not item.strip() for item in self.source_types)
            or len(self.source_types) != len(set(self.source_types))
        ):
            raise ValueError("source_types must contain unique non-empty values")
        for field, value in {
            "local_only": self.local_only,
            "store_raw_content": self.store_raw_content,
            "allow_derived_features": self.allow_derived_features,
            "allow_training_use": self.allow_training_use,
        }.items():
            if not isinstance(value, bool):
                raise ValueError(f"{field} must be a boolean")
        if not self.local_only:
            raise ValueError(
                "policy version 0.1.0 permits only local-only processing"
            )
        if (
            isinstance(self.retention_days, bool)
            or not isinstance(self.retention_days, int)
            or self.retention_days <= 0
        ):
            raise ValueError("retention_days must be a positive integer")
        if not REQUIRED_ACKNOWLEDGEMENTS <= set(self.acknowledgements):
            raise ValueError(
                "missing required acknowledgements: "
                f"{sorted(REQUIRED_ACKNOWLEDGEMENTS - set(self.acknowledgements))}"
            )
        if len(self.acknowledgements) != len(set(self.acknowledgements)):
            raise ValueError("acknowledgements must not contain duplicates")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "schema_version": self.policy_version,
            "consent_id": self.consent_id,
            "participant_id": self.participant_id,
            "granted_at": timestamp(self.granted_at),
            "purposes": list(self.purposes),
            "source_types": list(self.source_types),
            "local_only": self.local_only,
            "store_raw_content": self.store_raw_content,
            "allow_derived_features": self.allow_derived_features,
            "allow_training_use": self.allow_training_use,
            "retention_days": self.retention_days,
            "acknowledgements": list(self.acknowledgements),
        }

    @property
    def sha256(self) -> str:
        canonical = json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()
