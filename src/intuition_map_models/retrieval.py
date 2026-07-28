from __future__ import annotations

import hashlib
import math
import re
import zlib
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Iterable, Protocol

from intuition_map_eval.baseline import Prediction, STOPWORDS
from intuition_map_eval.dataset import Dataset

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


@lru_cache(maxsize=512)
def tokenize(text: str) -> tuple[str, ...]:
    """Return deterministic retrieval terms without high-frequency function words."""

    return tuple(
        token
        for token in TOKEN_PATTERN.findall(text.lower())
        if token not in STOPWORDS
    )


@dataclass(frozen=True, slots=True)
class RetrievalCandidate:
    candidate_id: str
    text: str
    order: int
    timestamp: datetime | None = None
    contexts: tuple[str, ...] = ()
    native_id: str | None = None


@dataclass(frozen=True, slots=True)
class RetrievalQuery:
    query_id: str
    text: str
    candidates: tuple[RetrievalCandidate, ...]
    explicit_target_ids: tuple[str, ...] = ()
    contexts: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RankedCandidate:
    query_id: str
    candidate_id: str
    rank: int
    score: float
    signals: dict[str, float]
    method: str


class Ranker(Protocol):
    name: str

    def rank(self, query: RetrievalQuery) -> tuple[RankedCandidate, ...]:
        ...


def _validate_query(query: RetrievalQuery) -> None:
    candidate_ids = [candidate.candidate_id for candidate in query.candidates]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError(
            f"retrieval query {query.query_id} has duplicate candidate ids"
        )
    unknown_links = set(query.explicit_target_ids) - set(candidate_ids)
    if unknown_links:
        raise ValueError(
            f"retrieval query {query.query_id} has unknown explicit targets: "
            f"{sorted(unknown_links)}"
        )


def _rank_scored(
    query: RetrievalQuery,
    method: str,
    scored: Iterable[tuple[RetrievalCandidate, float, dict[str, float]]],
) -> tuple[RankedCandidate, ...]:
    _validate_query(query)
    values = list(scored)
    for _, score, signals in values:
        if not math.isfinite(score) or any(
            not math.isfinite(value) for value in signals.values()
        ):
            raise ValueError(f"{method} produced a non-finite score")
    values.sort(key=lambda item: (-item[1], item[0].candidate_id))
    return tuple(
        RankedCandidate(
            query_id=query.query_id,
            candidate_id=candidate.candidate_id,
            rank=rank,
            score=score,
            signals=signals,
            method=method,
        )
        for rank, (candidate, score, signals) in enumerate(values, start=1)
    )


class StableRandomRanker:
    name = "stable_random"

    def __init__(self, seed: int) -> None:
        self.seed = seed

    def rank(self, query: RetrievalQuery) -> tuple[RankedCandidate, ...]:
        def score(candidate: RetrievalCandidate) -> float:
            payload = (
                f"{self.seed}\0{query.query_id}\0{candidate.candidate_id}"
            ).encode("utf-8")
            integer = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")
            return integer / ((1 << 64) - 1)

        return _rank_scored(
            query,
            self.name,
            (
                (candidate, value, {"stable_random": value})
                for candidate in query.candidates
                for value in (score(candidate),)
            ),
        )


class MostRecentRanker:
    name = "most_recent"

    def rank(self, query: RetrievalQuery) -> tuple[RankedCandidate, ...]:
        def score(candidate: RetrievalCandidate) -> float:
            if candidate.timestamp is not None:
                return candidate.timestamp.timestamp()
            return float(candidate.order)

        return _rank_scored(
            query,
            self.name,
            (
                (candidate, value, {"recency_order": value})
                for candidate in query.candidates
                for value in (score(candidate),)
            ),
        )


