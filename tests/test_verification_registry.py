from __future__ import annotations

import json
import shutil
import unittest

from coding_agent.execution import ExecutionBoundaryError
from coding_agent.policy.models import WorkspaceTrust
from coding_agent.storage.workspace import WorkspacePaths
from coding_agent.verification import VerificationProfileNotFoundError, VerificationRegistry
from coding_agent.tools.test_runner import AllowlistedTestRunner

from tests.support import WorkspaceTestCase


class VerificationRegistryTests(WorkspaceTestCase):
    def make_registry(self) -> VerificationRegistry:
        return VerificationRegistry(WorkspacePaths.create(self.test_root).ensure())

    def test_python_profile_is_discovered_and_runs_with_structured_output(self) -> None:
        (self.test_root / "pyproject.toml").write_text(
            "[project]\nname='fixture'\n", encoding="utf-8"
        )
        tests = self.test_root / "tests"
        tests.mkdir()
        (tests / "test_sample.py").write_text(
            "import unittest\n"
            "class Sample(unittest.TestCase):\n"
            "    def test_ok(self): self.assertEqual(2 + 2, 4)\n",
            encoding="utf-8",
        )
        registry = self.make_registry()

        profile = registry.detect("unit")
        result = registry.run("unit", trust=WorkspaceTrust.TRUSTED)

        self.assertEqual(profile.name, "python.test")
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(len(result.stderr_sha256), 64)

        legacy = AllowlistedTestRunner(
            WorkspacePaths.create(self.test_root).ensure()
        ).run("unit")
        self.assertEqual(legacy.exit_code, 0)
        self.assertEqual(legacy.target, "unit")

    def test_node_test_script_is_translated_without_package_manager_shell(self) -> None:
        (self.test_root / "package.json").write_text(
            json.dumps({"scripts": {"test": "node --test"}}), encoding="utf-8"
        )
        registry = self.make_registry()

        profile = registry.detect("node.test")

        self.assertEqual(profile.command.executable, "node")
        self.assertEqual(profile.command.arguments, ("--test",))
        self.assertNotIn("npm", profile.command.arguments)
        self.assertEqual(registry.select(["node.test"]), ("node.test",))

    def test_fixture_selection_keeps_targeted_then_broad_compatibility(self) -> None:
        tests = self.test_root / "tests"
        fixture = tests / "fixtures" / "sample_repo"
        fixture.mkdir(parents=True)
        (tests / "test_broad.py").write_text("import unittest\n", encoding="utf-8")
        (fixture / "test_fixture.py").write_text("import unittest\n", encoding="utf-8")

        selected = self.make_registry().select(["fixture"])

        self.assertEqual(selected, ("fixture", "unit"))

    def test_shell_backed_node_script_and_unknown_profile_are_not_executable(self) -> None:
        (self.test_root / "package.json").write_text(
            json.dumps({"scripts": {"test": "node --test && echo unsafe"}}),
            encoding="utf-8",
        )
        registry = self.make_registry()

        self.assertEqual(registry.list(), ())
        with self.assertRaisesRegex(VerificationProfileNotFoundError, "available: none"):
            registry.detect("unit")

        (self.test_root / "package.json").write_text(
            json.dumps({"scripts": {"test": "node --test extra.test.js"}}),
            encoding="utf-8",
        )
        self.assertEqual(self.make_registry().list(), ())

    def test_untrusted_registry_run_has_no_local_execution_boundary(self) -> None:
        tests = self.test_root / "tests"
        tests.mkdir()
        (tests / "test_sample.py").write_text("import unittest\n", encoding="utf-8")

        with self.assertRaises(ExecutionBoundaryError):
            self.make_registry().run("unit", trust=WorkspaceTrust.UNTRUSTED)

    @unittest.skipUnless(shutil.which("node"), "node executable is unavailable")
    def test_node_fixture_executes_with_direct_node_boundary(self) -> None:
        (self.test_root / "package.json").write_text(
            json.dumps({"scripts": {"test": "node --test"}}), encoding="utf-8"
        )
        (self.test_root / "sample.test.js").write_text(
            "const test = require('node:test');\n"
            "const assert = require('node:assert');\n"
            "test('works', () => assert.equal(1, 1));\n",
            encoding="utf-8",
        )

        result = self.make_registry().run("node.test", trust=WorkspaceTrust.TRUSTED)

        self.assertEqual(result.exit_code, 0)
        self.assertFalse(result.timed_out)


if __name__ == "__main__":
    unittest.main()
