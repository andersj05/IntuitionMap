from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path

from intuition_map_private.annotations import (
    create_blind_repeats,
    create_discovery_queue,
    create_standard_proposal_queue,
    export_annotation_batch,
    import_annotation_responses,
)
from intuition_map_private.burden import pilot_burden_summary
from intuition_map_private.cli import main as private_cli
from intuition_map_private.exporting import export_participant_bundle
from intuition_map_private.importer import import_jsonl
from intuition_map_private.policy import (
    REQUIRED_ACKNOWLEDGEMENTS,
    ConsentReceipt,
)
from intuition_map_private.protected import (
    freeze_chronological_test_manifest,
)
from intuition_map_private.store import PrivateWorkspace

FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "private"
    / "synthetic-thoughts.jsonl"
)
PARTICIPANT = "synthetic-participant"


class PrivateWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.workspace = PrivateWorkspace.initialize(
            Path(self.temporary.name) / "private-workspace"
        )

    def grant_consent(
        self,
        *,
        allow_training: bool = True,
        store_raw: bool = True,
    ) -> ConsentReceipt:
        receipt = ConsentReceipt.create(
            participant_id=PARTICIPANT,
            purposes=(
                "local_retrieval_research",
                "annotation_pilot",
            ),
            source_types=("synthetic_note",),
            retention_days=36_500,
            acknowledgements=tuple(sorted(REQUIRED_ACKNOWLEDGEMENTS)),
            allow_training_use=allow_training,
            store_raw_content=store_raw,
            granted_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            consent_id="consent_synthetic",
        )
        self.workspace.add_consent(receipt)
        return receipt

    def test_workspace_inside_git_requires_the_ignored_private_path(
        self,
    ) -> None:
        repository = Path(self.temporary.name) / "fake-repository"
        (repository / ".git").mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, "ignored path"):
            PrivateWorkspace.initialize(repository / "unsafe-private")
        safe = PrivateWorkspace.initialize(
            repository / "datasets" / "private" / "pilot"
        )
        self.assertTrue(safe.database_path.is_file())

    def test_cli_round_trip_outputs_metadata_not_private_content(self) -> None:
        cli_workspace = Path(self.temporary.name) / "cli-workspace"
        commands = [
            ["init", "--workspace", str(cli_workspace)],
            [
                "grant-consent",
                "--workspace",
                str(cli_workspace),
                "--participant",
                "cli-synthetic",
                "--source-type",
                "synthetic_note",
                "--purpose",
                "local_retrieval_research",
                "--purpose",
                "annotation_pilot",
                "--retention-days",
                "365",
                "--redacted-view-only",
                "--allow-derived-features",
                "--ack-ownership",
                "--ack-sensitive-data",
                "--ack-deletion-limits",
                "--ack-no-app-encryption",
            ],
            [
                "import-jsonl",
                "--workspace",
                str(cli_workspace),
                "--participant",
                "cli-synthetic",
                "--input",
                str(FIXTURE),
            ],
            [
                "freeze-test",
                "--workspace",
                str(cli_workspace),
                "--participant",
                "cli-synthetic",
            ],
        ]
        output = io.StringIO()
        with redirect_stdout(output):
            for command in commands:
                self.assertEqual(private_cli(command), 0)
        serialized = output.getvalue()
        self.assertNotIn("PRIVATE_CANARY_9f13", serialized)
        self.assertNotIn("alice@example.invalid", serialized)

    def imported_workspace(self) -> None:
        self.grant_consent()
        result = import_jsonl(
            self.workspace,
            participant_id=PARTICIPANT,
            path=FIXTURE,
        )
        self.assertEqual(result["inserted_count"], 10)

    def thought_id(self, source_id: str) -> str:
        with self.workspace.connect() as connection:
            row = connection.execute(
                """
                SELECT thought_id FROM thoughts
                WHERE participant_id=? AND source_id=?
                """,
                (PARTICIPANT, source_id),
            ).fetchone()
        self.assertIsNotNone(row)
        return row["thought_id"]

    def freeze(self) -> dict[str, object]:
        return freeze_chronological_test_manifest(
            self.workspace,
            participant_id=PARTICIPANT,
            test_fraction=0.20,
            minimum_test_queries=2,
        )

    def respond_to_discovery(
        self,
        *,
        source_id: str = "n008",
        discovered_source_id: str = "n003",
    ) -> tuple[str, str]:
        source_thought = self.thought_id(source_id)
        result = create_discovery_queue(
            self.workspace,
            participant_id=PARTICIPANT,
            source_thought_ids=[source_thought],
        )
        item_id = result["item_ids"][0]
        export_annotation_batch(
            self.workspace,
            participant_id=PARTICIPANT,
            stream="discovery",
            output_path="batches/discovery.json",
        )
        response_path = self.workspace.managed_path(
            "responses/discovery.jsonl"
        )
        response_path.parent.mkdir(parents=True, exist_ok=True)
        response_path.write_text(
            json.dumps(
                {
                    "item_id": item_id,
                    "response_ms": 4200,
                    "skipped": False,
                    "submitted_at": "2026-03-10T12:00:00Z",
                    "discovered_target_ids": [
                        self.thought_id(discovered_source_id)
                    ],
                    "relation_types": ["resembles"],
                    "rationale": None,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        import_annotation_responses(
            self.workspace,
            participant_id=PARTICIPANT,
            response_path=response_path,
        )
        return source_thought, item_id

    def test_import_requires_explicit_active_consent(self) -> None:
        with self.assertRaisesRegex(ValueError, "no active consent"):
            import_jsonl(
                self.workspace,
                participant_id=PARTICIPANT,
                path=FIXTURE,
            )

        with self.assertRaisesRegex(
            ValueError, "missing required acknowledgements"
        ):
            ConsentReceipt.create(
                participant_id=PARTICIPANT,
                purposes=("local_retrieval_research",),
                source_types=("synthetic_note",),
                retention_days=30,
                acknowledgements=(),
            )

    def test_expired_consent_blocks_new_processing(self) -> None:
        receipt = ConsentReceipt.create(
            participant_id=PARTICIPANT,
            purposes=("local_retrieval_research",),
            source_types=("synthetic_note",),
            retention_days=1,
            acknowledgements=tuple(sorted(REQUIRED_ACKNOWLEDGEMENTS)),
            granted_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
            consent_id="consent_expired",
        )
        self.workspace.add_consent(receipt)
        with self.assertRaisesRegex(ValueError, "no active consent"):
            import_jsonl(
                self.workspace,
                participant_id=PARTICIPANT,
                path=FIXTURE,
            )

    def test_import_is_immutable_idempotent_and_separates_weak_labels(
        self,
    ) -> None:
        self.imported_workspace()
        second = import_jsonl(
            self.workspace,
            participant_id=PARTICIPANT,
            path=FIXTURE,
        )
        self.assertEqual(second["inserted_count"], 0)
        self.assertEqual(second["reused_count"], 10)
        with self.workspace.connect() as connection:
            weak_count = connection.execute(
                "SELECT COUNT(*) AS count FROM weak_labels"
            ).fetchone()["count"]
            gold_count = connection.execute(
                "SELECT COUNT(*) AS count FROM gold_judgments"
            ).fetchone()["count"]
            redacted = connection.execute(
                "SELECT raw_text, redacted_text FROM thoughts WHERE source_id='n002'"
            ).fetchone()
        self.assertEqual(weak_count, 2)
        self.assertEqual(gold_count, 0)
        self.assertIn("alice@example.invalid", redacted["raw_text"])
        self.assertNotIn("alice@example.invalid", redacted["redacted_text"])
        self.assertIn("<REDACTED:EMAIL>", redacted["redacted_text"])

        changed = self.workspace.managed_path("imports/changed.jsonl")
        changed.parent.mkdir(parents=True, exist_ok=True)
        records = FIXTURE.read_text(encoding="utf-8").splitlines()
        value = json.loads(records[0])
        value["text"] = "Changed in place."
        records[0] = json.dumps(value)
        changed.write_text("\n".join(records) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(
            ValueError, "immutable source version changed"
        ):
            import_jsonl(
                self.workspace,
                participant_id=PARTICIPANT,
                path=changed,
            )

    def test_protected_manifest_is_sealed_and_blocks_later_import(
        self,
    ) -> None:
        self.imported_workspace()
        result = self.freeze()
        self.assertEqual(result["protected_test_query_count"], 2)
        self.assertTrue(result["sealed"])
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.freeze()
        with self.assertRaisesRegex(ValueError, "imports are frozen"):
            import_jsonl(
                self.workspace,
                participant_id=PARTICIPANT,
                path=FIXTURE,
            )

    def test_discovery_precedes_proposals_and_streams_remain_separate(
        self,
    ) -> None:
        self.imported_workspace()
        self.freeze()
        source = self.thought_id("n008")
        with self.assertRaisesRegex(
            ValueError, "discovery response is required"
        ):
            create_standard_proposal_queue(
                self.workspace,
                participant_id=PARTICIPANT,
                source_thought_id=source,
            )
        source, _ = self.respond_to_discovery()
        proposals = create_standard_proposal_queue(
            self.workspace,
            participant_id=PARTICIPANT,
            source_thought_id=source,
        )
        self.assertLessEqual(proposals["created_count"], 5)
        self.assertGreater(proposals["created_count"], 0)
        self.assertFalse(proposals["selection_details_exposed"])
        self.assertNotIn("items", proposals)
        batch = export_annotation_batch(
            self.workspace,
            participant_id=PARTICIPANT,
            stream="proposal",
            output_path="batches/proposals.json",
        )
        payload = json.loads(Path(batch["path"]).read_text(encoding="utf-8"))
        self.assertTrue(
            all("sampling_source" not in item for item in payload["items"])
        )
        self.assertTrue(
            all("repeat_of" not in item for item in payload["items"])
        )
        with self.workspace.connect() as connection:
            streams = {
                row["stream"]
                for row in connection.execute(
                    "SELECT stream FROM gold_judgments"
                )
            }
        self.assertEqual(streams, {"discovery"})

    def test_discovery_rejects_a_future_target(self) -> None:
        self.imported_workspace()
        self.freeze()
        source = self.thought_id("n005")
        item_id = create_discovery_queue(
            self.workspace,
            participant_id=PARTICIPANT,
            source_thought_ids=[source],
        )["item_ids"][0]
        export_annotation_batch(
            self.workspace,
            participant_id=PARTICIPANT,
            stream="discovery",
            output_path="batches/discovery-future.json",
        )
        response_path = self.workspace.managed_path(
            "responses/discovery-future.jsonl"
        )
        response_path.parent.mkdir(parents=True, exist_ok=True)
        response_path.write_text(
            json.dumps(
                {
                    "item_id": item_id,
                    "response_ms": 1000,
                    "skipped": False,
                    "submitted_at": "2026-03-10T12:00:00Z",
                    "discovered_target_ids": [self.thought_id("n010")],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "temporal leakage"):
            import_annotation_responses(
                self.workspace,
                participant_id=PARTICIPANT,
                response_path=response_path,
            )

    def test_response_cannot_be_overwritten_and_repeat_is_blind(self) -> None:
        self.imported_workspace()
        self.freeze()
        source, _ = self.respond_to_discovery()
        create_standard_proposal_queue(
            self.workspace,
            participant_id=PARTICIPANT,
            source_thought_id=source,
        )
        batch = export_annotation_batch(
            self.workspace,
            participant_id=PARTICIPANT,
            stream="proposal",
            output_path="batches/proposals.json",
            limit=1,
        )
        item = json.loads(Path(batch["path"]).read_text(encoding="utf-8"))[
            "items"
        ][0]
        response_path = self.workspace.managed_path(
            "responses/proposal.jsonl"
        )
        response_path.parent.mkdir(parents=True, exist_ok=True)
        response = {
            "item_id": item["item_id"],
            "response_ms": 3200,
            "skipped": False,
            "submitted_at": "2026-03-10T12:00:00Z",
            "verdict": "valid",
            "relation_types": [],
            "rationale": None,
        }
        response_path.write_text(
            json.dumps(response) + "\n", encoding="utf-8"
        )
        import_annotation_responses(
            self.workspace,
            participant_id=PARTICIPANT,
            response_path=response_path,
        )
        duplicate_path = self.workspace.managed_path(
            "responses/proposal-duplicate.jsonl"
        )
        duplicate_path.write_text(
            json.dumps(response) + "\n", encoding="utf-8"
        )
        with self.assertRaisesRegex(ValueError, "cannot be overwritten"):
            import_annotation_responses(
                self.workspace,
                participant_id=PARTICIPANT,
                response_path=duplicate_path,
            )

        repeats = create_blind_repeats(
            self.workspace,
            participant_id=PARTICIPANT,
            rate=0.10,
            minimum_delay_days=7,
            now=datetime(2026, 3, 20, tzinfo=timezone.utc),
        )
        self.assertEqual(repeats["created_count"], 1)
        repeat_batch = export_annotation_batch(
            self.workspace,
            participant_id=PARTICIPANT,
            stream="proposal",
            output_path="batches/repeat.json",
        )
        serialized = Path(repeat_batch["path"]).read_text(encoding="utf-8")
        self.assertNotIn("blind_repeat", serialized)
        self.assertNotIn("repeat_of", serialized)

    def test_default_export_is_redacted_and_training_excludes_test(
        self,
    ) -> None:
        self.imported_workspace()
        frozen = self.freeze()
        redacted = export_participant_bundle(
            self.workspace,
            participant_id=PARTICIPANT,
            output_path="exports/redacted.json",
        )
        redacted_text = Path(redacted["path"]).read_text(encoding="utf-8")
        self.assertNotIn("alice@example.invalid", redacted_text)
        self.assertIn("<REDACTED:EMAIL>", redacted_text)

        raw = export_participant_bundle(
            self.workspace,
            participant_id=PARTICIPANT,
            output_path="exports/raw.json",
            include_raw=True,
        )
        self.assertIn(
            "alice@example.invalid",
            Path(raw["path"]).read_text(encoding="utf-8"),
        )
        training = export_participant_bundle(
            self.workspace,
            participant_id=PARTICIPANT,
            output_path="exports/training.json",
            purpose="training",
        )
        training_payload = json.loads(
            Path(training["path"]).read_text(encoding="utf-8")
        )
        self.assertEqual(len(training_payload["thoughts"]), 8)
        self.assertTrue(training_payload["privacy"]["protected_test_excluded"])
        self.assertEqual(
            training_payload["protected_manifest_sha256"],
            frozen["definition_sha256"],
        )
        outside = Path(self.temporary.name) / "outside.json"
        with self.assertRaisesRegex(ValueError, "inside"):
            export_participant_bundle(
                self.workspace,
                participant_id=PARTICIPANT,
                output_path=outside,
            )

    def test_raw_export_and_training_require_explicit_consent(self) -> None:
        self.grant_consent(allow_training=False, store_raw=False)
        import_jsonl(
            self.workspace,
            participant_id=PARTICIPANT,
            path=FIXTURE,
        )
        self.freeze()
        with self.assertRaisesRegex(ValueError, "did not store exact raw"):
            export_participant_bundle(
                self.workspace,
                participant_id=PARTICIPANT,
                output_path="exports/raw-unavailable.json",
                include_raw=True,
            )
        with self.assertRaisesRegex(ValueError, "training use"):
            export_participant_bundle(
                self.workspace,
                participant_id=PARTICIPANT,
                output_path="exports/training-not-consented.json",
                purpose="training",
            )

    def test_revocation_blocks_processing_without_silently_deleting(
        self,
    ) -> None:
        receipt = self.grant_consent()
        import_jsonl(
            self.workspace,
            participant_id=PARTICIPANT,
            path=FIXTURE,
        )
        self.workspace.revoke_consent(
            receipt.consent_id,
            reason="Synthetic withdrawal test",
        )
        with self.assertRaisesRegex(ValueError, "no active consent"):
            import_jsonl(
                self.workspace,
                participant_id=PARTICIPANT,
                path=FIXTURE,
            )
        with self.workspace.connect() as connection:
            count = connection.execute(
                "SELECT COUNT(*) AS count FROM thoughts"
            ).fetchone()["count"]
        self.assertEqual(count, 10)

    def test_delete_propagates_to_rows_and_managed_exports(self) -> None:
        self.imported_workspace()
        self.freeze()
        self.respond_to_discovery()
        export = export_participant_bundle(
            self.workspace,
            participant_id=PARTICIPANT,
            output_path="exports/portable.json",
            include_raw=True,
        )
        export_path = Path(export["path"])
        self.assertTrue(export_path.is_file())
        with self.workspace.connect() as connection:
            managed_paths = [
                Path(row["path"])
                for row in connection.execute(
                    "SELECT path FROM exports WHERE participant_id=?",
                    (PARTICIPANT,),
                )
            ]
        self.assertGreaterEqual(len(managed_paths), 3)
        self.assertTrue(all(path.is_file() for path in managed_paths))
        receipt = self.workspace.delete_participant(PARTICIPANT)
        self.assertTrue(all(not path.exists() for path in managed_paths))
        self.assertFalse(receipt["original_sources_and_backups_deleted"])
        with self.workspace.connect() as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) AS count FROM participants"
                ).fetchone()["count"],
                0,
            )
        database_bytes = self.workspace.database_path.read_bytes()
        self.assertNotIn(b"PRIVATE_CANARY_9f13", database_bytes)
        self.assertNotIn(b"alice@example.invalid", database_bytes)

    def test_pilot_summary_cannot_self_certify_g3(self) -> None:
        self.imported_workspace()
        self.freeze()
        summary = pilot_burden_summary(
            self.workspace,
            participant_id=PARTICIPANT,
        )
        self.assertFalse(summary["g3_pass"])
        self.assertFalse(summary["all_burden_requirements_pass"])
        self.assertIn("verdict_distribution", summary)
        self.assertIn("responses_by_sampling_source", summary)


if __name__ == "__main__":
    unittest.main()