class TfIdfRanker:
    name = "tfidf"

    def rank(self, query: RetrievalQuery) -> tuple[RankedCandidate, ...]:
        candidate_counts = [
            Counter(tokenize(candidate.text)) for candidate in query.candidates
        ]
        document_count = len(candidate_counts)
        document_frequency: Counter[str] = Counter()
        for counts in candidate_counts:
            document_frequency.update(counts.keys())

        def idf(term: str) -> float:
            return math.log(
                (1 + document_count) / (1 + document_frequency[term])
            ) + 1.0

        query_counts = Counter(tokenize(query.text))
        query_vector = {
            term: count * idf(term) for term, count in query_counts.items()
        }
        query_norm = math.sqrt(
            sum(value * value for value in query_vector.values())
        )
        scored: list[tuple[RetrievalCandidate, float, dict[str, float]]] = []
        for candidate, counts in zip(query.candidates, candidate_counts):
            vector = {term: count * idf(term) for term, count in counts.items()}
            norm = math.sqrt(sum(value * value for value in vector.values()))
            dot = sum(
                query_value * vector.get(term, 0.0)
                for term, query_value in query_vector.items()
            )
            cosine = dot / (query_norm * norm) if query_norm and norm else 0.0
            scored.append((candidate, cosine, {"tfidf_cosine": cosine}))
        return _rank_scored(query, self.name, scored)


class BM25Ranker:
    name = "bm25"

    def __init__(self, *, k1: float = 1.2, b: float = 0.75) -> None:
        if k1 <= 0:
            raise ValueError("BM25 k1 must be positive")
        if not 0 <= b <= 1:
            raise ValueError("BM25 b must be between 0 and 1")
        self.k1 = k1
        self.b = b

    def rank(self, query: RetrievalQuery) -> tuple[RankedCandidate, ...]:
        candidate_counts = [
            Counter(tokenize(candidate.text)) for candidate in query.candidates
        ]
        document_count = len(candidate_counts)
        document_frequency: Counter[str] = Counter()
        for counts in candidate_counts:
            document_frequency.update(counts.keys())
        average_length = (
            sum(sum(counts.values()) for counts in candidate_counts)
            / document_count
            if document_count
            else 0.0
        )
        query_terms = set(tokenize(query.text))
        scored: list[tuple[RetrievalCandidate, float, dict[str, float]]] = []
        for candidate, counts in zip(query.candidates, candidate_counts):
            length = sum(counts.values())
            score = 0.0
            for term in query_terms:
                frequency = counts.get(term, 0)
                if not frequency:
                    continue
                frequency_in_documents = document_frequency[term]
                inverse_document_frequency = math.log(
                    1.0
                    + (
                        document_count - frequency_in_documents + 0.5
                    )
                    / (frequency_in_documents + 0.5)
                )
                length_ratio = length / average_length if average_length else 0.0
                denominator = frequency + self.k1 * (
                    1.0 - self.b + self.b * length_ratio
                )
                score += inverse_document_frequency * (
                    frequency * (self.k1 + 1.0) / denominator
                )
            scored.append((candidate, score, {"bm25": score}))
        return _rank_scored(query, self.name, scored)


class ExplicitLinkRanker:
    name = "explicit_link"

    def rank(self, query: RetrievalQuery) -> tuple[RankedCandidate, ...]:
        explicit_position = {
            candidate_id: position
            for position, candidate_id in enumerate(query.explicit_target_ids)
        }
        explicit_count = len(explicit_position)
        return _rank_scored(
            query,
            self.name,
            (
                (
                    candidate,
                    (
                        float(explicit_count - explicit_position[candidate.candidate_id])
                        if candidate.candidate_id in explicit_position
                        else 0.0
                    ),
                    {
                        "is_explicit_link": float(
                            candidate.candidate_id in explicit_position
                        )
                    },
                )
                for candidate in query.candidates
            ),
        )


