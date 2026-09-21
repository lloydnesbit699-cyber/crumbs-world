# Crumbs World — Phase 2A + 2B

## Phase 2A
Adds the Phase 1 recovery core to the real `crumbs_hud.py`:
- successful saves create an atomic, SHA-256 verified checkpoint
- startup verifies the checkpoint
- a verified checkpoint restores the map into memory
- disk files are **not** overwritten during startup recovery
- recovery events go to `.crumbs_recovery/recovery-journal.jsonl`
- checkpoint failure never makes a normal save fail

## Phase 2B
The included installer is paired with a smoke test in the next step. The test starts the real server in a temporary copy, saves through `/api/save`, kills the process without clean shutdown, starts a fresh process, and verifies the fresh server reports checkpoint restoration.

## Apply
From the repo root, copy `phase2_install.py` and `crumbs_recovery.py`, then run:

    python3 phase2_install.py

The installer creates `crumbs_hud.py.phase2-backup` before changing the file.

## GitHub status
The connected GitHub integration still returns HTTP 403 for branch/write operations, so no repository files were silently changed. This bundle is the repeatable patch for Working Copy/Git CLI.
