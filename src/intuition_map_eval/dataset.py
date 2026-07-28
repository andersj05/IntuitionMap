from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, TypeVar

from intuition_map_eval.schema import DatasetManifest, LinkJudgment, Thought

T = TypeVar("T")

DATASET_FILES = ("manifest.json", "thoughts.jsonl", "judgments.jsonl")


@dataclass(frozen=True, slots=True)
class Dataset:
    root: Path
    manifest: DatasetManifest
    thoughts: tuple[Thought, ...]
    judgments: tuple[LinkJudgment, ...]
    fingerprint: str

    @property
    def thoughts_by_id(self) -> dict[str, Thought]:
        return {thought.id: thought for thought in self.thoughts}

    @property
    def judgments_by_source(self) -> dict[str, tuple[LinkJudgment, ...]]:
        grouped: dict[str, list[LinkJudgment]] = {}
        for judgment in self.judgments:
            grouped.setdefault(judgment.source_id, []).append(judgment)
        return {source: tuple(items) for source, items in grouped.items()}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"missing dataset file: {path.name}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path.name}:{exc.lineno}: invalid JSON: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def _load_jsonl(path: Path, parser: Callable[[dict[str, Any]], T]) -> tuple[T, ...]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as exc:
        raise ValueError(f"missing dataset file: {path.name}") from exc
    records: list[T] = []
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
            raise ValueError(f"{path.name}:{line_number}: expected a JSON object")
        try:
            records.append(parser(value))
        except ValueError as exc:
            raise ValueError(f"{path.name}:{line_number}: {exc}") from exc
    return tuple(records)


def dataset_fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    for name in DATASET_FILES:
        path = root / name
        if not path.is_file():
            raise ValueError(f"missing dataset file: {name}")
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def load_dataset(root: str | Path) -> Dataset:
    root = Path(root).resolve()
    manifest = DatasetManifest.from_dict(_load_json(root / "manifest.json"))
    thoughts = _load_jsonl(root / "thoughts.jsonl", Thought.from_dict)
    judgments = _load_jsonl(
        root / "judgments.jsonl", LinkJudgment.from_dict
    )

    if len(thoughts) < 2:
        raise ValueError("a dataset must contain at least two thoughts")
    thought_ids = [thought.id for thought in thoughts]
    if len(thought_ids) != len(set(thought_ids)):
        raise ValueError("thought ids must be unique")
    timestamps = [thought.created_at for thought in thoughts]
    if timestamps != sorted(timestamps):
        raise ValueError("thoughts must be ordered by created_at")

    thoughts_by_id = {thought.id: thought for thought in thoughts}
    seen_pairs: set[tuple[str, str]] = set()
    for judgment in judgments:
        pair = (judgment.source_id, judgment.target_id)
        if pair in seen_pairs:
            raise ValueError(f"duplicate judgment for pair {pair}")
        seen_pairs.add(pair)
        if judgment.source_id not in thoughts_by_id:
            raise ValueError(f"unknown source thought: {judgment.source_id}")
        if judgment.target_id not in thoughts_by_id:
            raise ValueError(f"unknown target thought: {judgment.target_id}")
        source = thoughts_by_id[judgment.source_id]
        target = thoughts_by_id[judgment.target_id]
        if target.created_at >= source.created_at:
            raise ValueError(
                f"temporal leakage: target {target.id} must predate source {source.id}"
            )

    return Dataset(
        root=root,
        manifest=manifest,
        thoughts=thoughts,
        judgments=judgments,
        fingerprint=dataset_fingerprint(root),
    )


def validation_summary(dataset: Dataset) -> dict[str, Any]:
    verdict_counts: dict[str, int] = {}
    for judgment in dataset.judgments:
        verdict_counts[judgment.verdict.value] = (
            verdict_counts.get(judgment.verdict.value, 0) + 1
        )
    return {
        "dataset": dataset.manifest.name,
        "fingerprint": dataset.fingerprint,
        "thought_count": len(dataset.thoughts),
        "judgment_count": len(dataset.judgments),
        "judgment_counts": dict(sorted(verdict_counts.items())),
        "annotation_exhaustive": dataset.manifest.annotation.exhaustive,
        "unlabeled_pairs_are": dataset.manifest.annotation.unlabeled_pairs_are,
        "valid": True,
    }

