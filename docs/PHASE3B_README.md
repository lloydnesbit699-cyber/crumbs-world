# Phase 3B — Recovery Intelligence & Guardrails

Branch: `recovery/phase-3b` · Base: `main @ be2df24` (Phase 3A complete)
Status: implementation, awaiting six-check audit before merge

Phase 3B does **not** make recovery more aggressive. It makes recovery
smarter, observable, diagnosable, risk-aware, governed, and independently
verifiable. Phase 3A (exposure: Recovery sheet + `/api/recovery/status`)
is left untouched and extended, not rebuilt.

## What 3B adds

**Interruption classification** (`classify_interruption`, `crumbs_recovery.py`)
- Evidence: heartbeat file (written every 5 s by the running server),
  `dirty.flag` (set at startup, cleared on orderly shutdown),
  `clean.shutdown` marker (written by atexit / SIGTERM / SIGINT handlers).
- Decision tree (first match wins):
  1. recovery core unavailable → `DEPENDENCY_FAILURE`
  2. clean marker, no dirty flag → `CLEAN_SHUTDOWN`
  3. dirty, and the primary save is corrupt → `CORRUPTED_STATE`
  4. dirty, heartbeat was recent (≤ 15 s) → `CRASH` (kill -9 and segfault
     are indistinguishable — documented, not guessed)
  5. otherwise → `UNKNOWN_INTERRUPTION`
- `IOS_SUSPENSION` and `PROCESS_EXIT` are defined but **unused in v1**:
  with only a heartbeat and markers, a suspension-then-kill looks exactly
  like a crash. Unknown remains unknown.

**Risk model** (`assess_risk`)
- Maps concrete signals → level → permitted actions. Risk decides what the
  system is *allowed* to do, not just what it reports.
- Levels and authority:
  - LOW → NORMAL_STARTUP
  - MEDIUM → + RESTORE_VERIFIED_CHECKPOINT, LOG_NOTICE
  - HIGH → + PRESERVE_EVIDENCE, INTERVENTION_NOTICE (same restore power)
  - CRITICAL → WITHHOLD_ACTION, PRESERVE_EVIDENCE, INTERVENTION_REQUIRED
- Anti-escalation: repeated failures (`recent_failures >= 2`, counted from
  the journal) can only *raise* the level. The destructive-capable action
  set is `{} → {RESTORE} → {RESTORE} → {}` across LOW/MEDIUM/HIGH/CRITICAL —
  it never grows with risk. This is asserted in tests.
- Fresh install (no evidence, no checkpoint, no primary) → LOW /
  FIRST_RUN_NO_PRIOR_STATE, not a false CRITICAL.

**Verification chain** (`run_verification_chain` + `decide_outcome`)
- Formalizes the checks the code already performed, as a named checklist:
  CHECKPOINT_VALID → STATE_STRUCTURE_VALID → WORLD_DIMENSIONS_VALID →
  LAYERS_VALID → RULES_VALID → SERVER_RESPONDS.
- SERVER_RESPONDS stays `pending` at startup and resolves on the first
  served request (journaled once as `SERVER_RESPONDS`).
- Outcomes (failure/success library seed):
  - RESTORED + all checks pass → `RECOVERY_SUCCESS`
  - RESTORED from a fallback slot → `RECOVERY_PARTIAL` (older state; can't
    verify it's the latest)
  - restore raised / no valid state → `RECOVERY_FAILED`
  - action withheld for safety → `RECOVERY_UNSAFE`
  - nothing to recover (healthy primary, fresh start) → `RECOVERY_SUCCESS`
    with action `NONE`
  - anything else → `RECOVERY_UNKNOWN`

**Evidence trail** — every startup journals one `RECOVERY_REPORT` answering:
what happened, what was done, why it was permitted (risk level + reason),
what was preserved, and whether it worked. Failure evidence is never
deleted. The latest report is also atomically written to
`.crumbs_recovery/last_report.json` for the HUD.

**HUD** — the Recovery sheet gains a state block (SERVER / CHECKPOINT /
LAST SAVE / RECOVERY / RISK), the last report (cause, action, permitted-by,
per-step verification), and an ⚠ INTERVENTION REQUIRED panel at HIGH /
CRITICAL or UNSAFE / FAILED outcomes.

## Deliberately deferred

- **Live restore progress** (spec §8's progress bar): recovery runs
  synchronously at startup before the server accepts connections, so the
  HUD cannot watch it yet. Deferred until the observability architecture
  exists — not re-architected here.
- Distinguishing iOS suspension from crash (needs an explicit OS channel).
- Manual rollback button for prev-1/prev-2 (withheld action ≠ manual action).

## Project law (from the spec, adopted)

*A recovery action is not successful because it completed. It is successful
only after the recovered state has been independently verified.*

## Files changed

- `crumbs_recovery.py` — outcome taxonomy, interruption taxonomy, evidence
  helpers, `classify_interruption`, `count_recent_outcomes`, `assess_risk`,
  `run_verification_chain`, `decide_outcome`, report read/write. All additive.
- `crumbs_hud.py` — v5.22.1: heartbeat thread, dirty/clean lifecycle markers,
  `_recover_startup()` reworked as classify → assess → act → verify →
  report, `SERVER_RESPONDS` hook on first request, extended
  `/api/recovery/status` (report, risk, server_serving, heartbeat_age,
  last_save).
- `editor.html` — Recovery sheet: state block, report, intervention panel.
- `PHASE3B_README.md` — this file.
