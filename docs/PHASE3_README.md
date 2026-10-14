# Crumbs World — Phase 3: recovery state in the HUD

## What it adds
- `GET /api/recovery/status` (read-only): checkpoint slot inventory with
  per-slot SHA-256 verification, plus the last 50 journal events.
- Setup menu → Recovery…: a bottom sheet showing slot health badges and
  recent recovery events, with a Refresh button.
- Hardening (separate commit on this branch): startup no longer restores a
  stale checkpoint over a healthy primary save.

## API shape
```json
{
  "available": true,
  "slots": [
    {"slot": 0, "name": "latest.json", "present": true, "status": "PASS",
     "record": {"id": "CP-20260921-…", "created_at": 1790001493.5,
                "label": "save", "source": "crumbs_hud"}}
  ],
  "journal": [{"timestamp": 1790001493.5, "event": "CHECKPOINT_CREATED"}]
}
```

Slot `status` is `PASS`, `EMPTY`, or a failure reason
(`CHECKPOINT_UNREADABLE` / `CHECKPOINT_INTEGRITY_FAILED` / …).

## Notes
- The endpoint never writes: slot verification re-reads the files in place,
  and the journal is only appended by the normal save/startup paths.
- Version bumped to 5.22.0 (the updater reads `APP_VERSION` dynamically).
