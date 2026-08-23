from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from coding_agent.models.task_state import CodingTaskState
from coding_agent.models.validation import ModelValidationError
from coding_agent.storage.task_store import JsonTaskStore
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

    def test_version_1_golden_fixture_preserves_legacy_meaning(self) -> None:
        payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

        state = CodingTaskState.from_dict(payload)

        self.assertEqual(state.task_id, "legacy-v1")
        self.assertEqual(state.original_issue, "Analyze the legacy saved task")
        self.assertEqual(state.schema_version, 1)
        self.assertFalse(state.read_only)

    def test_store_rejects_future_version_without_rewriting_source(self) -> None:
        store = self.make_store()
        payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        payload.update(task_id="future-task", schema_version=999)
        target = self.write_raw_task(store, payload)
        original = target.read_bytes()

        with self.assertRaisesRegex(ModelValidationError, "unsupported schema_version"):
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


if __name__ == "__main__":
    unittest.main()
