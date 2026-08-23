"""Offline Python/Node manifest inspection without command execution."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ..storage.workspace import WorkspacePaths
from .instructions import InstructionResolver
from .profile import CommandCandidate, ManifestRecord, ProjectProfile


PYTHON_MANIFESTS = (
    "pyproject.toml",
    "setup.cfg",
    "setup.py",
    "requirements.txt",
    "uv.lock",
    "poetry.lock",
    "pdm.lock",
)
NODE_MANIFESTS = (
    "package.json",
    "bun.lock",
    "bun.lockb",
    "pnpm-lock.yaml",
    "yarn.lock",
    "package-lock.json",
    "npm-shrinkwrap.json",
)
UNKNOWN_MANIFESTS = ("Cargo.toml", "go.mod", "pom.xml", "build.gradle", "Gemfile")
NODE_LOCK_MANAGERS = (
    ("bun.lock", "bun"),
    ("bun.lockb", "bun"),
    ("pnpm-lock.yaml", "pnpm"),
    ("yarn.lock", "yarn"),
    ("package-lock.json", "npm"),
    ("npm-shrinkwrap.json", "npm"),
)


class ProjectInspector:
    def __init__(self, paths: WorkspacePaths, *, maximum_manifest_bytes: int = 1_048_576) -> None:
        if (
            not isinstance(maximum_manifest_bytes, int)
            or isinstance(maximum_manifest_bytes, bool)
            or maximum_manifest_bytes < 1
        ):
            raise ValueError("maximum_manifest_bytes must be positive")
        self.paths = paths.ensure()
        self.maximum_manifest_bytes = maximum_manifest_bytes

    def inspect(self) -> ProjectProfile:
        manifests: list[ManifestRecord] = []
        ecosystems: list[str] = []
        commands: list[CommandCandidate] = []
        python_paths = self._records(PYTHON_MANIFESTS, "python", manifests)
        node_paths = self._records(NODE_MANIFESTS, "node", manifests)
        unknown_paths = self._records(UNKNOWN_MANIFESTS, "unknown", manifests)
        if python_paths:
            ecosystems.append("python")
            commands.extend(self._python_commands(python_paths))
        python_managers = self._python_managers(python_paths)
        managers: list[str] = []
        package_payload: dict[str, Any] = {}
        if node_paths:
            ecosystems.append("node")
            package_payload = self._package_payload()
            managers = self._node_managers(package_payload)
            if len(managers) == 1:
                commands.extend(self._node_commands(managers[0], package_payload))
        if unknown_paths:
            ecosystems.append("unknown")
        return ProjectProfile(
            1,
            self.paths.workspace_root.name,
            tuple(ecosystems),
            tuple(dict.fromkeys([*python_managers, *managers])),
            tuple(manifests),
            tuple(commands),
            InstructionResolver(self.paths).resolve(),
        )

    def _records(
        self, names: tuple[str, ...], ecosystem: str, output: list[ManifestRecord]
    ) -> tuple[Path, ...]:
        found: list[Path] = []
        for name in names:
            candidate = self.paths.workspace_root / name
            if not candidate.exists() and not candidate.is_symlink():
                continue
            resolved = self.paths.resolve_workspace_path(candidate, must_exist=True)
            if not resolved.is_file():
                continue
            if resolved.stat().st_size > self.maximum_manifest_bytes:
                continue
            raw = resolved.read_bytes()
            output.append(ManifestRecord(name, ecosystem, name, hashlib.sha256(raw).hexdigest()))
            found.append(resolved)
        return tuple(found)

    def _python_managers(self, manifests: tuple[Path, ...]) -> list[str]:
        if not manifests:
            return []
        for lock_name, manager in (("uv.lock", "uv"), ("poetry.lock", "poetry"), ("pdm.lock", "pdm")):
            if (self.paths.workspace_root / lock_name).is_file():
                return [manager]
        return ["pip"]

    def _python_commands(self, manifests: tuple[Path, ...]) -> list[CommandCandidate]:
        commands: list[CommandCandidate] = []
        manifest_names = {item.name for item in manifests}
        if {"pyproject.toml", "setup.py", "setup.cfg"} & manifest_names:
            commands.append(
                CommandCandidate("build", ("python", "-m", "pip", "wheel", ".", "--no-deps"), "python manifest")
            )
        tests = self.paths.workspace_root / "tests"
        if tests.is_dir() and self._contains_test_module(tests):
            commands.append(
                CommandCandidate(
                    "test",
                    ("python", "-m", "unittest", "discover", "-s", "tests"),
                    "observed tests/test*.py",
                )
            )
        return commands

    def _contains_test_module(self, tests: Path) -> bool:
        for index, candidate in enumerate(tests.rglob("test*.py")):
            if index >= 2_000:
                return False
            try:
                resolved = self.paths.resolve_workspace_path(candidate, must_exist=True)
            except ValueError:
                continue
            if resolved.is_file():
                return True
        return False

    def _package_payload(self) -> dict[str, Any]:
        package = self.paths.workspace_root / "package.json"
        if not package.exists() and not package.is_symlink():
            return {}
        package = self.paths.resolve_workspace_path(package, must_exist=True)
        if not package.is_file() or package.stat().st_size > self.maximum_manifest_bytes:
            return {}
        try:
            payload = json.loads(package.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _node_managers(self, payload: dict[str, Any]) -> list[str]:
        managers: list[str] = []
        declared = payload.get("packageManager")
        if isinstance(declared, str):
            name = declared.split("@", 1)[0]
            if name in {"npm", "pnpm", "yarn", "bun"}:
                managers.append(name)
        for lock_name, manager in NODE_LOCK_MANAGERS:
            if (self.paths.workspace_root / lock_name).is_file() and manager not in managers:
                managers.append(manager)
        return managers

    @staticmethod
    def _node_commands(manager: str, payload: dict[str, Any]) -> list[CommandCandidate]:
        scripts = payload.get("scripts")
        if not isinstance(scripts, dict):
            return []
        return [
            CommandCandidate("script", (manager, "run", name), f"package.json scripts.{name}")
            for name, value in sorted(scripts.items())
            if isinstance(name, str) and name and isinstance(value, str) and value.strip()
        ]
