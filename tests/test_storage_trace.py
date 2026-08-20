from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from coding_agent.models.task_state import CodingTaskState
from coding_agent.observability.trace import JsonlTraceWriter, TraceEvent
from coding_agent.storage.task_store import JsonTaskStore, TaskNotFoundError
from coding_agent.storage.workspace import WorkspacePaths, WorkspacePolicyError

from tests.support import WorkspaceTestCase


class SecretBearingObject:
    def __repr__(self) -> str:
        return "token=OBJECT_SECRET"


class StorageAndTraceTests(WorkspaceTestCase):
    def make_paths(self) -> WorkspacePaths:
        return WorkspacePaths.create(self.test_root).ensure()

    def test_runtime_and_resolved_paths_stay_inside_workspace(self) -> None:
        paths = self.make_paths()
        self.assertTrue(paths.runtime_root.is_relative_to(self.test_root))
        with self.assertRaisesRegex(WorkspacePolicyError, "escapes workspace"):
            paths.resolve_workspace_path("../escape.txt")

    def test_absolute_runtime_outside_workspace_is_rejected(self) -> None:
        outside = self.test_root.parent / "outside-runtime"
        with self.assertRaisesRegex(WorkspacePolicyError, "inside workspace"):
            WorkspacePaths.create(self.test_root, outside)

    def test_task_directory_symlink_cannot_redirect_storage(self) -> None:
        paths = self.make_paths()
        outside = self.test_root.parent / f"outside-{self.test_root.name}"
        outside.mkdir()
        try:
            task_link = paths.runtime_root / "tasks"
            try:
                os.symlink(outside, task_link, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"directory symlinks unavailable: {exc}")
            with self.assertRaisesRegex(WorkspacePolicyError, "escapes runtime root"):
                paths.task_path("redirected")
        finally:
            outside.rmdir()

    @unittest.skipUnless(Path("D:/").drive.upper() == "D:", "Windows drive policy test")
    def test_forbidden_c_drive_is_rejected_without_writing(self) -> None:
        with self.assertRaisesRegex(WorkspacePolicyError, "forbidden drive C"):
            WorkspacePaths.create(self.test_root, "C:/unsafe-coding-agent-runtime")

    def test_atomic_store_round_trip_and_safe_ids(self) -> None:
        store = JsonTaskStore(self.make_paths())
        state = CodingTaskState.create("Issue", "repo", task_id="persisted")
        target = store.save(state)
        self.assertTrue(target.is_file())
        self.assertEqual(store.load("persisted").to_dict(), state.to_dict())
        self.assertEqual(store.list_task_ids(), ("persisted",))
        with self.assertRaises(ValueError):
            store.load("../escape")
        with self.assertRaises(TaskNotFoundError):
            store.load("missing")

    def test_precreated_temporary_symlink_is_never_followed(self) -> None:
        paths = self.make_paths()
        store = JsonTaskStore(paths)
        state = CodingTaskState.create("Issue", "repo", task_id="collision")
        task_dir = paths.resolve_runtime_path("tasks")
        task_dir.mkdir()
        outside = self.test_root.parent / f"outside-{self.test_root.name}.json"
        outside.write_text("do-not-overwrite", encoding="utf-8")
        collision = task_dir / f"collision.json.{os.getpid()}.fixed.tmp"
        try:
            try:
                os.symlink(outside, collision)
            except OSError as exc:
                self.skipTest(f"file symlinks unavailable: {exc}")
            with patch(
                "coding_agent.storage.task_store.uuid4",
                return_value=SimpleNamespace(hex="fixed"),
            ):
                with self.assertRaisesRegex(RuntimeError, "exclusive"):
                    store.save(state)
            self.assertEqual(outside.read_text(encoding="utf-8"), "do-not-overwrite")
        finally:
            outside.unlink(missing_ok=True)

    def test_trace_is_jsonl_and_redacts_nested_secrets(self) -> None:
        paths = self.make_paths()
        writer = JsonlTraceWriter(paths)
        writer.append(
            TraceEvent(
                task_id="trace-1",
                workflow_state="TESTING",
                action="test",
                success=True,
                latency_ms=3,
                input_metadata={
                    "api_key": "secret",
                    "nested": {"authorization": "Bearer x"},
                    "object": SecretBearingObject(),
                },
                result_metadata={
                    "count": 1,
                    "message": "Authorization: Bearer metadata-secret",
                },
                error="request failed with token=visible-value and Authorization: Bearer abc123",
            )
        )
        payload = json.loads(paths.trace_path("trace-1").read_text(encoding="utf-8"))
        self.assertEqual(payload["input_metadata"]["api_key"], "[REDACTED]")
        self.assertEqual(payload["input_metadata"]["nested"]["authorization"], "[REDACTED]")
        self.assertNotIn("visible-value", payload["error"])
        self.assertNotIn("abc123", payload["error"])
        self.assertNotIn("metadata-secret", payload["result_metadata"]["message"])
        self.assertNotIn("OBJECT_SECRET", payload["input_metadata"]["object"])

    def test_trace_output_size_is_bounded(self) -> None:
        writer = JsonlTraceWriter(self.make_paths(), maximum_event_bytes=200)
        with self.assertRaisesRegex(ValueError, "output-size"):
            writer.append(
                TraceEvent(
                    task_id="trace-large",
                    workflow_state="TESTING",
                    action="test",
                    success=False,
                    latency_ms=1,
                    input_metadata={"content": "x" * 500},
                )
            )


if __name__ == "__main__":
    unittest.main()
