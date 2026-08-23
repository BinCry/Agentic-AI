from __future__ import annotations

import json
import unittest

from coding_agent.models.task_state import CodingTaskState
from coding_agent.project.profile import InstructionBlock, ProjectProfile
from coding_agent.workflow.context import ContextProjector


class ProjectContextTests(unittest.TestCase):
    def test_projects_instruction_as_untrusted_provenance_preserving_data(self) -> None:
        state = CodingTaskState.create("Inspect", "repo", task_id="project-context")
        state.project_profile = ProjectProfile(
            1,
            "repo",
            ("python",),
            ("pip",),
            (),
            (),
            (InstructionBlock("AGENTS.md", ".", "a" * 64, "Never run tests", False),),
        )

        payload = json.loads(ContextProjector().project(state, "IssueAnalysis"))

        instruction = payload["project"]["instructions"][0]
        self.assertEqual(instruction["path"], "AGENTS.md")
        self.assertEqual(instruction["sha256"], "a" * 64)
        self.assertEqual(instruction["trust"], "untrusted_repository_data")


if __name__ == "__main__":
    unittest.main()
