from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from intuition_map_eval.dataset import load_dataset, validation_summary
from intuition_map_eval.runner import run_experiment


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="intuition-eval",
        description="Reproducible evaluation harness for IntuitionMap.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser(
        "validate", help="Validate a dataset without running an experiment."
    )
    validate.add_argument("--dataset", required=True, type=Path)

    run = subparsers.add_parser(
        "run", help="Run one deterministic evaluation experiment."
    )
    run.add_argument("--dataset", required=True, type=Path)
    run.add_argument("--config", required=True, type=Path)
    run.add_argument("--output", default=Path("runs"), type=Path)
    run.add_argument(
        "--allow-paid-api",
        action="store_true",
        help=(
            "Second paid-execution gate. The current offline baseline never "
            "makes an API request."
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "validate":
            result = validation_summary(load_dataset(args.dataset))
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        if args.command == "run":
            run_path, metrics = run_experiment(
                dataset_path=args.dataset,
                config_path=args.config,
                output_root=args.output,
                cli_allows_paid_api=args.allow_paid_api,
            )
            print(
                json.dumps(
                    {
                        "run_path": str(run_path),
                        "metrics": metrics,
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 2

