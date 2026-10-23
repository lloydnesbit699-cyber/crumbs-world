# Function book addendum (built after the PDF)

Rules unchanged: no hold-to-magnify scope, no auto-hide HUD (P / button / View menu only), full-screen lens stays.

| Function | Where | Test |
|---|---|---|
| Melody daily circuit + swim detours | `melodyStartCircuit`, `/api/patrol-paths` (`swims`), `/api/play/melody_spot` (`water`) | `melody_circuit_client_test.js` |
| Teleport shrines (8, Origin = Star Beacon) | `_shrine_plan`, `/api/play/shrines`, `/api/play/teleport`, `shrineTravel`, `drawShrines` (T key, View > Play menu) | `shrines_client_test.js` |
| Shrine overview markers (full / dim / hidden) — WORLD view only in Play, plus the Build (dev) World lens (Lloyd's ruling); fixed screen size (`SHRINE_MARKER_PX`), no longer tile-scaled or drawn at GROUND/FIRST/SURVEY (Stage 2, §15) | `shrineState`, `drawShrines`, `playModeName`, `lensRegionOn`, `SHRINE_MARKER_PX` | `shrines_client_test.js`, `stage2_shrines_client_test.js` |
| Areas 100x100, 3x3 live window, feather | `areaOf`, `areaAwake`, `areaLive`, `areaFeather` | `areas_client_test.js` |
| Day/night, compass, waypoint ring | `dayPhase`, `updateCompass`, `drawWaypointRing` | `world_life_client_test.js` |
| "I'm stuck" rescue — instant teleport to nearest safe ground (dry, standable, not hazard) | `_safe_at`, `_near_safe`, `/api/play/unstuck`, `playUnstuck`, `#btn-unstuck` (Play menu, runs only) | `unstuck_test.py` |
| Hero glide — drawn hero eases toward the server-stepped tile; camera/sprite/light pool follow the drawn position (render-only) | `playHeroGlideStep`, `heroDrawPos` | `stage1_camera_client_test.js` |
| FIRST = over-the-shoulder — camera focus rides ahead of the hero along his facing (no deadzone; turns swing, never snap) | `playFirstFocus`, `playCameraStep` (`opts.focus`), `playRegionBegin` | `stage1_camera_client_test.js` |
| Close-range pixel snap + scaler pin (GROUND/FIRST band: origin lands on whole backing pixels, quality scale frozen) | `playSnapOrigin`, `playQualityStep` (`pin`), `PLAY_CLOSE_MAX_N` | `stage1_camera_client_test.js` |
| Play entry leaves the full-screen lens before the camera snapshot, so exit restores the true Build camera (item 20) | `togglePlay`, `lensLeave`, `snapCameraSel` | `stage1_camera_client_test.js` |
| Build lens altitude range (Stage 3, §16.1) — lens spans 1–256px: down to a true WORLD fit of a 500-tile map (sub-6px keeps a decimal so the fit stays exact), up to Play's GROUND detailing scale on tall stages; named stops mirror Play's ladder, on Play's digits (2/3/4) | `lensBandPx`, `lensBandName`, `lensGoBand`, `lensClampPx`, `LENS_BAND_LABELS`, `lensBadge` | `lens_range_client_test.js`, `lens_full_client_test.js` |

Assumptions: shrine spacing is clamped to a third of the map diagonal (a full in-game day of walking exceeds any map); the engine `MAP_MAX` is still 500, so the 1100x1100 world needs that cap raised and performance-tested.
