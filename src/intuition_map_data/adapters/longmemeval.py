from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _string_tuple(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    return tuple(_string(item, field) for item in value)


def _native_answer(value: Any) -> str | int:
    if isinstance(value, bool):
        raise ValueError("answer must be a non-empty string or integer")
    if isinstance(value, int):
        return value
    return _string(value, "answer")


@dataclass(frozen=True, slots=True)
class LongMemEvalTurn:
    role: str
    content: str
    has_answer: bool

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LongMemEvalTurn:
        expected = {"role", "content", "has_answer"}
        if data.keys() != expected:
            raise ValueError(
                f"turn fields must be exactly {sorted(expected)}, got {sorted(data)}"
            )
        role = _string(data["role"], "turn.role")
        if role not in {"user", "assistant"}:
            raise ValueError("turn.role must be user or assistant")
        if not isinstance(data["has_answer"], bool):
            raise ValueError("turn.has_answer must be a boolean")
        return cls(
            role=role,
            content=_string(data["content"], "turn.content"),
            has_answer=data["has_answer"],
        )


@dataclass(frozen=True, slots=True)
class LongMemEvalSession:
    session_id: str
    date: str
    turns: tuple[LongMemEvalTurn, ...]


@dataclass(frozen=True, slots=True)
class LongMemEvalRecord:
    question_id: str
    question_type: str
    question: str
    answer: str | int
    question_date: str
    sessions: tuple[LongMemEvalSession, ...]
    answer_session_ids: tuple[str, ...]

    @property
    def evidence_sessions(self) -> tuple[LongMemEvalSession, ...]:
        evidence = set(self.answer_session_ids)
        return tuple(
            session for session in self.sessions if session.session_id in evidence
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LongMemEvalRecord:
        expected = {
            "question_id",
            "question_type",
            "question",
            "answer",
            "question_date",
            "haystack_dates",
            "haystack_session_ids",
            "haystack_sessions",
            "answer_session_ids",
        }
        if data.keys() != expected:
            missing = expected - data.keys()
            unknown = data.keys() - expected
            raise ValueError(
                f"LongMemEval record fields differ; missing={sorted(missing)}, "
                f"unknown={sorted(unknown)}"
            )
        dates = _string_tuple(data["haystack_dates"], "haystack_dates")
        session_ids = _string_tuple(
            data["haystack_session_ids"], "haystack_session_ids"
        )
        raw_sessions = data["haystack_sessions"]
        if not isinstance(raw_sessions, list):
            raise ValueError("haystack_sessions must be a list")
        if not (len(dates) == len(session_ids) == len(raw_sessions)):
            raise ValueError(
                "haystack_dates, haystack_session_ids, and haystack_sessions "
                "must have equal lengths"
            )
        if len(session_ids) != len(set(session_ids)):
            raise ValueError("haystack_session_ids must be unique")
        sessions: list[LongMemEvalSession] = []
        for index, raw_session in enumerate(raw_sessions):
            if not isinstance(raw_session, list) or not raw_session:
                raise ValueError(f"haystack_sessions[{index}] must be non-empty")
            turns: list[LongMemEvalTurn] = []
            for raw_turn in raw_session:
                if not isinstance(raw_turn, dict):
                    raise ValueError("LongMemEval turns must be objects")
                turns.append(LongMemEvalTurn.from_dict(raw_turn))
            sessions.append(
                LongMemEvalSession(
                    session_id=session_ids[index],
                    date=dates[index],
                    turns=tuple(turns),
                )
            )
        answer_session_ids = _string_tuple(
            data["answer_session_ids"], "answer_session_ids"
        )
        unknown_evidence = set(answer_session_ids) - set(session_ids)
        if unknown_evidence:
            raise ValueError(
                f"answer_session_ids not present in haystack: {sorted(unknown_evidence)}"
            )
        return cls(
            question_id=_string(data["question_id"], "question_id"),
            question_type=_string(data["question_type"], "question_type"),
            question=_string(data["question"], "question"),
            answer=_native_answer(data["answer"]),
            question_date=_string(data["question_date"], "question_date"),
            sessions=tuple(sessions),
            answer_session_ids=answer_session_ids,
        )


def iter_longmemeval(path: str | Path) -> Iterable[LongMemEvalRecord]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{Path(path).name}:{exc.lineno}: invalid JSON: {exc.msg}"
        ) from exc
    if not isinstance(data, list):
        raise ValueError("LongMemEval artifact must contain a JSON list")
    seen_ids: set[str] = set()
    for index, value in enumerate(data):
        if not isinstance(value, dict):
            raise ValueError(f"LongMemEval record {index} must be an object")
        try:
            record = LongMemEvalRecord.from_dict(value)
        except ValueError as exc:
            raise ValueError(f"LongMemEval record {index}: {exc}") from exc
        if record.question_id in seen_ids:
            raise ValueError(f"duplicate LongMemEval question_id: {record.question_id}")
        seen_ids.add(record.question_id)
        yield record
