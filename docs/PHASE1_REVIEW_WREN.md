# Phase 1A Review — Wren's notes (held for after Phase 1B)

Status: REVIEW ONLY. Do not implement until the other AI's Phase 1B drop
lands and her token run is complete. Then apply with full context.

## Bugs waiting to happen

1. **Single checkpoint slot.** Only `latest.json` exists. Every checkpoint
   overwrites the last. If state was corrupt *before* the checkpoint, the
   last good copy is destroyed. The transfer prompt's own safety rule
   ("never overwrite a known-good checkpoint with uncertain state") is
   violated by the implementation.
   Fix: keep last 3 (`latest.json`, `prev-1.json`, `prev-2.json`).
   Recovery tries newest first, falls back.

2. **No file locking.** Lloyd double-launches the server (sees "Address
   already in use"). Two writers won't tear the file (atomic writes hold)
   but journal entries interleave and checkpoints can clobber.
   Fix: `fcntl.flock` around checkpoint + journal writes.

3. **Checkpoint path not anchored.** `CheckpointStore(root)` trusts the
   caller. On a-Shell, CWD is unreliable (the `~` container lesson,
   2026-09-17). Fix: default root to the script's own directory via
   `Path(__file__).resolve().parent`.

4. **Journal grows forever.** Admitted in a code comment. Every checkpoint
   + health event appends to `recovery-journal.jsonl`. Slow storage leak
   on a phone. Fix: rotate at 1000 entries or 1MB.

5. **Nothing checkpoints on the way down.** iOS sends no SIGTERM to
   Python on suspension — the process just freezes. Recovery is only as
   fresh as the last checkpoint. If Lloyd paints 10 min without saving,
   that's 10 min lost. Fix: checkpoint on debounce (~30s after last edit),
   not just on manual save.

## Smaller items

- Checkpoint IDs use `time.strftime` + `time.time_ns() % 1000000`.
  Unlikely to collide, but `uuid4().hex` is bulletproof. Trivial swap.
- IDs use `time.localtime` — timezone travel makes them sort oddly.
  Cosmetic; use UTC or don't rely on sort order.
- `load_verified` checks the hash but not the state shape. A hash proves
  bits didn't rot; it doesn't prove the map isn't garbage.
  Fix (Phase 1B): schema-validate expected keys before declaring PASS.
- `healthy()` is never called automatically. Heartbeat timers freeze on
  iOS anyway — don't build Phase 2 around heartbeat; build around
  checkpoint freshness.
- `recover()` returns the record but doesn't apply it. That's Phase 1B's
  job (splice at `_save_now()`), just noting the gap is real: today this
  is "verified backup," not "self-healing."

## The big idea (post-1B)

Make the checkpoint BE the save. Two systems (`hud_map.json` + recovery
checkpoints) means "which one is newer?" arguments. If every save is a
verified checkpoint and every load verifies, there's one source of truth
and the divergence bug class disappears.

Also: the HUD recovery timeline ("last checkpoint 09:41, iOS suspension,
recovered in 2s") is the visible proof that builds trust. Worth building
once the core is solid.
