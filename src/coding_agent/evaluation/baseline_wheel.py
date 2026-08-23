"""Isolated wheel build, install, and import smoke gate."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Any, Callable

from .. import __version__
from ..storage.workspace import WorkspacePaths


CommandGate = Callable[..., dict[str, Any]]


def run_wheel_gate(
    paths: WorkspacePaths,
    run_root: Path,
    environment: dict[str, str],
    command_gate: CommandGate,
) -> dict[str, Any]:
    context = run_root / "build-context"
    try:
        context.mkdir()
        for name in ("pyproject.toml", "README.md"):
            shutil.copy2(paths.resolve_workspace_path(name, must_exist=True), context / name)
        shutil.copytree(
            paths.resolve_workspace_path("src", must_exist=True),
            context / "src",
            ignore=shutil.ignore_patterns("*.egg-info", "__pycache__", "*.pyc"),
        )
    except (OSError, ValueError) as exc:
        return {"status": "failed", "required": True, "error": type(exc).__name__}
    wheel_dir = run_root / "wheel"
    build_gate = command_gate(
        [
            sys.executable,
            "-B",
            "-m",
            "pip",
            "wheel",
            ".",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(wheel_dir),
        ],
        required=True,
        timeout_seconds=120,
        cwd=context,
    )
    build_diagnostics = f"{build_gate.get('_stdout', '')}\n{build_gate.get('_stderr', '')}"
    _discard_process_output(build_gate)
    wheels = sorted(wheel_dir.glob("*.whl")) if wheel_dir.is_dir() else []
    if build_gate["status"] != "passed" or len(wheels) != 1:
        build_gate["status"] = "failed"
        build_gate["diagnostic"] = "wheel build did not produce exactly one artifact"
        if "Cannot import 'setuptools.build_meta'" in build_diagnostics:
            build_gate["status"] = "unavailable"
            build_gate["diagnostic"] = "install the local build requirements for wheel smoke"
        return build_gate
    install_root = run_root / "wheel-install"
    install_gate = command_gate(
        [
            sys.executable,
            "-B",
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--no-index",
            "--target",
            str(install_root),
            str(wheels[0]),
        ],
        required=True,
        timeout_seconds=120,
    )
    _discard_process_output(install_gate)
    if install_gate["status"] != "passed":
        return install_gate
    smoke_environment = dict(environment)
    smoke_environment["PYTHONPATH"] = str(install_root)
    smoke_gate = command_gate(
        [
            sys.executable,
            "-B",
            "-c",
            "import coding_agent; print(coding_agent.__version__)",
        ],
        required=True,
        timeout_seconds=30,
        environment=smoke_environment,
    )
    smoke_gate.pop("_stderr", None)
    version = smoke_gate.pop("_stdout", "").strip()
    smoke_gate["wheel"] = wheels[0].name
    smoke_gate["imported_version"] = version or None
    if smoke_gate["status"] == "passed" and version != __version__:
        smoke_gate["status"] = "failed"
        smoke_gate["diagnostic"] = "installed wheel version does not match source"
    return smoke_gate


def _discard_process_output(gate: dict[str, Any]) -> None:
    gate.pop("_stdout", None)
    gate.pop("_stderr", None)
