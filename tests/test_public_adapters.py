from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from intuition_map_data.adapters.atomic2020 import (
    iter_atomic2020_archive,
    iter_atomic2020_tsv,
    validate_atomic2020_archive,
)
from intuition_map_data.adapters.longmemeval import (
    LongMemEvalRecord,
    iter_longmemeval,
)
from intuition_map_data.adapters.personalllm import iter_personalllm_jsonl


FIXTURES = Path(__file__).parent / "fixtures" / "public"


class PublicAdapterTests(unittest.TestCase):
    def test_longmemeval_preserves_native_question_and_evidence(self) -> None:
        records = tuple(iter_longmemeval(FIXTURES / "longmemeval-mini.json"))
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record.question_type, "knowledge-update")
        self.assertEqual(record.answer, "The blue notebook")
        self.assertEqual(
            [session.session_id for session in record.evidence_sessions],
            ["fixture-session-2"],
        )
        self.assertTrue(record.evidence_sessions[0].turns[0].has_answer)

    def test_longmemeval_preserves_numeric_counting_answers(self) -> None:
        values = json.loads(
            (FIXTURES / "longmemeval-mini.json").read_text(encoding="utf-8")
        )
        values[0]["answer"] = 3
        record = LongMemEvalRecord.from_dict(values[0])
        self.assertEqual(record.answer, 3)

    def test_longmemeval_does_not_invent_missing_turn_evidence_flags(self) -> None:
        values = json.loads(
            (FIXTURES / "longmemeval-mini.json").read_text(encoding="utf-8")
        )
        del values[0]["haystack_sessions"][0][0]["has_answer"]
        record = LongMemEvalRecord.from_dict(values[0])
        self.assertIsNone(record.sessions[0].turns[0].has_answer)

    def test_longmemeval_disambiguates_colliding_native_session_ids(self) -> None:
        values = json.loads(
            (FIXTURES / "longmemeval-mini.json").read_text(encoding="utf-8")
        )
        values[0]["haystack_session_ids"][1] = "fixture-session-1"
        values[0]["answer_session_ids"] = []
        record = LongMemEvalRecord.from_dict(values[0])
        self.assertEqual(record.sessions[0].session_id, record.sessions[1].session_id)
        self.assertNotEqual(
            record.sessions[0].candidate_id,
            record.sessions[1].candidate_id,
        )

    def test_longmemeval_preserves_an_empty_native_turn(self) -> None:
        values = json.loads(
            (FIXTURES / "longmemeval-mini.json").read_text(encoding="utf-8")
        )
        values[0]["haystack_sessions"][0][0]["content"] = ""
        record = LongMemEvalRecord.from_dict(values[0])
        self.assertTrue(record.sessions[0].turns[0].is_empty)

    def test_personalllm_preserves_candidates_profiles_and_native_ids(self) -> None:
        records = tuple(iter_personalllm_jsonl(FIXTURES / "personalllm-mini.jsonl"))
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record.prompt_id, 101)
        self.assertEqual(len(record.candidates), 8)
        self.assertEqual(set(record.rewards), {"profile_alpha", "profile_beta"})
        self.assertEqual(record.preferred_candidate("profile_alpha").text, "Holl")
        self.assertEqual(record.preferred_candidate("profile_beta").text, "Aster")

    def test_atomic2020_preserves_native_direction_and_split(self) -> None:
        triples = tuple(
            iter_atomic2020_tsv(FIXTURES / "atomic2020-test.tsv", split="test")
        )
        self.assertEqual(len(triples), 3)
        self.assertEqual(triples[0].relation, "xIntent")
        self.assertEqual(triples[0].split, "test")
        self.assertEqual(
            (triples[2].head, triples[2].tail),
            (
                "PersonX finds a paper map",
                "PersonX opens a fictional drawer",
            ),
        )

    def test_atomic2020_marks_an_incomplete_native_tail(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "train.tsv"
            path.write_text("head\trelation\t\n", encoding="utf-8")
            triple = tuple(iter_atomic2020_tsv(path, split="train"))[0]
            self.assertEqual(triple.tail, "")
            self.assertFalse(triple.is_complete)

    def test_atomic2020_archive_requires_native_files_and_license(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive_path = Path(temporary) / "atomic.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr(
                    "atomic2020_data-feb2021/LICENSE",
                    "Attribution 4.0 International\n",
                )
                archive.writestr(
                    "atomic2020_data-feb2021/README.md",
                    "Synthetic archive fixture\n",
                )
                for split in ("train", "dev", "test"):
                    archive.writestr(
                        f"atomic2020_data-feb2021/{split}.tsv",
                        "head\trelation\ttail\n",
                    )
            summary = validate_atomic2020_archive(archive_path)
            self.assertEqual(summary["license_heading"], "Attribution 4.0 International")
            triples = tuple(iter_atomic2020_archive(archive_path, split="dev"))
            self.assertEqual(triples[0].split, "dev")


if __name__ == "__main__":
    unittest.main()
