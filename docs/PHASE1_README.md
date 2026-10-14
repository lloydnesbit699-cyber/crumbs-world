# Crumbs Server Survival — Phase 1

## Goal

Prove the core property:

> The server process may disappear without losing the last verified state.

## Files

- `crumbs_recovery.py` — atomic checkpoint store + integrity verification + recovery journal.
- `recovery_smoke_test.py` — self-contained proof-of-concept.
- `PHASE1_REVIEW_WREN.md` — Wren's hardening review (implemented in v1.1).

## Test

```text
python3 recovery_smoke_test.py
```

Expected:

```text
PHASE 1 PASS (v1.1)
checkpoint -> interruption -> restart -> verified recovery
rotation -> fallback -> corruption detection
```

## v1.1 hardening (Wren)

- **Checkpoint rotation**: keeps `latest.json` + `prev-1.json` + `prev-2.json`.
  Recovery tries newest first and falls back. A corrupt new checkpoint can
  never destroy all older good copies.
- **File locking**: `fcntl.flock` guards checkpoint + journal writes, so a
  double-launched server can't interleave or clobber state.
- **Anchored paths**: default checkpoint root is the script's own directory
  (`__file__`), never the process working directory (unreliable on a-Shell).
- **Journal rotation**: capped at 1 MiB / 1000 lines, keeps the last 500.
- **UUID checkpoint IDs**: `CP-<utc-stamp>-<8 hex>` instead of
  timestamp + nanosecond-modulo.

## Safety

Phase 1 does **not**:
- delete project state
- overwrite a known-good checkpoint with uncertain state
- restart a real server automatically
- fight iOS background suspension
- depend on Replit or another host

Those belong to later phases.

## Next integration step

After this core passes, integrate checkpoints into `crumbs_hud.py` at the existing save boundary (`_save_now`) and add startup recovery reporting. Then test an actual server stop/restart cycle.
