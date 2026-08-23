from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from coding_agent.models.run_accounting import RunBudget, UsageLedger
from coding_agent.models.task_state import CodingTaskState
from coding_agent.models.validation import ModelValidationError
from coding_agent.storage.checkpoint_store import CheckpointStore
from coding_agent.storage.task_store import JsonTaskStore
from coding_agent.storage.task_state_migrations import (
    CURRENT_TASK_SCHEMA_VERSION,
    TaskStateMigrationError,
    TaskStateMigrator,
)
from coding_agent.storage.workspace import WorkspacePaths

from tests.support import WorkspaceTestCase


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "task_states" / "version-1-task.json"


class TaskStateCompatibilityTests(WorkspaceTestCase):
    def make_store(self) -> JsonTaskStore:
        return JsonTaskStore(WorkspacePaths.create(self.test_root).ensure())

    def write_raw_task(self, store: JsonTaskStore, payload: dict[str, object]) -> Path:
        target = store.paths.task_path(str(payload["task_id"]))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return target

    def test_version_1_golden_fixture_migrates_without_mutating_input(self) -> None:
        payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        original = deepcopy(payload)

        migrated = TaskStateMigrator().migrate(payload)
        state = CodingTaskState.from_dict(migrated)

        self.assertEqual(payload, original)
        self.assertEqual(state.task_id, "legacy-v1")
        self.assertEqual(state.original_issue, "Analyze the legacy saved task")
        self.assertEqual(state.schema_version, CURRENT_TASK_SCHEMA_VERSION)
        self.assertFalse(state.read_only)
        self.assertEqual(state.run_budget, RunBudget())
        self.assertEqual(state.usage_ledger, UsageLedger())
        self.assertIsNone(state.project_profile)
        self.assertEqual(TaskStateMigrator().migrate(migrated), migrated)

    def test_version_2_state_adds_empty_project_profile(self) -> None:
        payload = CodingTaskState.create("Issue", "repo", task_id="legacy-v2").to_dict()
        payload["schema_version"] = 2
        payload.pop("project_profile")

        migrated = TaskStateMigrator().migrate(payload)

        self.assertEqual(migrated["schema_version"], CURRENT_TASK_SCHEMA_VERSION)
        self.assertIsNone(migrated["project_profile"])

    def test_legacy_usage_ledger_gains_explicit_known_call_counts(self) -> None:
        state = CodingTaskState.create("Issue", "repo", task_id="legacy-usage")
        state.usage_ledger.record(
            provider="legacy",
            model="fixture",
            input_tokens=4,
            output_tokens=2,
            total_tokens=6,
            latency_ms=3,
        )
        payload = state.to_dict()
        payload["schema_version"] = 3
        ledger = payload["usage_ledger"]
        assert isinstance(ledger, dict)
        for field in (
            "usage_known_calls",
            "usage_unknown_calls",
            "latency_known_calls",
            "input_tokens_known_calls",
            "output_tokens_known_calls",
            "reasoning_tokens_known_calls",
            "total_tokens_known_calls",
        ):
            ledger.pop(field)

        restored = CodingTaskState.from_dict(TaskStateMigrator().migrate(payload))

        self.assertEqual(restored.usage_ledger.usage_known_calls, 1)
        self.assertEqual(restored.usage_ledger.usage_unknown_calls, 0)
        self.assertEqual(restored.usage_ledger.total_tokens_known_calls, 1)

    def test_load_then_save_creates_one_immutable_legacy_backup(self) -> None:
        store = self.make_store()
        payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        target = self.write_raw_task(store, payload)
        original = target.read_bytes()

        state = store.load("legacy-v1")
        self.assertEqual(state.schema_version, CURRENT_TASK_SCHEMA_VERSION)
        self.assertEqual(target.read_bytes(), original)

        store.save(state)
        backup = store.paths.resolve_runtime_path("task-backups/legacy-v1.v1.json")
        self.assertEqual(backup.read_bytes(), original)
        store.save(state)
        self.assertEqual(backup.read_bytes(), original)
        self.assertEqual(len(list(backup.parent.glob("legacy-v1.*.json"))), 1)

    def test_conflicting_legacy_backup_blocks_state_replacement(self) -> None:
        store = self.make_store()
        payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        target = self.write_raw_task(store, payload)
        backup = store.paths.resolve_runtime_path("task-backups/legacy-v1.v1.json")
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_text("conflicting backup", encoding="utf-8")
        state = store.load("legacy-v1")
        original = target.read_bytes()

        with self.assertRaisesRegex(TaskStateMigrationError, "backup differs"):
            store.save(state)

        self.assertEqual(target.read_bytes(), original)

    def test_store_rejects_future_version_without_rewriting_source(self) -> None:
        store = self.make_store()
        payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        payload.update(task_id="future-task", schema_version=999)
        target = self.write_raw_task(store, payload)
        original = target.read_bytes()

        with self.assertRaisesRegex(TaskStateMigrationError, "newer than supported"):
            store.load("future-task")

        self.assertEqual(target.read_bytes(), original)

    def test_failed_atomic_replace_preserves_last_valid_state(self) -> None:
        store = self.make_store()
        state = CodingTaskState.create("Original issue", "repo", task_id="atomic-task")
        target = store.save(state)
        original = target.read_bytes()
        state.original_issue = "Updated issue"

        with patch("coding_agent.storage.task_store.os.replace", side_effect=OSError("injected")):
            with self.assertRaisesRegex(OSError, "injected"):
                store.save(state)

        self.assertEqual(target.read_bytes(), original)
        self.assertEqual(store.load("atomic-task").original_issue, "Original issue")
        self.assertEqual(list(target.parent.glob("*.tmp")), [])

    def test_legacy_checkpoint_restores_through_same_migration_chain(self) -> None:
        paths = WorkspacePaths.create(self.test_root).ensure()
        payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        payload["task_id"] = "legacy-checkpoint"
        target = paths.resolve_runtime_path(
            "checkpoints/legacy-checkpoint/checkpoint-0000-0001.json"
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"state": payload}), encoding="utf-8")

        state = CheckpointStore(paths).restore(
            "legacy-checkpoint", "checkpoint-0000-0001"
        )

        self.assertEqual(state.schema_version, CURRENT_TASK_SCHEMA_VERSION)
        self.assertEqual(state.original_issue, "Analyze the legacy saved task")

    def test_run_accounting_validates_records_merges_and_round_trips(self) -> None:
        state = CodingTaskState.create("Issue", "repo", task_id="accounting")
        state.run_budget = RunBudget(
            maximum_model_tokens=100,
            maximum_command_seconds=30,
            maximum_output_bytes=4096,
            maximum_wall_clock_seconds=120,
        )
        state.usage_ledger.record(
            provider="openrouter",
            model="stealth/ox-alpha",
            input_tokens=10,
            output_tokens=5,
            reasoning_tokens=2,
            latency_ms=80,
        )
        other = UsageLedger()
        other.record(
            provider="openai",
            model="gpt-test",
            input_tokens=2,
            output_tokens=3,
            total_tokens=5,
            latency_ms=20,
        )
        state.usage_ledger.merge(other)

        restored = CodingTaskState.from_dict(state.to_dict())

        self.assertEqual(restored.run_budget, state.run_budget)
        self.assertEqual(restored.usage_ledger.total_tokens, 20)
        self.assertEqual(restored.usage_ledger.model_calls, 2)
        self.assertEqual(restored.usage_ledger.usage_known_calls, 2)
        self.assertEqual(restored.usage_ledger.providers, ["openai", "openrouter"])
        with self.assertRaisesRegex(ModelValidationError, "maximum_model_tokens"):
            RunBudget(maximum_model_tokens=True).validate()
        with self.assertRaisesRegex(ModelValidationError, "input_tokens"):
            UsageLedger().record(
                provider="openrouter",
                model="stealth/ox-alpha",
                input_tokens="invalid",  # type: ignore[arg-type]
            )

    def test_unknown_usage_is_counted_without_inventing_tokens(self) -> None:
        ledger = UsageLedger()

        ledger.record(
            provider="fixture",
            model="unknown-usage-model",
            model_calls=2,
            usage_known_calls=0,
            usage_unknown_calls=2,
            latency_known_calls=2,
            input_tokens_known_calls=0,
            output_tokens_known_calls=0,
            reasoning_tokens_known_calls=0,
            total_tokens_known_calls=0,
            latency_ms=12,
            total_tokens=0,
        )

        self.assertEqual(ledger.model_calls, 2)
        self.assertEqual(ledger.usage_unknown_calls, 2)
        self.assertEqual(ledger.total_tokens, 0)
        self.assertEqual(ledger.total_tokens_known_calls, 0)


if __name__ == "__main__":
    unittest.main()
