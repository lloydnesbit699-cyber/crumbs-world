# Crumbs Server Survival — Phase 1

## Goal

Prove the core property:

> The server process may disappear without losing the last verified state.

## Files

- `crumbs_recovery.py` — atomic checkpoint store + integrity verification + recovery journal.
- `recovery_smoke_test.py` — self-contained proof-of-concept.

## Test

```text
python3 recovery_smoke_test.py
```

Expected:

```text
PHASE 1 PASS
checkpoint -> interruption -> restart -> verified recovery -> corruption detection
```

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
