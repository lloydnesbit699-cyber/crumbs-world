#!/usr/bin/env python3
"""Phase 1 recovery-core smoke test.

Run:
    python3 recovery_smoke_test.py

This deliberately simulates the server disappearing by creating a checkpoint,
then creating a new supervisor instance and recovering it.
"""
import json
import tempfile
from pathlib import Path

from crumbs_recovery import CheckpointStore, RecoverySupervisor


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="crumbs-recovery-") as td:
        root = Path(td)

        state = {
            "map": {
                "width": 3,
                "height": 2,
                "tiles": [[1, 2, 0], [3, 0, 4]],
            },
            "server": {
                "app_version": "5.21.15",
                "last_operation": "phase-1-smoke-test",
            },
        }

        # Server instance A.
        store_a = CheckpointStore(root)
        sup_a = RecoverySupervisor(store_a)
        checkpoint = store_a.checkpoint(
            state,
            label="phase-1-smoke",
            source="smoke-test",
        )
        sup_a.healthy(checkpoint["id"])

        # Simulate the process disappearing. No checkpoint is deleted.
        sup_a.interruption(RecoverySupervisor.PROCESS_EXIT)

        # Server instance B starts later and sees the same persistent store.
        store_b = CheckpointStore(root)
        sup_b = RecoverySupervisor(store_b)
        recovered, status = sup_b.startup()

        assert status == "PASS", status
        assert recovered is not None
        assert recovered["state"] == state
        assert recovered["id"] == checkpoint["id"]

        # Verify corruption is detected rather than silently accepted.
        latest = store_b.latest_path
        record = json.loads(latest.read_text(encoding="utf-8"))
        record["state"]["map"]["tiles"][0][0] = 999
        latest.write_text(json.dumps(record), encoding="utf-8")

        corrupted, corrupt_status = store_b.recover()
        assert corrupted is None
        assert corrupt_status == "CHECKPOINT_INTEGRITY_FAILED"

    print("PHASE 1 PASS")
    print("checkpoint -> interruption -> restart -> verified recovery -> corruption detection")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
