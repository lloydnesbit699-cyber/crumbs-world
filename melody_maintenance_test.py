import json
import os
import tempfile
import unittest

import melody_agent


class MelodyMaintenanceTests(unittest.TestCase):
    def test_tasks_persist_and_are_private_per_player(self):
        with tempfile.TemporaryDirectory() as root:
            task = melody_agent.task_create(
                root, "alice", "Repair map loading", "Check saved layers.",
                "repair")
            self.assertEqual(melody_agent.task_list(root, "alice"), [task])
            self.assertEqual(melody_agent.task_list(root, "bobby"), [])
            self.assertTrue(os.path.isfile(
                os.path.join(root, "vaults", "alice", "melody", "tasks.json")))

    def test_attempt_history_blocks_third_repeat_but_keeps_task_open(self):
        with tempfile.TemporaryDirectory() as root:
            task = melody_agent.task_create(root, "alice", "Fix map load",
                                            kind="repair")
            for outcome in ("failed once", "failed twice"):
                task = melody_agent.task_record_attempt(
                    root, "alice", task["id"], "rebuild the sidecar", outcome)
            with self.assertRaisesRegex(ValueError, "failed twice"):
                melody_agent.task_record_attempt(
                    root, "alice", task["id"], " Rebuild   the sidecar ",
                    "repeat")
            task = melody_agent.task_record_attempt(
                root, "alice", task["id"], "validate layers before load",
                "different strategy recorded")
            self.assertEqual(task["status"], "in_progress")
            self.assertEqual(len(task["attempts"]), 3)
            self.assertEqual(
                [e["status"] for e in task["status_history"]],
                ["open", "in_progress"])

    def test_status_and_model_tools_use_the_same_private_ledger(self):
        with tempfile.TemporaryDirectory() as root:
            created = json.loads(melody_agent.run_tool(
                root, "alice", "task_create",
                {"title": "Build the garden", "kind": "build"}))
            updated = json.loads(melody_agent.run_tool(
                root, "alice", "task_set_status",
                {"task_id": created["id"], "status": "done"}))
            listed = json.loads(melody_agent.run_tool(
                root, "alice", "task_list", {}))
            self.assertEqual(updated["status"], "done")
            self.assertEqual(listed[0]["id"], created["id"])
            self.assertEqual(listed[0]["status_history"][-1]["status"], "done")

    def test_invalid_task_kind_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError, "task kind"):
                melody_agent.task_create(root, "alice", "bad kind",
                                         kind="deployment bypass")

    def test_task_keeps_accumulating_distinct_attempts(self):
        with tempfile.TemporaryDirectory() as root:
            task = melody_agent.task_create(root, "alice", "Keep investigating",
                                            kind="repair")
            for i in range(45):
                task = melody_agent.task_record_attempt(
                    root, "alice", task["id"], f"distinct strategy {i}",
                    f"result {i}")
            self.assertEqual(len(task["attempts"]), 45)
            self.assertEqual(task["status"], "in_progress")

    def test_diagnostics_tool_is_only_offered_to_owner(self):
        regular = {t["function"]["name"]
                   for t in melody_agent.tools_for_session(False)}
        owner = {t["function"]["name"]
                 for t in melody_agent.tools_for_session(True)}
        self.assertNotIn("diagnose_system", regular)
        self.assertIn("diagnose_system", owner)
        self.assertIn("task_create", regular)

    def test_corrupt_task_ledger_is_reported(self):
        with tempfile.TemporaryDirectory() as root:
            task_path = melody_agent._tasks_path(root, "alice")
            with open(task_path, "w", encoding="utf-8") as f:
                f.write("{not json")
            with self.assertRaises(json.JSONDecodeError):
                melody_agent.task_list(root, "alice")


if __name__ == "__main__":
    unittest.main()
