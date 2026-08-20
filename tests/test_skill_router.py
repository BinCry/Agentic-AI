from __future__ import annotations

import unittest

from coding_agent.skills.catalog import SkillCatalog, SkillCatalogError
from coding_agent.skills.router import SkillRouter
from coding_agent.workflow.status import WorkflowStatus

from tests.support import WorkspaceTestCase


class SkillCatalogTests(WorkspaceTestCase):
    def test_catalog_loads_metadata_and_digest(self) -> None:
        self.write_skill("fix", declared_name="ck:fix", description="Fix problems")
        catalog = SkillCatalog(self.test_root / ".claude" / "skills").load()
        definition = catalog.get("ck:fix")
        self.assertIsNotNone(definition)
        assert definition is not None
        self.assertEqual(definition.internal_name, "fix")
        self.assertEqual(len(definition.content_digest), 64)
        self.assertEqual(definition.keywords, ("test", "coding"))

    def test_router_selects_first_available_skill(self) -> None:
        self.write_skill("ask")
        self.write_skill("fix")
        catalog = SkillCatalog(self.test_root / ".claude" / "skills").load()
        selected = SkillRouter(catalog).select(WorkflowStatus.ANALYZING)
        self.assertEqual(selected.internal_name, "fix")

    def test_router_rejects_state_without_available_skill(self) -> None:
        self.write_skill("unrelated")
        catalog = SkillCatalog(self.test_root / ".claude" / "skills").load()
        with self.assertRaisesRegex(SkillCatalogError, "no reusable skill"):
            SkillRouter(catalog).select(WorkflowStatus.TESTING)

    def test_missing_skill_root_is_rejected(self) -> None:
        with self.assertRaisesRegex(SkillCatalogError, "does not exist"):
            SkillCatalog(self.test_root / "missing").load()


if __name__ == "__main__":
    unittest.main()
