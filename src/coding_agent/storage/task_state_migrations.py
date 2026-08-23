"""Pure ordered migrations for durable task-state JSON payloads."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

from ..models.run_accounting import RunBudget, UsageLedger
from ..models.task_state_schema import (
    CURRENT_TASK_SCHEMA_VERSION,
    MINIMUM_TASK_SCHEMA_VERSION,
)


class TaskStateMigrationError(ValueError):
    """Raised when persisted task state cannot be migrated safely."""


Migration = Callable[[dict[str, Any]], dict[str, Any]]


def _migrate_version_1_to_2(payload: dict[str, Any]) -> dict[str, Any]:
    migrated = deepcopy(payload)
    migrated.setdefault("run_budget", RunBudget().to_dict())
    migrated.setdefault("usage_ledger", UsageLedger().to_dict())
    migrated["schema_version"] = 2
    return migrated


def _migrate_version_2_to_3(payload: dict[str, Any]) -> dict[str, Any]:
    migrated = deepcopy(payload)
    migrated.setdefault("project_profile", None)
    migrated["schema_version"] = 3
    return migrated


class TaskStateMigrator:
    """Apply every required migration without mutating caller-owned data."""

    _migrations: dict[int, Migration] = {
        1: _migrate_version_1_to_2,
        2: _migrate_version_2_to_3,
    }

    @staticmethod
    def version_of(payload: object) -> int:
        if not isinstance(payload, dict):
            raise TaskStateMigrationError("task state must be a JSON object")
        version = payload.get("schema_version")
        if not isinstance(version, int) or isinstance(version, bool):
            raise TaskStateMigrationError("task state schema_version must be an integer")
        if version < MINIMUM_TASK_SCHEMA_VERSION:
            raise TaskStateMigrationError(f"task state schema_version {version} is unsupported")
        if version > CURRENT_TASK_SCHEMA_VERSION:
            raise TaskStateMigrationError(
                f"task state schema_version {version} is newer than supported "
                f"version {CURRENT_TASK_SCHEMA_VERSION}"
            )
        return version

    def migrate(self, payload: object) -> dict[str, Any]:
        version = self.version_of(payload)
        migrated = deepcopy(payload)
        while version < CURRENT_TASK_SCHEMA_VERSION:
            migration = self._migrations.get(version)
            if migration is None:
                raise TaskStateMigrationError(
                    f"no task-state migration exists from schema_version {version}"
                )
            migrated = migration(migrated)
            next_version = self.version_of(migrated)
            if next_version != version + 1:
                raise TaskStateMigrationError(
                    f"migration from schema_version {version} did not advance exactly once"
                )
            version = next_version
        return migrated
