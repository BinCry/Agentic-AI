"""Test helpers that keep every temporary write inside the D: workspace."""

from __future__ import annotations

import os
import shutil
import stat
import unittest
from pathlib import Path
from typing import Callable
from uuid import uuid4


class WorkspaceTestCase(unittest.TestCase):
    test_root: Path

    def setUp(self) -> None:
        base = Path(os.environ.get("CODING_AGENT_TEST_TMP", ".tmp/tests")).resolve()
        if base.drive.upper() == "C:":
            self.fail("CODING_AGENT_TEST_TMP must not use drive C:")
        base.mkdir(parents=True, exist_ok=True)
        self.test_root = base / f"case-{uuid4().hex}"
        self.test_root.mkdir()

    def tearDown(self) -> None:
        if self.test_root.exists():
            shutil.rmtree(self.test_root, onerror=_remove_readonly)

    def write_skill(
        self,
        internal_name: str,
        *,
        declared_name: str | None = None,
        description: str = "test skill",
    ) -> Path:
        skill_path = self.test_root / ".claude" / "skills" / internal_name / "SKILL.md"
        skill_path.parent.mkdir(parents=True, exist_ok=True)
        skill_path.write_text(
            "---\n"
            f"name: {declared_name or internal_name}\n"
            f"description: {description}\n"
            "keywords: [test, coding]\n"
            "---\n\n"
            "# Test Skill\n",
            encoding="utf-8",
        )
        return skill_path


def _remove_readonly(function: Callable[[str], object], path: str, exception_info: object) -> None:
    """Allow isolated Git fixture objects to be removed on Windows."""
    del exception_info
    os.chmod(path, stat.S_IWRITE)
    function(path)