class HashedEmbeddingRanker:
    """A dependency-free hashed lexical projection, not a neural embedding."""

    name = "hashed_embedding"

    def __init__(self, *, dimensions: int = 512, seed: int = 1729) -> None:
        if isinstance(dimensions, bool) or not isinstance(dimensions, int):
            raise ValueError("embedding dimensions must be an integer")
        if dimensions <= 0:
            raise ValueError("embedding dimensions must be positive")
        self.dimensions = dimensions
        self.seed = seed

    def _features(self, text: str) -> tuple[str, ...]:
        terms = tokenize(text)
        bigrams = tuple(
            f"{left}\u241f{right}" for left, right in zip(terms, terms[1:])
        )
        return terms + bigrams

    @lru_cache(maxsize=512)
    def _vector(self, text: str) -> dict[int, float]:
        vector: dict[int, float] = {}
        for feature, count in Counter(self._features(text)).items():
            digest = zlib.crc32(
                feature.encode("utf-8"), self.seed & 0xFFFFFFFF
            )
            bucket = digest % self.dimensions
            sign = 1.0 if digest & 0x80000000 else -1.0
            vector[bucket] = vector.get(bucket, 0.0) + sign * count
        norm = math.sqrt(sum(value * value for value in vector.values()))
        if norm:
            return {index: value / norm for index, value in vector.items()}
        return {}

    def rank(self, query: RetrievalQuery) -> tuple[RankedCandidate, ...]:
        query_vector = self._vector(query.text)
        scored: list[tuple[RetrievalCandidate, float, dict[str, float]]] = []
        for candidate in query.candidates:
            vector = self._vector(candidate.text)
            cosine = sum(
                query_value * vector.get(index, 0.0)
                for index, query_value in query_vector.items()
            )
            scored.append(
                (candidate, cosine, {"hashed_embedding_cosine": cosine})
            )
        return _rank_scored(query, self.name, scored)


class ReciprocalRankFusionRanker:
    name = "rrf_hybrid"

    def __init__(self, rankers: tuple[Ranker, ...], *, rrf_k: int = 60) -> None:
        if len(rankers) < 2:
            raise ValueError("RRF requires at least two rankers")
        names = [ranker.name for ranker in rankers]
        if len(names) != len(set(names)):
            raise ValueError("RRF channel names must be unique")
        if isinstance(rrf_k, bool) or not isinstance(rrf_k, int) or rrf_k <= 0:
            raise ValueError("RRF k must be a positive integer")
        self.rankers = rankers
        self.rrf_k = rrf_k

    def rank(self, query: RetrievalQuery) -> tuple[RankedCandidate, ...]:
        by_channel = {
            ranker.name: ranker.rank(query) for ranker in self.rankers
        }
        return self.fuse(query, by_channel)

    def fuse(
        self,
        query: RetrievalQuery,
        by_channel: dict[str, tuple[RankedCandidate, ...]],
    ) -> tuple[RankedCandidate, ...]:
        expected = {ranker.name for ranker in self.rankers}
        if set(by_channel) != expected:
            raise ValueError(
                "RRF supplied channels differ; "
                f"expected={sorted(expected)}, got={sorted(by_channel)}"
            )
        rank_lookup = {
            channel: {
                item.candidate_id: item.rank for item in rankings
            }
            for channel, rankings in by_channel.items()
        }
        scored: list[tuple[RetrievalCandidate, float, dict[str, float]]] = []
        for candidate in query.candidates:
            signals = {
                f"rrf_{channel}": 1.0
                / (self.rrf_k + ranks[candidate.candidate_id])
                for channel, ranks in rank_lookup.items()
            }
            scored.append((candidate, sum(signals.values()), signals))
        return _rank_scored(query, self.name, scored)


def dataset_queries(dataset: Dataset) -> tuple[RetrievalQuery, ...]:
    queries: list[RetrievalQuery] = []
    for source_index, source in enumerate(dataset.thoughts):
        candidates = tuple(
            RetrievalCandidate(
                candidate_id=target.id,
                native_id=target.id,
                text=target.text,
                order=target_index,
                timestamp=target.created_at,
                contexts=target.contexts,
            )
            for target_index, target in enumerate(
                dataset.thoughts[:source_index]
            )
        )
        queries.append(
            RetrievalQuery(
                query_id=source.id,
                text=source.text,
                candidates=candidates,
                explicit_target_ids=source.explicit_links,
                contexts=source.contexts,
            )
        )
    return tuple(queries)


def rank_dataset(dataset: Dataset, ranker: Ranker) -> tuple[Prediction, ...]:
    predictions: list[Prediction] = []
    for query in dataset_queries(dataset):
        predictions.extend(
            Prediction(
                source_id=item.query_id,
                target_id=item.candidate_id,
                rank=item.rank,
                score=item.score,
                signals=item.signals,
                method=item.method,
                confidence=None,
                abstained=False,
            )
            for item in ranker.rank(query)
        )
    return tuple(predictions)
