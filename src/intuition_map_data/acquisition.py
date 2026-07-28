from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, Callable
from urllib.request import Request, urlopen

OpenUrl = Callable[[Request], BinaryIO]


def _non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _sha256_string(value: Any, field: str) -> str:
    result = _non_empty_string(value, field).lower()
    if len(result) != 64 or any(character not in "0123456789abcdef" for character in result):
        raise ValueError(f"{field} must be a lowercase SHA-256 hex digest")
    return result


def _positive_integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return value


@dataclass(frozen=True, slots=True)
class ArtifactSpec:
    path: str
    destination: str
    url: str
    size_bytes: int
    sha256: str
    role: str

    @classmethod
    def from_dict(cls, data: dict[str, Any], index: int) -> ArtifactSpec:
        required = {"path", "destination", "url", "size_bytes", "sha256", "role"}
        missing = required - data.keys()
        unknown = data.keys() - required
        if missing:
            raise ValueError(f"artifacts[{index}] missing fields: {sorted(missing)}")
        if unknown:
            raise ValueError(f"artifacts[{index}] unknown fields: {sorted(unknown)}")
        url = _non_empty_string(data["url"], f"artifacts[{index}].url")
        if not url.startswith("https://"):
            raise ValueError(f"artifacts[{index}].url must use HTTPS")
        return cls(
            path=_non_empty_string(data["path"], f"artifacts[{index}].path"),
            destination=_non_empty_string(
                data["destination"], f"artifacts[{index}].destination"
            ),
            url=url,
            size_bytes=_positive_integer(
                data["size_bytes"], f"artifacts[{index}].size_bytes"
            ),
            sha256=_sha256_string(data["sha256"], f"artifacts[{index}].sha256"),
            role=_non_empty_string(data["role"], f"artifacts[{index}].role"),
        )


@dataclass(frozen=True, slots=True)
class PublicDatasetSpec:
    manifest_path: Path
    registry_id: str
    name: str
    upstream_revision: str
    artifacts: tuple[ArtifactSpec, ...]
    raw: dict[str, Any]

    @property
    def registered_download_bytes(self) -> int:
        return sum(artifact.size_bytes for artifact in self.artifacts)


def load_public_dataset_spec(path: str | Path) -> PublicDatasetSpec:
    manifest_path = Path(path).resolve()
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"missing public-data manifest: {manifest_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{manifest_path.name}:{exc.lineno}: invalid JSON: {exc.msg}"
        ) from exc
    if not isinstance(data, dict):
        raise ValueError("public-data manifest must contain a JSON object")
    if data.get("schema_version") != "0.1.0":
        raise ValueError("unsupported public-data manifest schema_version")
    artifact_values = data.get("artifacts")
    if not isinstance(artifact_values, list) or not artifact_values:
        raise ValueError("artifacts must be a non-empty list")
    artifacts: list[ArtifactSpec] = []
    destinations: set[str] = set()
    for index, value in enumerate(artifact_values):
        if not isinstance(value, dict):
            raise ValueError(f"artifacts[{index}] must be an object")
        artifact = ArtifactSpec.from_dict(value, index)
        if artifact.destination in destinations:
            raise ValueError(f"duplicate artifact destination: {artifact.destination}")
        destinations.add(artifact.destination)
        artifacts.append(artifact)
    return PublicDatasetSpec(
        manifest_path=manifest_path,
        registry_id=_non_empty_string(data.get("registry_id"), "registry_id"),
        name=_non_empty_string(data.get("name"), "name"),
        upstream_revision=_non_empty_string(
            data.get("upstream_revision"), "upstream_revision"
        ),
        artifacts=tuple(artifacts),
        raw=data,
    )


def resolve_artifact_destination(root: str | Path, destination: str) -> Path:
    root_path = Path(root).resolve()
    relative = Path(destination)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise ValueError(f"unsafe artifact destination: {destination}")
    resolved = (root_path / relative).resolve()
    if resolved == root_path or root_path not in resolved.parents:
        raise ValueError(f"artifact destination escapes root: {destination}")
    return resolved


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_artifact(path: str | Path, artifact: ArtifactSpec) -> dict[str, Any]:
    artifact_path = Path(path)
    if not artifact_path.is_file():
        raise ValueError(f"missing artifact: {artifact_path}")
    size = artifact_path.stat().st_size
    if size != artifact.size_bytes:
        raise ValueError(
            f"size mismatch for {artifact.path}: expected {artifact.size_bytes}, got {size}"
        )
    digest = sha256_file(artifact_path)
    if digest != artifact.sha256:
        raise ValueError(
            f"SHA-256 mismatch for {artifact.path}: expected {artifact.sha256}, got {digest}"
        )
    return {
        "path": str(artifact_path),
        "size_bytes": size,
        "sha256": digest,
        "role": artifact.role,
        "verified": True,
    }


def _default_open(request: Request) -> BinaryIO:
    return urlopen(request, timeout=120)


def acquire_artifact(
    artifact: ArtifactSpec,
    root: str | Path,
    *,
    open_url: OpenUrl = _default_open,
    verify_only: bool = False,
) -> dict[str, Any]:
    destination = resolve_artifact_destination(root, artifact.destination)
    if destination.exists():
        receipt = verify_artifact(destination, artifact)
        return {**receipt, "status": "verified-existing"}
    if verify_only:
        raise ValueError(f"missing artifact in verify-only mode: {destination}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".part")
    if partial.exists():
        partial.unlink()
    request = Request(
        artifact.url,
        headers={"User-Agent": "IntuitionMap-data-acquisition/0.1"},
    )
    try:
        with open_url(request) as response, partial.open("xb") as output:
            shutil.copyfileobj(response, output, length=1024 * 1024)
        receipt = verify_artifact(partial, artifact)
        os.replace(partial, destination)
    except Exception:
        if partial.exists():
            partial.unlink()
        raise
    return {**receipt, "path": str(destination), "status": "downloaded"}


def acquire_public_dataset(
    spec: PublicDatasetSpec,
    root: str | Path,
    *,
    open_url: OpenUrl = _default_open,
    verify_only: bool = False,
) -> dict[str, Any]:
    artifacts = [
        acquire_artifact(
            artifact,
            root,
            open_url=open_url,
            verify_only=verify_only,
        )
        for artifact in spec.artifacts
    ]
    return {
        "schema_version": "0.1.0",
        "registry_id": spec.registry_id,
        "name": spec.name,
        "upstream_revision": spec.upstream_revision,
        "manifest": str(spec.manifest_path),
        "verified_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "artifact_count": len(artifacts),
        "registered_download_bytes": spec.registered_download_bytes,
        "artifacts": artifacts,
        "paid_api_requests": 0,
        "estimated_cost_usd": 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Acquire and verify a pinned public IntuitionMap artifact."
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("datasets/external"),
        help="Ignored local artifact root (default: datasets/external)",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Reject missing artifacts instead of downloading them.",
    )
    args = parser.parse_args(argv)
    spec = load_public_dataset_spec(args.manifest)
    receipt = acquire_public_dataset(
        spec,
        args.root,
        verify_only=args.verify_only,
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
