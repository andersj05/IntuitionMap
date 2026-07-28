from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from intuition_map_private.annotations import (
    create_blind_repeats,
    create_discovery_queue,
    create_standard_proposal_queue,
    export_annotation_batch,
    import_annotation_responses,
)
from intuition_map_private.burden import pilot_burden_summary
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


def _workspace_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--workspace", required=True, type=Path)


def _participant_parser(parser: argparse.ArgumentParser) -> None:
    _workspace_parser(parser)
    parser.add_argument("--participant", required=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="intuition-private",
        description=(
            "Local-only consent, import, annotation, export, and deletion "
            "workflow for IntuitionMap private data."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)

    initialize = commands.add_parser("init")
    _workspace_parser(initialize)

    consent = commands.add_parser("grant-consent")
    _participant_parser(consent)
    consent.add_argument("--source-type", action="append", required=True)
    consent.add_argument(
        "--purpose",
        action="append",
        choices=["local_retrieval_research", "annotation_pilot"],
        required=True,
    )
    consent.add_argument("--retention-days", type=int, required=True)
    consent.add_argument("--allow-training-use", action="store_true")
    raw_choice = consent.add_mutually_exclusive_group(required=True)
    raw_choice.add_argument("--store-exact-raw", action="store_true")
    raw_choice.add_argument("--redacted-view-only", action="store_true")
    consent.add_argument(
        "--allow-derived-features",
        action="store_true",
        help="Required for local redaction, retrieval, and queue construction.",
    )
    consent.add_argument("--ack-ownership", action="store_true")
    consent.add_argument("--ack-sensitive-data", action="store_true")
    consent.add_argument("--ack-deletion-limits", action="store_true")
    consent.add_argument("--ack-no-app-encryption", action="store_true")

    import_command = commands.add_parser("import-jsonl")
    _participant_parser(import_command)
    import_command.add_argument("--input", required=True, type=Path)

    freeze = commands.add_parser("freeze-test")
    _participant_parser(freeze)
    freeze.add_argument("--test-fraction", type=float, default=0.20)
    freeze.add_argument("--minimum-test-queries", type=int, default=2)

    discovery = commands.add_parser("queue-discovery")
    _participant_parser(discovery)
    discovery.add_argument("--source-thought", action="append")
    discovery.add_argument("--limit", type=int, default=20)

    proposals = commands.add_parser("queue-proposals")
    _participant_parser(proposals)
    proposals.add_argument("--source-thought", required=True)
    proposals.add_argument("--seed", type=int, default=1729)

    repeats = commands.add_parser("queue-repeats")
    _participant_parser(repeats)
    repeats.add_argument("--rate", type=float, default=0.10)
    repeats.add_argument("--minimum-delay-days", type=int, default=7)

    batch = commands.add_parser("export-batch")
    _participant_parser(batch)
    batch.add_argument(
        "--stream", choices=["discovery", "proposal"], required=True
    )
    batch.add_argument("--output", required=True, type=Path)
    batch.add_argument("--limit", type=int, default=20)

    responses = commands.add_parser("import-responses")
    _participant_parser(responses)
    responses.add_argument("--input", required=True, type=Path)

    summary = commands.add_parser("pilot-summary")
    _participant_parser(summary)

    export = commands.add_parser("export")
    _participant_parser(export)
    export.add_argument("--output", required=True, type=Path)
    export.add_argument(
        "--purpose",
        choices=["user_portability", "training"],
        default="user_portability",
    )
    export.add_argument("--include-raw", action="store_true")

    revoke = commands.add_parser("revoke-consent")
    _workspace_parser(revoke)
    revoke.add_argument("--consent-id", required=True)
    revoke.add_argument("--reason", required=True)

    delete = commands.add_parser("delete-participant")
    _participant_parser(delete)
    delete.add_argument(
        "--confirm-participant",
        required=True,
        help="Must exactly match --participant.",
    )
    return parser


def _consent(args: argparse.Namespace) -> dict[str, Any]:
    acknowledgements = []
    if args.ack_ownership:
        acknowledgements.append("owns_or_controls_content")
    if args.ack_sensitive_data:
        acknowledgements.append("understands_sensitive_data_risk")
    if args.ack_deletion_limits:
        acknowledgements.append("understands_deletion_limits")
    if args.ack_no_app_encryption:
        acknowledgements.append(
            "understands_local_storage_is_not_app_encryption"
        )
    if set(acknowledgements) != REQUIRED_ACKNOWLEDGEMENTS:
        raise ValueError(
            "all four explicit acknowledgement flags are required"
        )
    if not args.allow_derived_features:
        raise ValueError(
            "--allow-derived-features is required for this pilot workflow"
        )
    receipt = ConsentReceipt.create(
        participant_id=args.participant,
        purposes=args.purpose,
        source_types=args.source_type,
        retention_days=args.retention_days,
        acknowledgements=acknowledgements,
        store_raw_content=args.store_exact_raw,
        allow_derived_features=args.allow_derived_features,
        allow_training_use=args.allow_training_use,
        local_only=True,
    )
    result = PrivateWorkspace(args.workspace).add_consent(receipt)
    result["policy_summary"] = {
        "local_only": True,
        "store_raw_content": receipt.store_raw_content,
        "allow_training_use": receipt.allow_training_use,
        "retention_days": receipt.retention_days,
    }
    return result


def _execute(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "init":
        workspace = PrivateWorkspace.initialize(args.workspace)
        return {
            "workspace": str(workspace.root),
            "database": str(workspace.database_path),
            "local_only": True,
            "application_level_encryption": False,
        }
    if args.command == "grant-consent":
        return _consent(args)
    workspace = PrivateWorkspace(args.workspace)
    if args.command == "import-jsonl":
        return import_jsonl(
            workspace,
            participant_id=args.participant,
            path=args.input,
        )
    if args.command == "freeze-test":
        return freeze_chronological_test_manifest(
            workspace,
            participant_id=args.participant,
            test_fraction=args.test_fraction,
            minimum_test_queries=args.minimum_test_queries,
        )
    if args.command == "queue-discovery":
        return create_discovery_queue(
            workspace,
            participant_id=args.participant,
            source_thought_ids=args.source_thought,
            limit=args.limit,
        )
    if args.command == "queue-proposals":
        return create_standard_proposal_queue(
            workspace,
            participant_id=args.participant,
            source_thought_id=args.source_thought,
            seed=args.seed,
        )
    if args.command == "queue-repeats":
        return create_blind_repeats(
            workspace,
            participant_id=args.participant,
            rate=args.rate,
            minimum_delay_days=args.minimum_delay_days,
        )
    if args.command == "export-batch":
        return export_annotation_batch(
            workspace,
            participant_id=args.participant,
            stream=args.stream,
            output_path=args.output,
            limit=args.limit,
        )
    if args.command == "import-responses":
        return import_annotation_responses(
            workspace,
            participant_id=args.participant,
            response_path=args.input,
        )
    if args.command == "pilot-summary":
        return pilot_burden_summary(
            workspace,
            participant_id=args.participant,
        )
    if args.command == "export":
        return export_participant_bundle(
            workspace,
            participant_id=args.participant,
            output_path=args.output,
            purpose=args.purpose,
            include_raw=args.include_raw,
        )
    if args.command == "revoke-consent":
        return workspace.revoke_consent(
            args.consent_id,
            reason=args.reason,
        )
    if args.command == "delete-participant":
        if args.confirm_participant != args.participant:
            raise ValueError(
                "--confirm-participant must exactly match --participant"
            )
        return workspace.delete_participant(args.participant)
    raise ValueError(f"unsupported command: {args.command}")


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = _execute(args)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
