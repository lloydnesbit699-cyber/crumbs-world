#!/usr/bin/env python3
"""Ensure server exception logs are safe, persistent, and repairable."""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import crumbs_hud as hud


class RuntimeErrorLedgerTest(unittest.TestCase):
    def test_known_height_grid_failure_has_safe_repair_record(self):
        with tempfile.TemporaryDirectory(prefix="crumbs-runtime-ledger-") as temp:
            log_path = os.path.join(temp, "runtime-errors.jsonl")

            def cell_height():
                raise TypeError("unhashable type: dict; never persist this detail")

            try:
                cell_height()
            except TypeError as exc:
                with mock.patch.object(hud, "_RUNTIME_ERROR_LOG", log_path):
                    row = hud._record_runtime_error(
                        "GET", "/api/height-grid?secret=do-not-log", exc,
                        sys.exc_info()[2])

            self.assertTrue(os.path.isfile(log_path))
            self.assertEqual(row["code"], "object_instance_shape")
            self.assertEqual(row["path"], "/api/height-grid")
            self.assertIn("core.obj_tid", row["fix"])
            with open(log_path, encoding="utf-8") as stream:
                raw = stream.read()
            saved = json.loads(raw)
            self.assertEqual(saved["id"], row["id"])
            self.assertEqual(saved["version"], hud.APP_VERSION)
            self.assertNotIn("do-not-log", raw)
            self.assertNotIn("unhashable type", raw)


if __name__ == "__main__":
    unittest.main()
