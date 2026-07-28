from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

from intuition_map_eval.dataset import Dataset
from intuition_map_eval.schema import Thought

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "but",
        "by",
        "for",
        "from",
        "have",
        "i",
        "if",
        "in",
        "into",
        "is",
        "it",
        "like",
        "may",
        "me",
        "more",
        "my",
        "of",
        "on",
        "only",
        "or",
        "rather",
        "should",
        "than",
        "that",
        "the",
        "their",
        "to",
        "when",
        "with",
    }
)


def tokenize(text: str) -> frozenset[str]:
    return frozenset(
        token
        for token in TOKEN_PATTERN.findall(text.lower())
        if token not in STOPWORDS
    )


def _jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 0.0


@dataclass(frozen=True, slots=True)
class Prediction:
    source_id: str
    target_id: str
    rank: int
    score: float
    signals: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "rank": self.rank,
            "score": self.score,
            "signals": self.signals,
        }


@dataclass(frozen=True, slots=True)
class LexicalTemporalConfig:
    context_weight: float = 0.15
    recency_weight: float = 0.05
    recency_half_life_days: float = 30.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LexicalTemporalConfig:
        allowed = {
            "context_weight",
            "recency_weight",
            "recency_half_life_days",
        }
        unknown = data.keys() - allowed
        if unknown:
            raise ValueError(
                f"unknown lexical-temporal parameters: {sorted(unknown)}"
            )
        config = cls(**data)
        if config.context_weight < 0 or config.recency_weight < 0:
            raise ValueError("baseline weights must be non-negative")
        if config.recency_half_life_days <= 0:
            raise ValueError("recency_half_life_days must be positive")
        return config


class LexicalTemporalBaseline:
    def __init__(self, config: LexicalTemporalConfig) -> None:
        self.config = config

    def _score(self, source: Thought, target: Thought) -> tuple[float, dict[str, float]]:
        lexical = _jaccard(tokenize(source.text), tokenize(target.text))
        source_contexts = frozenset(source.contexts)
        target_contexts = frozenset(target.contexts)
        context = _jaccard(source_contexts, target_contexts)
        age_days = (source.created_at - target.created_at).total_seconds() / 86_400
        recency = math.pow(0.5, age_days / self.config.recency_half_life_days)
        score = (
            lexical
            + self.config.context_weight * context
            + self.config.recency_weight * recency
        )
        signals = {
            "lexical_jaccard": lexical,
            "context_jaccard": context,
            "recency": recency,
        }
        return score, signals

    def rank(self, dataset: Dataset) -> tuple[Prediction, ...]:
        predictions: list[Prediction] = []
        for source_index, source in enumerate(dataset.thoughts):
            candidates: list[tuple[Thought, float, dict[str, float]]] = []
            for target in dataset.thoughts[:source_index]:
                score, signals = self._score(source, target)
                candidates.append((target, score, signals))
            candidates.sort(
                key=lambda item: (
                    -item[1],
                    -item[0].created_at.timestamp(),
                    item[0].id,
                )
            )
            predictions.extend(
                Prediction(
                    source_id=source.id,
                    target_id=target.id,
                    rank=rank,
                    score=score,
                    signals=signals,
                )
                for rank, (target, score, signals) in enumerate(
                    candidates, start=1
                )
            )
        return tuple(predictions)

