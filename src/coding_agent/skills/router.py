"""Select reusable skills according to the explicit workflow state."""

from __future__ import annotations

from pathlib import Path

from ..models.records import ActiveSkill
from ..workflow.status import WorkflowStatus
from .catalog import SkillCatalog, SkillCatalogError, SkillDefinition

DEFAULT_STATE_SKILLS: dict[WorkflowStatus, tuple[str, ...]] = {
    WorkflowStatus.ANALYZING: ("fix", "ask", "ck-debug"),
    WorkflowStatus.RETRIEVING: ("scout", "gkg", "ck-graphify"),
    WorkflowStatus.VERIFYING_EVIDENCE: ("scout", "gkg", "ck-graphify"),
    WorkflowStatus.PLANNING: ("ck-plan", "cook"),
    WorkflowStatus.EDITING: ("cook", "fix"),
    WorkflowStatus.TESTING: ("test",),
    WorkflowStatus.DEBUGGING: ("ck-debug", "fix"),
    WorkflowStatus.REVIEWING: ("code-review",),
    WorkflowStatus.WAITING_APPROVAL: ("project-management",),
    WorkflowStatus.FINALIZING: ("git", "ship"),
}


class SkillRouter:
    def __init__(
        self,
        catalog: SkillCatalog,
        state_skills: dict[WorkflowStatus, tuple[str, ...]] | None = None,
    ) -> None:
        self.catalog = catalog
        self.state_skills = state_skills or DEFAULT_STATE_SKILLS

    def candidates(self, status: WorkflowStatus) -> tuple[SkillDefinition, ...]:
        return tuple(
            definition
            for name in self.state_skills.get(status, ())
            if (definition := self.catalog.get(name)) is not None
        )

    def select(self, status: WorkflowStatus) -> SkillDefinition:
        candidates = self.candidates(status)
        if not candidates:
            raise SkillCatalogError(f"no reusable skill configured for state {status.value}")
        return candidates[0]

    @staticmethod
    def as_active_skill(definition: SkillDefinition, workspace: Path) -> ActiveSkill:
        resolved_workspace = workspace.resolve()
        resolved_path = definition.path.resolve()
        path = (
            resolved_path.relative_to(resolved_workspace).as_posix()
            if resolved_path.is_relative_to(resolved_workspace)
            else str(resolved_path)
        )
        return ActiveSkill(
            name=definition.declared_name,
            path=path,
            content_digest=definition.content_digest,
        )
