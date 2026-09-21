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
    # phase 3: read-only status for the HUD (no journal side effects)
    # ------------------------------------------------------------------
    def slot_info(self) -> list:
        """Per-slot inventory for the HUD. Verifies in place; writes nothing."""
        out = []
        for slot in range(KEEP_CHECKPOINTS):
            path = self._slot_path(slot)
            info: Dict[str, Any] = {
                "slot": slot,
                "name": path.name,
                "present": path.is_file(),
                "status": "EMPTY",
                "record": None,
            }
            if path.is_file():
                record, status = self._verify_path(path)
                info["status"] = "PASS" if record is not None else status
                if record is not None:
                    info["record"] = {
                        "id": record.get("id"),
                        "created_at": record.get("created_at"),
                        "label": record.get("label"),
                        "source": record.get("source"),
                    }
            out.append(info)
        return out

    def journal_tail(self, n: int = 50) -> list:
        """Last n journal entries, newest last. Never raises."""
        try:
            n = max(1, min(200, int(n)))
        except (TypeError, ValueError):
            n = 50
        try:
            lines = self.journal_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        out = []
        for line in lines[-n:]:
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
        return out

    # ------------------------------------------------------------------
    # phase 3B: last recovery report (HUD reads; server writes at startup)
    # ------------------------------------------------------------------
    @property
    def report_path(self) -> Path:
        return self.directory / "last_report.json"

    def write_report(self, report: Dict[str, Any]) -> None:
        """Atomically persist the latest RECOVERY_REPORT for the HUD."""
        with self._locked():
            self._atomic_write(self.report_path, _canonical_json(report) + b"\n")

    def read_report(self) -> Optional[Dict[str, Any]]:
        try:
            return json.loads(self.report_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def resolve_server_responds(self) -> bool:
        """Flip the persisted report's SERVER_RESPONDS step pending -> pass.

        Reporting only: touches last_report.json and nothing else — no world
        state, no checkpoint, no recovery action, no risk change. Idempotent:
        only a step still marked pending transitions. Never raises: a
        persistence failure must be logged by the caller, never fatal.
        Returns True when a transition was persisted."""
        try:
            report = self.read_report()
            if not isinstance(report, dict):
                return False
            steps = (report.get("verification") or {}).get("steps") or []
            changed = False
            for s in steps:
                if (isinstance(s, dict) and s.get("name") == STEP_SERVER_RESPONDS
                        and s.get("status") == "pending"):
                    s["status"] = "pass"
                    s["detail"] = "first request served"
                    changed = True
            if not changed:
                return False
            with self._locked():
                self._atomic_write(self.report_path, _canonical_json(report) + b"\n")
            return True
        except Exception:
            return False

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


# ======================================================================
# Phase 3B — Recovery Intelligence & Guardrails
#
# Observe / classify / assess / verify / record. Nothing in this section
# deletes, overwrites, or grants itself more authority. The only actions
# the system may take are the ones the risk model explicitly permits,
# and a repeated failure can only NARROW what is permitted, never widen.
# ======================================================================

# ---- failure/success library: outcome taxonomy (definitions first) ----
RECOVERY_SUCCESS = "RECOVERY_SUCCESS"  # valid state produced AND independently verified
RECOVERY_PARTIAL = "RECOVERY_PARTIAL"  # some state restored, completeness unverifiable
RECOVERY_FAILED = "RECOVERY_FAILED"    # no verified valid state produced
RECOVERY_UNSAFE = "RECOVERY_UNSAFE"    # action withheld: could harm known-good state
RECOVERY_UNKNOWN = "RECOVERY_UNKNOWN"  # validity of the result cannot be established

RECOVERY_OUTCOME_DEFS = {
    RECOVERY_SUCCESS: "a recovery or repair operation that produces a valid state "
                      "and passes independent verification",
    RECOVERY_PARTIAL: "some state is restored, but the complete expected state "
                      "cannot be independently verified",
    RECOVERY_FAILED: "a recovery or repair operation that does not produce a "
                     "verified valid state",
    RECOVERY_UNSAFE: "a proposed action could destroy or compromise a known-good "
                     "state, so the action must be withheld",
    RECOVERY_UNKNOWN: "the system cannot establish whether the resulting state "
                      "is valid",
}

# ---- interruption taxonomy ----
# IOS_SUSPENSION and PROCESS_EXIT are defined but intentionally UNUSED in v1:
# with only a heartbeat and shutdown markers, a suspension-then-kill is
# indistinguishable from a crash. Unknown remains unknown — see
# classify_interruption(). They are reserved for a future explicit channel.
CLEAN_SHUTDOWN = "CLEAN_SHUTDOWN"
IOS_SUSPENSION = "IOS_SUSPENSION"
PROCESS_EXIT = "PROCESS_EXIT"
CRASH = "CRASH"  # sudden death: kill -9 and segfault are indistinguishable here
DEPENDENCY_FAILURE = "DEPENDENCY_FAILURE"
CORRUPTED_STATE = "CORRUPTED_STATE"
UNKNOWN_INTERRUPTION = "UNKNOWN_INTERRUPTION"

# ---- interruption evidence files (live beside checkpoints; gitignored) ----
HEARTBEAT_NAME = "heartbeat.json"
DIRTY_NAME = "dirty.flag"
CLEAN_NAME = "clean.shutdown"
HEARTBEAT_INTERVAL_S = 5.0
HEARTBEAT_STALE_AFTER_S = 15.0  # 3x the interval: was alive moments ago, then gone

# ---- risk model ----
RISK_LOW = "LOW"
RISK_MEDIUM = "MEDIUM"
RISK_HIGH = "HIGH"
RISK_CRITICAL = "CRITICAL"
RISK_LEVELS = (RISK_LOW, RISK_MEDIUM, RISK_HIGH, RISK_CRITICAL)

# Permitted actions per level. Authority never grows with risk: the
# destructive-capable subset ({RESTORE_VERIFIED_CHECKPOINT}) is
# {} -> {RESTORE} -> {RESTORE} -> {} across LOW/MEDIUM/HIGH/CRITICAL.
# Notices get louder with risk, but no new power is granted.
PERMITTED_ACTIONS = {
    RISK_LOW: ("NORMAL_STARTUP",),
    RISK_MEDIUM: ("NORMAL_STARTUP", "RESTORE_VERIFIED_CHECKPOINT", "LOG_NOTICE"),
    RISK_HIGH: ("NORMAL_STARTUP", "RESTORE_VERIFIED_CHECKPOINT",
                "PRESERVE_EVIDENCE", "INTERVENTION_NOTICE"),
    RISK_CRITICAL: ("WITHHOLD_ACTION", "PRESERVE_EVIDENCE", "INTERVENTION_REQUIRED"),
}
_DESTRUCTIVE_ACTIONS = frozenset({"RESTORE_VERIFIED_CHECKPOINT"})


def read_heartbeat(store: "CheckpointStore") -> Optional[Dict[str, Any]]:
    """Return the last heartbeat with its age in seconds, or None. Never raises."""
    try:
        raw = json.loads((store.directory / HEARTBEAT_NAME).read_text(encoding="utf-8"))
        ts = float(raw.get("ts", 0))
    except (OSError, ValueError, TypeError, AttributeError):
        return None
    if ts <= 0:
        return None
    return {"ts": ts, "pid": raw.get("pid"), "age": max(0.0, time.time() - ts)}


def classify_interruption(store: "CheckpointStore", *,
                          dependencies_ok: bool = True,
                          primary_state: str = "unknown") -> Dict[str, Any]:
    """Classify the previous run's end from evidence. Never guesses beyond it.

    Decision tree (first match wins):
      not dependencies_ok                    -> DEPENDENCY_FAILURE
      clean marker, no dirty flag            -> CLEAN_SHUTDOWN
      dirty, and the primary save is corrupt  -> CORRUPTED_STATE
      dirty, heartbeat was recent             -> CRASH (sudden death)
      otherwise                               -> UNKNOWN_INTERRUPTION
    """
    d = store.directory
    clean = (d / CLEAN_NAME).is_file()
    dirty = (d / DIRTY_NAME).is_file()
    hb = read_heartbeat(store)
    evidence: Dict[str, Any] = {
        "clean_marker": clean,
        "dirty_flag": dirty,
        "heartbeat": hb,
        "primary_state": primary_state,
        "dependencies_ok": bool(dependencies_ok),
    }
    if not dependencies_ok:
        category = DEPENDENCY_FAILURE
    elif clean and not dirty:
        category = CLEAN_SHUTDOWN
    elif dirty and primary_state == "corrupt":
        category = CORRUPTED_STATE
    elif dirty and hb is not None and hb["age"] <= HEARTBEAT_STALE_AFTER_S:
        category = CRASH
    else:
        category = UNKNOWN_INTERRUPTION
    return {"category": category, "evidence": evidence}


def count_recent_outcomes(store: "CheckpointStore", n: int = 200) -> Dict[str, int]:
    """Count RECOVERY_REPORT outcomes in the journal tail. Never raises."""
    counts: Dict[str, int] = {}
    try:
        for entry in store.journal_tail(n):
            if entry.get("event") != "RECOVERY_REPORT":
                continue
            outcome = (entry.get("report") or {}).get("verification", {}).get("outcome")
            if isinstance(outcome, str):
                counts[outcome] = counts.get(outcome, 0) + 1
    except Exception:
        pass
    return counts


def assess_risk(*, interruption: str, checkpoint_finding: str,
                primary_state: str, recent_failures: int = 0,
                prior_state_known: bool = True) -> Dict[str, Any]:
    """Map concrete signals to a risk level and its permitted actions.

    checkpoint_finding: "PASS" | "FALLBACK" | "NONE"
    primary_state:      "healthy" | "corrupt" | "missing" | "unknown"
    recent_failures is only ever allowed to RAISE the level, never lower it.
    """
    def _risk(level: str, reason: str) -> Dict[str, Any]:
        return {"level": level, "permitted": list(PERMITTED_ACTIONS[level]),
                "reason": reason}

    if not prior_state_known and checkpoint_finding == "NONE" and primary_state == "missing":
        return _risk(RISK_LOW, "FIRST_RUN_NO_PRIOR_STATE")
    if interruption == DEPENDENCY_FAILURE:
        return _risk(RISK_CRITICAL, "RECOVERY_CORE_UNAVAILABLE")
    if checkpoint_finding == "NONE" and primary_state != "healthy":
        return _risk(RISK_CRITICAL, "NO_VERIFIED_CHECKPOINT_AND_PRIMARY_UNUSABLE")
    if checkpoint_finding == "FALLBACK" or recent_failures >= 2:
        return _risk(RISK_HIGH, "FALLBACK_SLOT_USED" if checkpoint_finding == "FALLBACK"
                     else "REPEATED_RECOVERY_FAILURES")
    if interruption in (CRASH, UNKNOWN_INTERRUPTION, CORRUPTED_STATE,
                        IOS_SUSPENSION, PROCESS_EXIT):
        return _risk(RISK_MEDIUM, "DIRTY_INTERRUPTION:" + interruption)
    return _risk(RISK_LOW, "CLEAN_SHUTDOWN")


# ---- verification chain (formalizes the checks the code already performs) ----
STEP_CHECKPOINT_VALID = "CHECKPOINT_VALID"
STEP_STATE_STRUCTURE_VALID = "STATE_STRUCTURE_VALID"
STEP_WORLD_DIMENSIONS_VALID = "WORLD_DIMENSIONS_VALID"
STEP_LAYERS_VALID = "LAYERS_VALID"
STEP_RULES_VALID = "RULES_VALID"
STEP_SERVER_RESPONDS = "SERVER_RESPONDS"
VERIFICATION_STEPS = (STEP_CHECKPOINT_VALID, STEP_STATE_STRUCTURE_VALID,
                      STEP_WORLD_DIMENSIONS_VALID, STEP_LAYERS_VALID,
                      STEP_RULES_VALID, STEP_SERVER_RESPONDS)


def run_verification_chain(*, checkpoint_ok: bool,
                           state: Optional[Dict[str, Any]],
                           expected_dims: Optional[tuple] = None) -> Dict[str, Any]:
    """Evaluate the named verification steps. SERVER_RESPONDS stays pending:
    it resolves on the first served request, after startup returns."""
    steps = []

    def _step(name: str, ok: bool, detail: str = "") -> None:
        steps.append({"name": name, "status": "pass" if ok else "fail",
                      "detail": detail})

    _step(STEP_CHECKPOINT_VALID, bool(checkpoint_ok),
          "" if checkpoint_ok else "no verified checkpoint")
    struct_ok = isinstance(state, dict) and isinstance(state.get("map"), dict)
    _step(STEP_STATE_STRUCTURE_VALID, struct_ok,
          "" if struct_ok else "state/map missing or malformed")
    dims_ok = False
    if struct_ok and expected_dims is not None:
        m = state["map"]
        dims_ok = (m.get("width"), m.get("height")) == tuple(expected_dims)
    _step(STEP_WORLD_DIMENSIONS_VALID, dims_ok,
          "" if dims_ok else "dimension mismatch or unknown expectation")
    layers_ok = False
    if struct_ok:
        layers_ok = all(isinstance(state["map"].get(k), list)
                        for k in ("tiles", "objects", "collision"))
    _step(STEP_LAYERS_VALID, layers_ok,
          "" if layers_ok else "a map layer is not a list")
    rules = state.get("rules") if isinstance(state, dict) else None
    rules_ok = rules is None or isinstance(rules, dict)
    _step(STEP_RULES_VALID, rules_ok,
          "" if rules_ok else "rules present but malformed")
    steps.append({"name": STEP_SERVER_RESPONDS, "status": "pending",
                  "detail": "resolves on first served request"})
    checkable = [s for s in steps if s["status"] != "pending"]
    return {"steps": steps, "all_ok": all(s["status"] == "pass" for s in checkable)}


def decide_outcome(*, action: str, fallback: bool = False,
                   checks_ok: bool = True, error: Optional[str] = None) -> str:
    """Map (action taken, verification result) to the outcome taxonomy.

    action: "RESTORED" | "NONE" | "WITHHELD"
    """
    if action == "WITHHELD":
        return RECOVERY_UNSAFE
    if error:
        return RECOVERY_FAILED
    if action == "RESTORED":
        if not checks_ok:
            return RECOVERY_FAILED
        return RECOVERY_PARTIAL if fallback else RECOVERY_SUCCESS
    if action == "NONE":
        return RECOVERY_SUCCESS
    return RECOVERY_UNKNOWN
