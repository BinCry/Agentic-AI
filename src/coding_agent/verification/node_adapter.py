"""Translate a narrow Node test script into direct node argv without a shell."""

from __future__ import annotations

import json
import re
import shlex

from ..storage.workspace import WorkspacePaths, WorkspacePolicyError
from ..tools.command_models import CommandRequest
from .models import VerificationProfile


_SHELL_SYNTAX = re.compile(r"(?:&&|\|\||[|;<>`$\r\n])")


def discover_node_profiles(
    paths: WorkspacePaths,
    *,
    maximum_manifest_bytes: int = 1_048_576,
) -> tuple[VerificationProfile, ...]:
    package = paths.workspace_root / "package.json"
    if not package.exists() and not package.is_symlink():
        return ()
    try:
        resolved = paths.resolve_workspace_path(package, must_exist=True)
    except WorkspacePolicyError:
        raise
    if not resolved.is_file() or resolved.stat().st_size > maximum_manifest_bytes:
        return ()
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return ()
    scripts = payload.get("scripts") if isinstance(payload, dict) else None
    test_script = scripts.get("test") if isinstance(scripts, dict) else None
    arguments = _direct_node_test_arguments(test_script)
    if arguments is None:
        return ()
    return (
        VerificationProfile(
            "node.test",
            "node",
            "test",
            CommandRequest("node", arguments),
            "package.json scripts.test translated without a package-manager shell",
        ),
    )


def _direct_node_test_arguments(value: object) -> tuple[str, ...] | None:
    if not isinstance(value, str) or not value.strip() or _SHELL_SYNTAX.search(value):
        return None
    try:
        tokens = tuple(shlex.split(value, posix=True))
    except ValueError:
        return None
    if tokens != ("node", "--test"):
        return None
    return ("--test",)
