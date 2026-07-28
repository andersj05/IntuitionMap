from __future__ import annotations

import argparse
import json
import platform
from collections import Counter
from pathlib import Path
from typing import Any

from intuition_map_data.acquisition import (
    acquire_public_dataset,
    load_public_dataset_spec,
    resolve_artifact_destination,
)
from intuition_map_data.adapters.atomic2020 import (
    iter_atomic2020_archive,
    validate_atomic2020_archive,
)
from intuition_map_data.adapters.longmemeval import iter_longmemeval
from intuition_map_data.adapters.personalllm import iter_personalllm_parquet


def _artifact_by_role(
    spec_path: Path, external_root: Path, role: str
) -> Path:
    spec = load_public_dataset_spec(spec_path)
    matches = [
        artifact for artifact in spec.artifacts if artifact.role == role
    ]
    if len(matches) != 1:
        raise ValueError(
            f"{spec.registry_id} must register exactly one {role} artifact"
        )
    return resolve_artifact_destination(external_root, matches[0].destination)


def _validate_longmemeval(path: Path) -> dict[str, Any]:
    question_types: Counter[str] = Counter()
    record_count = 0
    session_count = 0
    turn_count = 0
    evidence_session_count = 0
    numeric_answer_count = 0
    for record in iter_longmemeval(path):
        record_count += 1
        question_types[record.question_type] += 1
        session_count += len(record.sessions)
        evidence_session_count += len(record.evidence_sessions)
        turn_count += sum(len(session.turns) for session in record.sessions)
        numeric_answer_count += isinstance(record.answer, int)
    return {
        "record_count": record_count,
        "session_count": session_count,
        "turn_count": turn_count,
        "evidence_session_count": evidence_session_count,
        "numeric_answer_count": numeric_answer_count,
        "question_types": dict(sorted(question_types.items())),
        "native_task_preserved": True,
    }


def _validate_personalllm(path: Path) -> dict[str, Any]:
    import pyarrow

    profiles: Counter[str] = Counter()
    subsets: Counter[str] = Counter()
    record_count = 0
    for record in iter_personalllm_parquet(path):
        record_count += 1
        profiles.update(record.rewards)
        subsets[record.subset] += 1
    return {
        "record_count": record_count,
        "profile_count": len(profiles),
        "profile_names": sorted(profiles),
        "subsets": dict(sorted(subsets.items())),
        "parquet_reader": f"pyarrow {pyarrow.__version__}",
        "native_task_preserved": True,
    }


def _validate_atomic2020(path: Path) -> dict[str, Any]:
    archive = validate_atomic2020_archive(path)
    split_counts: dict[str, int] = {}
    incomplete_tail_counts: dict[str, int] = {}
    relations: Counter[str] = Counter()
    for split in ("train", "dev", "test"):
        count = 0
        incomplete = 0
        for triple in iter_atomic2020_archive(path, split=split):
            count += 1
            incomplete += not triple.is_complete
            relations[triple.relation] += 1
        split_counts[split] = count
        incomplete_tail_counts[split] = incomplete
    return {
        **archive,
        "split_counts": split_counts,
        "incomplete_tail_counts": incomplete_tail_counts,
        "relation_count": len(relations),
        "relation_names": sorted(relations),
        "native_task_preserved": True,
    }


def validate_public_portfolio(
    config_root: str | Path = Path("configs/data"),
    external_root: str | Path = Path("datasets/external"),
) -> dict[str, Any]:
    config_root = Path(config_root).resolve()
    external_root = Path(external_root).resolve()
    manifest_paths = {
        "longmemeval": config_root / "longmemeval-oracle.json",
        "personalllm": config_root / "personalllm-test.json",
        "atomic2020": config_root / "atomic2020.json",
    }
    acquisition: dict[str, Any] = {}
    for name, path in manifest_paths.items():
        spec = load_public_dataset_spec(path)
        acquisition[name] = acquire_public_dataset(
            spec,
            external_root,
            verify_only=True,
        )
    longmemeval_path = _artifact_by_role(
        manifest_paths["longmemeval"],
        external_root,
        "native-oracle-benchmark",
    )
    personalllm_path = _artifact_by_role(
        manifest_paths["personalllm"],
        external_root,
        "native-test-split",
    )
    atomic_path = _artifact_by_role(
        manifest_paths["atomic2020"],
        external_root,
        "native-release-archive",
    )
    return {
        "schema_version": "0.1.0",
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "acquisition": acquisition,
        "native_adapters": {
            "longmemeval": _validate_longmemeval(longmemeval_path),
            "personalllm": _validate_personalllm(personalllm_path),
            "atomic2020": _validate_atomic2020(atomic_path),
        },
        "private_data_used": False,
        "paid_api_requests": 0,
        "estimated_cost_usd": 0,
        "valid": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify the pinned Phase 1 public-data portfolio."
    )
    parser.add_argument("--config-root", type=Path, default=Path("configs/data"))
    parser.add_argument(
        "--external-root",
        type=Path,
        default=Path("datasets/external"),
    )
    args = parser.parse_args(argv)
    print(
        json.dumps(
            validate_public_portfolio(args.config_root, args.external_root),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
