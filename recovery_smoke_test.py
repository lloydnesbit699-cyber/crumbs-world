#!/usr/bin/env python3
"""Phase 1 recovery-core smoke test (v1.1 — hardened).

Run:
    python3 recovery_smoke_test.py

Covers:
    - checkpoint -> interruption -> restart -> verified recovery
    - corruption detection
    - rotation: 3 slots kept, newest-first recovery
    - fallback: corrupt latest.json recovers from prev-1.json
    - total corruption: all slots bad -> integrity failure, nothing returned
"""
import json
import tempfile
from pathlib import Path

from crumbs_recovery import CheckpointStore, RecoverySupervisor, KEEP_CHECKPOINTS


def make_state(n: int) -> dict:
    return {
        "map": {
            "width": 3,
            "height": 2,
            "tiles": [[n, 2, 0], [3, 0, 4]],
        },
        "server": {
            "app_version": "5.21.15",
            "last_operation": f"phase-1-smoke-test-{n}",
        },
    }


def corrupt_slot(store: CheckpointStore, slot: int) -> None:
    path = store._slot_path(slot)
    record = json.loads(path.read_text(encoding="utf-8"))
    record["state"]["map"]["tiles"][0][0] = 999
    path.write_text(json.dumps(record), encoding="utf-8")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="crumbs-recovery-") as td:
        root = Path(td)

        # --- basic cycle: checkpoint -> interruption -> restart -> recover ---
        store_a = CheckpointStore(root)
        sup_a = RecoverySupervisor(store_a)
        checkpoint = store_a.checkpoint(make_state(1), label="phase-1-smoke",
                                       source="smoke-test")
        sup_a.healthy(checkpoint["id"])
        sup_a.interruption(RecoverySupervisor.PROCESS_EXIT)

        store_b = CheckpointStore(root)
        sup_b = RecoverySupervisor(store_b)
        recovered, status = sup_b.startup()
        assert status == "PASS", status
        assert recovered is not None
        assert recovered["state"] == make_state(1)
        assert recovered["id"] == checkpoint["id"]
        print("ok: checkpoint -> interruption -> restart -> verified recovery")

        # --- rotation: write KEEP_CHECKPOINTS + 1, oldest must fall off ---
        ids = [checkpoint["id"]]
        for n in (2, 3, 4):
            ids.append(store_b.checkpoint(make_state(n), label=f"rot-{n}",
                                          source="smoke-test")["id"])
        for slot in range(KEEP_CHECKPOINTS):
            assert store_b._slot_path(slot).is_file(), f"slot {slot} missing"
        rec, st = store_b.recover()
        assert st == "PASS" and rec["id"] == ids[-1], "newest must win"
        # ids[0] (state 1) has rotated out; newest three are ids[1..3]
        print("ok: rotation keeps 3 slots, newest wins")

        # --- fallback: corrupt latest, must recover prev-1 ---
        corrupt_slot(store_b, 0)
        rec, st = store_b.recover()
        assert st == "PASS", st
        assert rec["id"] == ids[-2], "must fall back to prev-1"
        assert rec["state"] == make_state(3)
        print("ok: corrupt latest -> falls back to prev-1")

        # --- total corruption: all slots bad -> clean failure ---
        for slot in range(KEEP_CHECKPOINTS):
            corrupt_slot(store_b, slot)
        rec, st = store_b.recover()
        assert rec is None
        assert st == "CHECKPOINT_INTEGRITY_FAILED", st
        print("ok: all slots corrupt -> integrity failure, nothing returned")

    print("PHASE 1 PASS (v1.1)")
    print("checkpoint -> interruption -> restart -> verified recovery")
    print("rotation -> fallback -> corruption detection")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
