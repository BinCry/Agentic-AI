from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path

from coding_agent.project.inspector import ProjectInspector
from coding_agent.project.profile import ProjectProfile
from coding_agent.storage.workspace import WorkspacePaths, WorkspacePolicyError

from tests.support import WorkspaceTestCase


class ProjectInspectorTests(WorkspaceTestCase):
    def inspect(self) -> ProjectProfile:
        return ProjectInspector(WorkspacePaths.create(self.test_root).ensure()).inspect()

    def test_detects_python_manifest_and_observed_unittest_candidate(self) -> None:
        (self.test_root / "pyproject.toml").write_text(
            "[project]\nname = 'fixture'\n", encoding="utf-8"
        )
        tests = self.test_root / "tests"
        tests.mkdir()
        (tests / "test_app.py").write_text("import unittest\n", encoding="utf-8")

        profile = self.inspect()

        self.assertEqual(profile.ecosystems, ("python",))
        self.assertEqual(profile.package_managers, ("pip",))
        self.assertIn("pyproject.toml", [item.path for item in profile.manifests])
        self.assertIn(
            ("python", "-m", "unittest", "discover", "-s", "tests"),
            [item.argv for item in profile.commands],
        )

    def test_detects_node_lockfile_manager_and_declared_scripts(self) -> None:
        fixture = Path(__file__).parent / "fixtures" / "sample_node_repo"
        shutil.copytree(fixture, self.test_root, dirs_exist_ok=True)

        profile = self.inspect()

        self.assertEqual(profile.ecosystems, ("node",))
        self.assertEqual(profile.package_managers, ("npm",))
        self.assertEqual(
            [item.argv for item in profile.commands],
            [("npm", "run", "build"), ("npm", "run", "test")],
        )
        self.assertEqual(ProjectProfile.from_dict(profile.to_dict()), profile)
        json.dumps(profile.to_dict())

    def test_exposes_unknown_manifest_without_inventing_command(self) -> None:
        (self.test_root / "Cargo.toml").write_text(
            "[package]\nname = 'fixture'\n", encoding="utf-8"
        )

        profile = self.inspect()

        self.assertEqual(profile.ecosystems, ("unknown",))
        self.assertEqual(profile.manifests[0].path, "Cargo.toml")
        self.assertEqual(profile.commands, ())
        self.assertEqual(profile.package_managers, ())

    def test_hybrid_profile_keeps_managers_and_lockfile_provenance(self) -> None:
        (self.test_root / "pyproject.toml").write_text("[project]\nname='hybrid'\n", encoding="utf-8")
        (self.test_root / "uv.lock").write_text("version = 1\n", encoding="utf-8")
        (self.test_root / "package.json").write_text(
            json.dumps({"scripts": {"test": "node --test"}}), encoding="utf-8"
        )
        (self.test_root / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n", encoding="utf-8")

        profile = self.inspect()

        self.assertEqual(profile.ecosystems, ("python", "node"))
        self.assertEqual(profile.package_managers, ("uv", "pnpm"))
        self.assertIn("uv.lock", [item.path for item in profile.manifests])
        self.assertIn("pnpm-lock.yaml", [item.path for item in profile.manifests])
        self.assertIn(("pnpm", "run", "test"), [item.argv for item in profile.commands])

    def test_rejects_manifest_symlink_escape_before_reading_content(self) -> None:
        outside = self.test_root.parent / f"{self.test_root.name}-package.json"
        outside.write_text('{"scripts":{"leak":"secret"}}', encoding="utf-8")
        link = self.test_root / "package.json"
        try:
            link.symlink_to(outside)
        except OSError as exc:
            outside.unlink(missing_ok=True)
            self.skipTest(f"file symlinks unavailable: {exc}")
        try:
            with self.assertRaisesRegex(WorkspacePolicyError, "escapes workspace"):
                self.inspect()
        finally:
            link.unlink(missing_ok=True)
            outside.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
