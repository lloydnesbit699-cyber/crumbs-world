# Runtime incident notes

## 2026-10-20: attributed object cells crashed the height-grid request

**Observed:** the newest Harley stderr logs contained repeated
`TypeError: unhashable type: 'dict'` exceptions while serving the height-grid
request. The failing expression passed an object-layer cell directly to the
asset registry (`tiles.get(obj)`).

**Cause:** object-layer cells support both legacy integer tile IDs and
attribute-bearing dictionaries such as `{"tid": 42, "size": 1.5}`. The
height calculation handled only the legacy integer representation and used
the dictionary itself as a registry key.

**Repair:** resolve both representations through `core.obj_tid(cell)` before
looking up the asset. The regression check places an attributed object and
builds the full height grid.

**Prevention and diagnosis:** unexpected HTTP request exceptions are recorded
in `logs/runtime-errors.jsonl`. The ledger omits request contents and secrets;
it records an error id, method, route, error class, source location, and a
repair hint. Owners can read it at `/api/log/errors` and through Melody's
owner-only diagnostics. Use the error id to connect a player report with the
server record.
