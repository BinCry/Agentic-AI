from __future__ import annotations

import json
import math
import unittest
from dataclasses import replace

from coding_agent.storage.observation_store import (
    ObservationConflictError,
    ObservationQuotaError,
    ObservationStore,
    ObservationStoreError,
)
from coding_agent.storage.workspace import WorkspacePaths

from tests.support import WorkspaceTestCase


class ObservationStoreTests(WorkspaceTestCase):
    def make_store(self, **limits: int) -> ObservationStore:
        return ObservationStore(
            WorkspacePaths.create(self.test_root).ensure(), **limits
        )

    def test_reservation_is_durable_before_result_and_completion_round_trips(self) -> None:
        store = self.make_store()
        pending = store.reserve("task-1", "turn-1:write", "repo.create_file", "a" * 64)

        restored = self.make_store().find_by_idempotency_key("task-1", "turn-1:write")

        self.assertEqual(restored, pending)
        self.assertEqual(restored.status, "pending")
        completed = store.complete(
            pending,
            {"success": True, "output": {"path": "new.py"}},
            summary="created new.py",
        )
        self.assertEqual(completed.status, "completed")
        self.assertEqual(store.get_result(completed)["output"]["path"], "new.py")
        self.assertEqual(len(completed.result_sha256 or ""), 64)

    def test_same_idempotency_request_reuses_result_without_duplicate_record(self) -> None:
        store = self.make_store()
        first = store.append(
            "task-1",
            "turn-1:read",
            "repo.read_file",
            "b" * 64,
            {"success": True, "output": "value = 1"},
            summary="read module",
        )

        second = store.append(
            "task-1",
            "turn-1:read",
            "repo.read_file",
            "b" * 64,
            {"success": True, "output": "ignored duplicate"},
            summary="duplicate",
        )

        self.assertEqual(second, first)
        self.assertEqual(len(store.list("task-1")), 1)
        self.assertEqual(store.get_result(second)["output"], "value = 1")

    def test_idempotency_key_cannot_bind_different_request_or_tool(self) -> None:
        store = self.make_store()
        store.reserve("task-1", "turn-1", "git.status", "c" * 64)
        for tool, digest in (("git.diff", "c" * 64), ("git.status", "d" * 64)):
            with self.subTest(tool=tool, digest=digest), self.assertRaises(
                ObservationConflictError
            ):
                store.reserve("task-1", "turn-1", tool, digest)

    def test_item_and_session_quotas_fail_without_completed_artifact(self) -> None:
        store = self.make_store(maximum_item_bytes=32, maximum_session_bytes=64)
        pending = store.reserve("task-1", "turn-1", "repo.read_file", "e" * 64)
        with self.assertRaises(ObservationQuotaError):
            store.complete(
                pending,
                {"output": "x" * 100},
                summary="too large",
            )
        self.assertEqual(store.get(pending.task_id, pending.observation_id).status, "pending")

    def test_summary_is_bounded_and_redacted(self) -> None:
        store = self.make_store(maximum_summary_chars=30)
        record = store.append(
            "task-1",
            "turn-1",
            "git.status",
            "f" * 64,
            {"success": True},
            summary="token=visible-value " + "x" * 100,
        )
        self.assertNotIn("visible-value", record.summary)
        self.assertLessEqual(len(record.summary), 30)

    def test_corrupted_artifact_is_detected_by_digest(self) -> None:
        store = self.make_store()
        record = store.append(
            "task-1",
            "turn-1",
            "git.status",
            "1" * 64,
            {"success": True, "output": "clean"},
            summary="status",
        )
        artifact = self.test_root / str(record.artifact_path)
        payload = json.loads(artifact.read_text(encoding="utf-8"))
        payload["result"]["output"] = "tampered"
        artifact.write_text(json.dumps(payload), encoding="utf-8")

        with self.assertRaisesRegex(ObservationStoreError, "digest mismatch"):
            store.get_result(record)

    def test_custom_runtime_root_round_trips_artifact(self) -> None:
        paths = WorkspacePaths.create(self.test_root, "runtime-state").ensure()
        store = ObservationStore(paths)
        record = store.append(
            "task-1",
            "turn-1",
            "git.status",
            "2" * 64,
            {"success": True},
            summary="status",
        )

        self.assertTrue(str(record.artifact_path).startswith("runtime-state/"))
        self.assertTrue(store.get_result(record)["success"])

    def test_pending_index_reconciles_completed_artifact_after_crash(self) -> None:
        store = self.make_store()
        pending = store.reserve("task-1", "turn-1", "git.status", "3" * 64)
        completed = store.complete(
            pending, {"success": True}, summary="status complete"
        )
        index = store.paths.resolve_runtime_path("observations/task-1/index.json")
        index.write_text(
            json.dumps([pending.to_dict()]), encoding="utf-8"
        )

        restored = self.make_store().find_by_idempotency_key("task-1", "turn-1")

        self.assertEqual(restored, completed)
        self.assertTrue(self.make_store().get_result(restored)["success"])

    def test_artifact_path_must_remain_inside_runtime_root(self) -> None:
        store = self.make_store()
        record = store.append(
            "task-1",
            "turn-1",
            "git.status",
            "4" * 64,
            {"success": True},
            summary="status",
        )
        escaped = replace(record, artifact_path="../outside.json")

        with self.assertRaisesRegex(ObservationStoreError, "path is invalid"):
            store.get_result(escaped)

    def test_result_rejects_noncanonical_or_nonfinite_json(self) -> None:
        invalid_results = (
            {"value": math.nan},
            {"value": (1, 2)},
            {1: "integer key"},
            {"": "empty key"},
        )
        for offset, result in enumerate(invalid_results):
            with self.subTest(result=result):
                store = self.make_store()
                pending = store.reserve(
                    "task-1", f"turn-{offset}", "git.status", f"{offset + 5:x}" * 64
                )
                with self.assertRaisesRegex(ObservationStoreError, "canonical finite"):
                    store.complete(pending, result, summary="invalid")

    def test_count_and_session_quotas_are_enforced(self) -> None:
        count_store = self.make_store(maximum_observations=1)
        count_store.reserve("task-1", "turn-1", "git.status", "9" * 64)
        with self.assertRaisesRegex(ObservationQuotaError, "count"):
            count_store.reserve("task-1", "turn-2", "git.status", "a" * 64)

        session_store = self.make_store(
            maximum_item_bytes=128, maximum_session_bytes=150
        )
        session_store.append(
            "task-2",
            "turn-1",
            "repo.read_file",
            "b" * 64,
            {"output": "x" * 70},
            summary="first",
        )
        second = session_store.reserve(
            "task-2", "turn-2", "repo.read_file", "c" * 64
        )
        with self.assertRaisesRegex(ObservationQuotaError, "session"):
            session_store.complete(
                second, {"output": "y" * 70}, summary="second"
            )

    def test_boolean_limits_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive integers"):
            self.make_store(maximum_observations=True)


if __name__ == "__main__":
    unittest.main()
