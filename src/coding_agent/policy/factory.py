"""Construct the compatibility tool policy from explicit authority inputs."""

from __future__ import annotations

from .loader import PolicyLoader
from .models import ApprovalMode, WorkspaceTrust
from ..storage.workspace import WorkspacePaths
from ..tools.policy import ToolPermissionPolicy


def build_tool_policy(
    paths: WorkspacePaths,
    *,
    approval_mode: str | None,
    workspace_trust: str,
    policy_file: str | None,
    workspace_policy: str | None,
    read_only: bool = False,
) -> ToolPermissionPolicy:
    mode = ApprovalMode(approval_mode) if approval_mode else (
        ApprovalMode.READ_ONLY if read_only else ApprovalMode.ASK
    )
    if read_only and mode is not ApprovalMode.READ_ONLY:
        raise ValueError("read_only tasks require approval mode read-only")
    loader = PolicyLoader(paths)
    rules = ()
    if policy_file:
        rules += loader.load_explicit(policy_file)
    if workspace_policy:
        rules += loader.load_workspace_narrowing(workspace_policy)
    return ToolPermissionPolicy(
        paths,
        mode=mode,
        workspace_trust=WorkspaceTrust(workspace_trust),
        rules=rules,
    )
