"""Side-effect-free policy explanation and shared policy CLI options."""

from __future__ import annotations

import argparse
import json
from typing import Any

from .policy.factory import build_tool_policy
from .policy.models import ApprovalMode, WorkspaceTrust
from .storage.workspace import WorkspacePaths
from .tools.contracts import ToolRequest


def add_policy_options(parser: argparse.ArgumentParser, *, optional_mode: bool = False) -> None:
    parser.add_argument(
        "--approval-mode",
        "--mode",
        choices=tuple(item.value for item in ApprovalMode),
        default=None if optional_mode else ApprovalMode.ASK.value,
    )
    parser.add_argument(
        "--workspace-trust",
        choices=tuple(item.value for item in WorkspaceTrust),
        default=WorkspaceTrust.TRUSTED.value,
    )
    parser.add_argument("--policy-file", help="Explicit trusted policy TOML")
    parser.add_argument(
        "--workspace-policy",
        help="Workspace-contained narrowing-only policy TOML",
    )


def add_policy_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    policy = subparsers.add_parser("policy", help="Explain tool authority without execution")
    commands = policy.add_subparsers(dest="policy_command", required=True)
    check = commands.add_parser("check", help="Validate and explain one tool request")
    check.add_argument("--tool", required=True)
    check.add_argument("--arguments-json", default="{}")
    check.add_argument("--state", default="EDITING")
    add_policy_options(check)


def run_policy_command(args: argparse.Namespace, paths: WorkspacePaths) -> dict[str, Any]:
    if args.policy_command != "check":
        raise ValueError(f"unsupported policy command: {args.policy_command}")
    try:
        arguments = json.loads(args.arguments_json)
    except json.JSONDecodeError as exc:
        raise ValueError("arguments-json must be valid JSON") from exc
    if not isinstance(arguments, dict):
        raise ValueError("arguments-json must decode to an object")
    policy = build_tool_policy(
        paths,
        approval_mode=args.approval_mode,
        workspace_trust=args.workspace_trust,
        policy_file=args.policy_file,
        workspace_policy=args.workspace_policy,
    )
    request = ToolRequest("policy-check", "policy-check", args.tool, arguments, args.state)
    decision = policy.explain(request)
    return {
        "tool": decision.spec.to_dict(),
        "decision": decision.explanation.to_dict(),
    }
