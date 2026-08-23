"""Model-free project inspection CLI."""

from __future__ import annotations

import argparse

from .project.inspector import ProjectInspector
from .storage.workspace import WorkspacePaths


def add_project_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    project = subparsers.add_parser("project", help="Inspect repository metadata")
    commands = project.add_subparsers(dest="project_command", required=True)
    inspect_parser = commands.add_parser(
        "inspect", help="Print a bounded project profile without using a model"
    )
    inspect_parser.add_argument("--format", choices=("json",), default="json")


def run_project_command(args: argparse.Namespace, paths: WorkspacePaths) -> dict[str, object]:
    if args.project_command != "inspect":
        raise ValueError(f"unsupported project command: {args.project_command}")
    return ProjectInspector(paths).inspect().to_dict()
