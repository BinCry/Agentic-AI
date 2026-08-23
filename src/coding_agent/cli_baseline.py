"""CLI registration and handler for local capability baselines."""

from __future__ import annotations

import argparse
from pathlib import Path

from .evaluation.baseline import BaselineRunner
from .storage.workspace import WorkspacePaths


def add_baseline_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "baseline", help="Run reproducible local tests, wheel smoke, and evaluation"
    )
    parser.add_argument(
        "--benchmark", default="tests/fixtures/benchmarks/retrieval_cases.json"
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--output", help="Workspace-relative JSON report path; defaults inside runtime"
    )
    parser.add_argument(
        "--require-coverage",
        action="store_true",
        help="Fail when the optional coverage package is unavailable",
    )


def run_baseline_command(args: argparse.Namespace, paths: WorkspacePaths) -> dict[str, object]:
    return BaselineRunner(paths).run(
        args.benchmark,
        top_k=args.top_k,
        output_path=Path(args.output) if args.output else None,
        require_coverage=args.require_coverage,
    )
