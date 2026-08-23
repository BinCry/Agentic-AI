from __future__ import annotations

import hashlib
import unittest

from coding_agent.project.instructions import InstructionResolver
from coding_agent.storage.workspace import WorkspacePaths, WorkspacePolicyError

from tests.support import WorkspaceTestCase


class InstructionResolverTests(WorkspaceTestCase):
    def write_instruction(self, path: str, content: str) -> None:
        target = self.test_root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def test_resolves_root_to_leaf_with_stable_same_scope_precedence(self) -> None:
        self.write_instruction("CLAUDE.md", "root claude")
        self.write_instruction("AGENTS.md", "root agents")
        self.write_instruction("src/CLAUDE.md", "src claude")
        self.write_instruction("src/AGENTS.md", "src agents")
        self.write_instruction("src/package/module.py", "VALUE = 1")

        blocks = InstructionResolver(self.make_paths()).resolve("src/package/module.py")

        self.assertEqual(
            [block.path for block in blocks],
            ["CLAUDE.md", "AGENTS.md", "src/CLAUDE.md", "src/AGENTS.md"],
        )
        self.assertEqual([block.scope for block in blocks], [".", ".", "src", "src"])
        self.assertEqual(blocks[-1].content, "src agents")
        self.assertTrue(all(len(block.sha256) == 64 for block in blocks))

    def test_bounds_instruction_content_and_hashes_full_source(self) -> None:
        content = "A" * 40
        self.write_instruction("AGENTS.md", content)

        blocks = InstructionResolver(
            self.make_paths(), maximum_file_bytes=16, maximum_total_bytes=16
        ).resolve()

        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].content, "A" * 16)
        self.assertTrue(blocks[0].truncated)
        self.assertEqual(blocks[0].sha256, hashlib.sha256(content.encode()).hexdigest())

    def test_rejects_target_and_instruction_symlink_escape(self) -> None:
        paths = self.make_paths()
        with self.assertRaisesRegex(WorkspacePolicyError, "escapes workspace"):
            InstructionResolver(paths).resolve("../outside.py")

        outside = self.test_root.parent / f"{self.test_root.name}-outside.md"
        outside.write_text("outside", encoding="utf-8")
        link = self.test_root / "AGENTS.md"
        try:
            link.symlink_to(outside)
        except OSError as exc:
            outside.unlink(missing_ok=True)
            self.skipTest(f"file symlinks unavailable: {exc}")
        try:
            with self.assertRaisesRegex(WorkspacePolicyError, "escapes workspace"):
                InstructionResolver(paths).resolve()
        finally:
            link.unlink(missing_ok=True)
            outside.unlink(missing_ok=True)

    def test_skips_binary_instruction_without_exposing_bytes(self) -> None:
        (self.test_root / "AGENTS.md").write_bytes(b"safe\x00secret")

        self.assertEqual(InstructionResolver(self.make_paths()).resolve(), ())

        (self.test_root / "AGENTS.md").write_bytes(b"invalid-utf8-\xff")
        self.assertEqual(InstructionResolver(self.make_paths()).resolve(), ())

    def make_paths(self) -> WorkspacePaths:
        return WorkspacePaths.create(self.test_root).ensure()


if __name__ == "__main__":
    unittest.main()
