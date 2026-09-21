#!/usr/bin/env python3
"""
Crumbs Phase 1 recovery core (v1.1 — hardened).

Purpose:
    Keep small, verified last-known-good checkpoints independent of the
    server process.  The execution environment may disappear; the checkpoints
    survive it.

Phase 1 intentionally does NOT restart processes or delete/overwrite project
data.  It only provides:
    - atomic checkpoint writes with rotation (latest + 2 backups)
    - SHA-256 integrity verification with fallback to older checkpoints
    - latest-checkpoint discovery
    - explicit recovery of a verified checkpoint
    - an interruption/recovery record
    - inter-process file locking (safe against double-launched servers)
    - journal rotation (bounded disk use on phones)

Stdlib only.
"""
from __future__ import annotations

import contextlib
import fcntl
import hashlib
import hmac
import json
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterator, Optional, Tuple


CHECKPOINT_VERSION = 1
DEFAULT_DIRNAME = ".crumbs_recovery"

# How many checkpoint slots to keep: slot 0 is newest, older slots are
# fallbacks if a newer checkpoint fails verification.
KEEP_CHECKPOINTS = 3

# Journal bounds: rotate when either is exceeded.
JOURNAL_MAX_BYTES = 1_048_576  # 1 MiB
JOURNAL_MAX_LINES = 1000
JOURNAL_KEEP_LINES = 500  # lines retained after a rotation


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _new_checkpoint_id() -> str:
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime(time.time()))
    return f"CP-{stamp}-{uuid.uuid4().hex[:8]}"


class CheckpointStore:
    """Persistent, non-destructive checkpoint storage."""

    def __init__(
        self,
        root: Optional[str | os.PathLike[str]] = None,
        directory: str = DEFAULT_DIRNAME,
    ):
        if root is None:
            # Anchor to this file's location, never to the process CWD.
            # On a-Shell/iOS the working directory is unreliable.
            root = Path(__file__).resolve().parent
        self.root = Path(root)
        self.directory = self.root / directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self._lock_depth = 0
        self._lock_fh = None

    # ------------------------------------------------------------------
    # locking
    # ------------------------------------------------------------------
    @contextlib.contextmanager
    def _locked(self) -> Iterator[None]:
        """Reentrant exclusive lock guarding checkpoint + journal writes."""
        if self._lock_depth == 0:
            self._lock_fh = open(self.directory / ".lock", "a+b")
            fcntl.flock(self._lock_fh.fileno(), fcntl.LOCK_EX)
        self._lock_depth += 1
        try:
            yield
        finally:
            self._lock_depth -= 1
            if self._lock_depth == 0 and self._lock_fh is not None:
                try:
                    fcntl.flock(self._lock_fh.fileno(), fcntl.LOCK_UN)
                finally:
                    self._lock_fh.close()
                    self._lock_fh = None

    # ------------------------------------------------------------------
    # paths
    # ------------------------------------------------------------------
    def _slot_path(self, slot: int) -> Path:
        if slot == 0:
            return self.directory / "latest.json"
        return self.directory / f"prev-{slot}.json"

    @property
    def latest_path(self) -> Path:
        return self._slot_path(0)

    @property
    def journal_path(self) -> Path:
        return self.directory / "recovery-journal.jsonl"

    # ------------------------------------------------------------------
    # writes
    # ------------------------------------------------------------------
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
            "id": _new_checkpoint_id(),
            "created_at": now,
            "label": str(label)[:80],
            "source": str(source)[:80],
            "state": state,
        }
        record["state_sha256"] = _sha256(state)
        payload = _canonical_json(record) + b"\n"

        with self._locked():
            # Rotate: prev-2 <- prev-1 <- latest, then write new latest.
            # A corrupt new state can never destroy all older good copies.
            for slot in range(KEEP_CHECKPOINTS - 1, 0, -1):
                src = self._slot_path(slot - 1)
                dst = self._slot_path(slot)
                if src.is_file():
                    os.replace(src, dst)
            self._atomic_write(self._slot_path(0), payload)
            self.record_event(
                "CHECKPOINT_CREATED",
                checkpoint_id=record["id"],
                state_sha256=record["state_sha256"],
            )
        return record

    # ------------------------------------------------------------------
    # reads
    # ------------------------------------------------------------------
    def _verify_path(self, path: Path) -> Tuple[Optional[Dict[str, Any]], str]:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
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

    def load_verified(self) -> Tuple[Optional[Dict[str, Any]], str]:
        """Return the newest verified checkpoint, falling back to older slots."""
        last_status = "NO_CHECKPOINT"
        for slot in range(KEEP_CHECKPOINTS):
            path = self._slot_path(slot)
            if not path.is_file():
                continue
            record, status = self._verify_path(path)
            if record is not None:
                if slot > 0:
                    self.record_event(
                        "RECOVERY_FALLBACK",
                        slot=slot,
                        checkpoint_id=record["id"],
                    )
                return record, "PASS"
            last_status = status
            self.record_event(
                "CHECKPOINT_SLOT_FAILED",
                slot=slot,
                reason=status,
            )
        return None, last_status

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

    # ------------------------------------------------------------------
    # journal
    # ------------------------------------------------------------------
    def _maybe_rotate_journal(self) -> None:
        path = self.journal_path
        if not path.is_file():
            return
        try:
            size = path.stat().st_size
        except OSError:
            return
        if size <= JOURNAL_MAX_BYTES:
            # Cheap path: only count lines when size is already suspicious.
            return
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, ValueError):
            return
        if len(lines) <= JOURNAL_MAX_LINES and size <= JOURNAL_MAX_BYTES:
            return
        keep = lines[-JOURNAL_KEEP_LINES:]
        tmp = path.with_suffix(".jsonl.rot")
        try:
            tmp.write_text("\n".join(keep) + "\n", encoding="utf-8")
            os.replace(tmp, path)
        except OSError:
            try:
                tmp.unlink()
            except OSError:
                pass

    def record_event(self, event: str, **fields: Any) -> None:
        entry = {
            "timestamp": time.time(),
            "event": str(event),
            **fields,
        }
        line = _canonical_json(entry) + b"\n"

        with self._locked():
            self._maybe_rotate_journal()
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
