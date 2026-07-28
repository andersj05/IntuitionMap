from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from intuition_map_eval.dataset import (
    DATASET_FILES,
    dataset_fingerprint,
    load_dataset,
)
from intuition_map_eval.fingerprint import canonical_text_sha256

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class DatasetTests(unittest.TestCase):
    def _write_dataset(
        self,
        root: Path,
        thoughts: list[dict[str, object]],
        judgments: list[dict[str, object]],
    ) -> None:
        (root / "manifest.json").write_text(
            json.dumps(
                {
                    "schema_version": "0.1.0",
                    "name": "test-dataset",
                    "description": "Dataset validation fixture.",
                    "provenance": "test",
                    "contains_personal_data": False,
                    "annotation": {
                        "candidate_pool": "all_prior_thoughts",
                        "exhaustive": False,
                        "unlabeled_pairs_are": "unknown",
                    },
                }
            ),
            encoding="utf-8",
        )
        (root / "thoughts.jsonl").write_text(
            "\n".join(json.dumps(value) for value in thoughts),
            encoding="utf-8",
        )
        (root / "judgments.jsonl").write_text(
            "\n".join(json.dumps(value) for value in judgments),
            encoding="utf-8",
        )

    def test_smoke_dataset_is_valid_and_stable(self) -> None:
        dataset = load_dataset(PROJECT_ROOT / "datasets" / "smoke")
        self.assertEqual(len(dataset.thoughts), 10)
        self.assertEqual(len(dataset.judgments), 15)
        self.assertEqual(len(dataset.fingerprint), 64)
        self.assertFalse(dataset.manifest.annotation.exhaustive)

    def test_future_target_is_rejected_as_temporal_leakage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "manifest.json").write_text(
                json.dumps(
                    {
                        "schema_version": "0.1.0",
                        "name": "bad-time",
                        "description": "Fixture with a future target.",
                        "provenance": "test",
                        "contains_personal_data": False,
                        "annotation": {
                            "candidate_pool": "all_prior_thoughts",
                            "exhaustive": False,
                            "unlabeled_pairs_are": "unknown",
                        },
                    }
                ),
                encoding="utf-8",
            )
            (root / "thoughts.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "id": "older",
                                "text": "Older thought",
                                "created_at": "2026-01-01T00:00:00Z",
                            }
                        ),
                        json.dumps(
                            {
                                "id": "newer",
                                "text": "Newer thought",
                                "created_at": "2026-01-02T00:00:00Z",
                            }
                        ),
                    ]
                ),
                encoding="utf-8",
            )
            (root / "judgments.jsonl").write_text(
                json.dumps(
                    {
                        "source_id": "older",
                        "target_id": "newer",
                        "verdict": "valid",
                        "relation_types": ["related"],
                        "strength": 0.5,
                        "rationale": "Invalid temporal direction.",
                        "annotator": "test",
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "temporal leakage"):
                load_dataset(root)

    def test_text_fingerprints_are_independent_of_checkout_line_endings(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            lf_root = root / "lf"
            crlf_root = root / "crlf"
            lf_root.mkdir()
            crlf_root.mkdir()

            for name in DATASET_FILES:
                source = PROJECT_ROOT / "datasets" / "smoke" / name
                canonical = source.read_bytes().replace(
                    b"\r\n", b"\n"
                ).replace(b"\r", b"\n")
                (lf_root / name).write_bytes(canonical)
                (crlf_root / name).write_bytes(
                    canonical.replace(b"\n", b"\r\n")
                )

            self.assertEqual(
                dataset_fingerprint(lf_root),
                dataset_fingerprint(crlf_root),
            )
            self.assertEqual(
                canonical_text_sha256(lf_root / "manifest.json"),
                canonical_text_sha256(crlf_root / "manifest.json"),
            )

    def test_unknown_or_future_explicit_links_are_rejected(self) -> None:
        base = [
            {
                "id": "older",
                "text": "Older thought",
                "created_at": "2026-01-01T00:00:00Z",
            },
            {
                "id": "newer",
                "text": "Newer thought",
                "created_at": "2026-01-02T00:00:00Z",
            },
        ]
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            unknown = [dict(value) for value in base]
            unknown[1]["explicit_links"] = ["missing"]
            self._write_dataset(root, unknown, [])
            with self.assertRaisesRegex(ValueError, "unknown explicit link"):
                load_dataset(root)

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            future = [dict(value) for value in base]
            future[0]["explicit_links"] = ["newer"]
            self._write_dataset(root, future, [])
            with self.assertRaisesRegex(
                ValueError, "explicit-link target.*must predate"
            ):
                load_dataset(root)

    def test_unknown_verdict_is_rejected(self) -> None:
        thoughts = [
            {
                "id": "older",
                "text": "Older thought",
                "created_at": "2026-01-01T00:00:00Z",
            },
            {
                "id": "newer",
                "text": "Newer thought",
                "created_at": "2026-01-02T00:00:00Z",
            },
        ]
        judgments = [
            {
                "source_id": "newer",
                "target_id": "older",
                "verdict": "unknown",
                "relation_types": [],
                "strength": 0.5,
                "rationale": "Unknown is not a verdict label.",
                "annotator": "test",
            }
        ]
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self._write_dataset(root, thoughts, judgments)
            with self.assertRaisesRegex(ValueError, "verdict must be one of"):
                load_dataset(root)


if __name__ == "__main__":
    unittest.main()
