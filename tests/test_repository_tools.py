from __future__ import annotations

import hashlib
import unittest

from coding_agent.storage.workspace import WorkspacePaths
from coding_agent.tools.patch_service import PatchConflictError, PatchService
from coding_agent.tools.repository_service import RepositoryReadService, RepositoryToolError

from tests.support import WorkspaceTestCase


class RepositoryToolTests(WorkspaceTestCase):
    def make_paths(self) -> WorkspacePaths:
        return WorkspacePaths.create(self.test_root).ensure()

    def test_read_search_and_python_symbols(self) -> None:
        target = self.test_root / "module.py"
        source = "class Example:\n    def run(self):\n        return 'needle'\n"
        target.write_text(source, encoding="utf-8")
        service = RepositoryReadService(self.make_paths())
        self.assertEqual(service.read_file("module.py"), source)
        self.assertEqual(service.search_text("needle")[0].line, 3)
        symbols = service.find_symbols("module.py")
        self.assertEqual([(item.name, item.kind) for item in symbols], [("Example", "class"), ("run", "function")])

    def test_read_size_is_bounded(self) -> None:
        (self.test_root / "large.txt").write_text("x" * 20, encoding="utf-8")
        service = RepositoryReadService(self.make_paths(), maximum_file_bytes=10)
        with self.assertRaises(RepositoryToolError):
            service.read_file("large.txt")

    def test_list_files_returns_workspace_relative_posix_paths(self) -> None:
        (self.test_root / "src").mkdir()
        (self.test_root / "src" / "module.py").write_text("value = 1\n", encoding="utf-8")
        files = RepositoryReadService(self.make_paths()).list_files("src")
        self.assertEqual(files, ["src/module.py"])

    def test_ignored_name_in_workspace_ancestor_does_not_hide_repository(self) -> None:
        workspace = self.test_root / ".coding-agent" / "nested-workspace"
        (workspace / "src").mkdir(parents=True)
        (workspace / "src" / "module.py").write_text("value = 1\n", encoding="utf-8")
        paths = WorkspacePaths.create(workspace).ensure()

        files = RepositoryReadService(paths).list_files("src")

        self.assertEqual(files, ["src/module.py"])

    def test_patch_requires_matching_digest_and_applies_atomically(self) -> None:
        target = self.test_root / "module.py"
        original = "a = 1\nb = 2\n"
        target.write_text(original, encoding="utf-8")
        service = PatchService(self.make_paths())
        patch = "@@ -1,2 +1,2 @@\n-a = 1\n+a = 3\n b = 2\n"
        record = service.apply_unified_patch(
            "module.py",
            patch,
            expected_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
        )
        self.assertTrue(record.applied)
        self.assertEqual(target.read_text(encoding="utf-8"), "a = 3\nb = 2\n")
        with self.assertRaises(PatchConflictError):
            service.apply_unified_patch("module.py", patch, expected_sha256="0" * 64)

    def test_create_file_refuses_overwrite(self) -> None:
        target = self.test_root / "new.py"
        target.write_text("existing\n", encoding="utf-8")
        with self.assertRaises(PatchConflictError):
            PatchService(self.make_paths()).create_file("new.py", "replacement\n")


if __name__ == "__main__":
    unittest.main()
