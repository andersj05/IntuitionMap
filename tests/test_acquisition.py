from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from urllib.request import Request

from intuition_map_data.acquisition import (
    acquire_artifact,
    load_public_dataset_spec,
    resolve_artifact_destination,
)


class _Response(io.BytesIO):
    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


class AcquisitionTests(unittest.TestCase):
    def test_registered_manifests_are_valid_and_bounded(self) -> None:
        manifest_root = Path(__file__).parents[1] / "configs" / "data"
        paths = sorted(manifest_root.glob("*.json"))
        self.assertEqual(len(paths), 3)
        specs = [load_public_dataset_spec(path) for path in paths]
        self.assertEqual(
            {spec.registry_id for spec in specs},
            {"LME-001", "PLLM-001", "ATOMIC-001"},
        )
        self.assertLessEqual(
            sum(spec.registered_download_bytes for spec in specs),
            50_000_000,
        )
        with tempfile.TemporaryDirectory() as temporary:
            for spec in specs:
                for artifact in spec.artifacts:
                    destination = resolve_artifact_destination(
                        temporary, artifact.destination
                    )
                    self.assertIn(Path(temporary).resolve(), destination.parents)

    def test_destination_cannot_escape_artifact_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            for destination in ("../escape", "nested/../../escape"):
                with self.subTest(destination=destination):
                    with self.assertRaisesRegex(ValueError, "unsafe"):
                        resolve_artifact_destination(temporary, destination)

    def test_acquire_verifies_then_reuses_exact_artifact(self) -> None:
        payload = b"registered public fixture"
        sha256 = hashlib.sha256(payload).hexdigest()
        manifest = {
            "schema_version": "0.1.0",
            "registry_id": "TEST-001",
            "name": "test",
            "upstream_revision": "immutable",
            "artifacts": [
                {
                    "path": "fixture.bin",
                    "destination": "test/fixture.bin",
                    "url": "https://example.invalid/fixture.bin",
                    "size_bytes": len(payload),
                    "sha256": sha256,
                    "role": "test",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            spec = load_public_dataset_spec(manifest_path)
            calls: list[Request] = []

            def open_url(request: Request) -> _Response:
                calls.append(request)
                return _Response(payload)

            first = acquire_artifact(spec.artifacts[0], root / "external", open_url=open_url)
            second = acquire_artifact(spec.artifacts[0], root / "external", open_url=open_url)
            self.assertEqual(first["status"], "downloaded")
            self.assertEqual(second["status"], "verified-existing")
            self.assertEqual(len(calls), 1)

    def test_corrupt_download_is_not_promoted(self) -> None:
        expected = b"expected"
        corrupt = b"corrupt!"
        manifest = {
            "schema_version": "0.1.0",
            "registry_id": "TEST-002",
            "name": "corrupt test",
            "upstream_revision": "immutable",
            "artifacts": [
                {
                    "path": "fixture.bin",
                    "destination": "test/fixture.bin",
                    "url": "https://example.invalid/fixture.bin",
                    "size_bytes": len(expected),
                    "sha256": hashlib.sha256(expected).hexdigest(),
                    "role": "test",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            artifact = load_public_dataset_spec(manifest_path).artifacts[0]
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                acquire_artifact(
                    artifact,
                    root / "external",
                    open_url=lambda request: _Response(corrupt),
                )
            destination = root / "external" / "test" / "fixture.bin"
            self.assertFalse(destination.exists())
            self.assertFalse(destination.with_name("fixture.bin.part").exists())


if __name__ == "__main__":
    unittest.main()
