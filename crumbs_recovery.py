#!/usr/bin/env python3
"""
Crumbs Phase 1 recovery core.

Purpose:
    Keep a small, verified last-known-good checkpoint independent of the
    server process.  The execution environment may disappear; the checkpoint
    survives it.

Phase 1 intentionally does NOT restart processes or delete/overwrite project
data.  It only provides:
    - atomic checkpoint writes
    - SHA-256 integrity verification
    - latest-checkpoint discovery
    - explicit recovery of a verified checkpoint
    - an interruption/recovery record

Stdlib only.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


CHECKPOINT_VERSION = 1
DEFAULT_DIRNAME = ".crumbs_recovery"


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


class CheckpointStore:
    """Persistent, non-destructive checkpoint storage."""

    def __init__(self, root: str | os.PathLike[str], directory: str = DEFAULT_DIRNAME):
        self.root = Path(root)
        self.directory = self.root / directory
        self.directory.mkdir(parents=True, exist_ok=True)

    @property
    def latest_path(self) -> Path:
        return self.directory / "latest.json"

    @property
    def journal_path(self) -> Path:
        return self.directory / "recovery-journal.jsonl"

    def _atomic_write(self, path: Path, payload: bytes) -> None:
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=str(path.parent),
        )
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(payload)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_name, path)
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    def checkpoint(
        self,
        state: Dict[str, Any],
        *,
        label: str = "manual",
        source: str = "server",
    ) -> Dict[str, Any]:
        if not isinstance(state, dict):
            raise TypeError("checkpoint state must be a dict")

        now = time.time()
        record = {
            "checkpoint_version": CHECKPOINT_VERSION,
            "id": f"CP-{time.strftime('%Y%m%d-%H%M%S', time.localtime(now))}-{time.time_ns() % 1000000:06d}",
            "created_at": now,
            "label": str(label)[:80],
            "source": str(source)[:80],
            "state": state,
        }
        record["state_sha256"] = _sha256(state)

        self._atomic_write(
            self.latest_path,
            _canonical_json(record) + b"\n",
        )
        self.record_event(
            "CHECKPOINT_CREATED",
            checkpoint_id=record["id"],
            state_sha256=record["state_sha256"],
        )
        return record

    def load_verified(self) -> Tuple[Optional[Dict[str, Any]], str]:
        if not self.latest_path.is_file():
            return None, "NO_CHECKPOINT"

        try:
            record = json.loads(self.latest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None, "CHECKPOINT_UNREADABLE"

        if record.get("checkpoint_version") != CHECKPOINT_VERSION:
            return None, "CHECKPOINT_VERSION_UNSUPPORTED"

        state = record.get("state")
        expected = record.get("state_sha256")
        if not isinstance(state, dict) or not isinstance(expected, str):
            return None, "CHECKPOINT_MALFORMED"

        actual = _sha256(state)
        if not hmac.compare_digest(actual, expected):
            return None, "CHECKPOINT_INTEGRITY_FAILED"

        return record, "PASS"

    def recover(self) -> Tuple[Optional[Dict[str, Any]], str]:
        record, status = self.load_verified()
        if record is None:
            self.record_event("RECOVERY_FAILED", reason=status)
            return None, status

        self.record_event(
            "RECOVERY_VERIFIED",
            checkpoint_id=record["id"],
            state_sha256=record["state_sha256"],
        )
        return record, "PASS"

    def record_event(self, event: str, **fields: Any) -> None:
        entry = {
            "timestamp": time.time(),
            "event": str(event),
            **fields,
        }
        line = _canonical_json(entry) + b"\n"

        # Journal entries are append-only for Phase 1.  A partial last line
        # is harmless; future phases can add journal compaction/rotation.
        with open(self.journal_path, "ab") as fh:
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())


class RecoverySupervisor:
    """Small state machine for Phase 1; no automatic destructive actions."""

    CLEAN_SHUTDOWN = "CLEAN_SHUTDOWN"
    IOS_SUSPENSION = "IOS_SUSPENSION"
    PROCESS_EXIT = "PROCESS_EXIT"
    CRASH = "CRASH"
    DEPENDENCY_FAILURE = "DEPENDENCY_FAILURE"
    CORRUPTED_STATE = "CORRUPTED_STATE"
    UNKNOWN_INTERRUPTION = "UNKNOWN_INTERRUPTION"

    def __init__(self, store: CheckpointStore):
        self.store = store

    def interruption(self, reason: str) -> None:
        self.store.record_event(
            "SERVER_INTERRUPTION",
            reason=str(reason),
        )

    def startup(self) -> Tuple[Optional[Dict[str, Any]], str]:
        record, status = self.store.recover()
        self.store.record_event(
            "RECOVERY_STARTUP",
            status=status,
            checkpoint_id=record.get("id") if record else None,
        )
        return record, status

    def healthy(self, checkpoint_id: Optional[str] = None) -> None:
        self.store.record_event(
            "SERVER_HEALTHY",
            checkpoint_id=checkpoint_id,
        )
