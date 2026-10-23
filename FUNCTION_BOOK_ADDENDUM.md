# Function book addendum (built after the PDF)

Rules unchanged: no hold-to-magnify scope, no auto-hide HUD (P / button / View menu only), full-screen lens stays.

| Function | Where | Test |
|---|---|---|
| Melody daily circuit + swim detours | `melodyStartCircuit`, `/api/patrol-paths` (`swims`), `/api/play/melody_spot` (`water`) | `melody_circuit_client_test.js` |
| Teleport shrines (8, Origin = Star Beacon) | `_shrine_plan`, `/api/play/shrines`, `/api/play/teleport`, `shrineTravel`, `drawShrines` (T key, View > Play menu) | `shrines_client_test.js` |
| Shrine overview markers (full / dim / hidden) | `shrineState`, `drawShrines` | `shrines_client_test.js` |
| Areas 100x100, 3x3 live window, feather | `areaOf`, `areaAwake`, `areaLive`, `areaFeather` | `areas_client_test.js` |
| Day/night, compass, waypoint ring | `dayPhase`, `updateCompass`, `drawWaypointRing` | `world_life_client_test.js` |
| "I'm stuck" rescue — instant teleport to nearest safe ground (dry, standable, not hazard) | `_safe_at`, `_near_safe`, `/api/play/unstuck`, `playUnstuck`, `#btn-unstuck` (Play menu, runs only) | `unstuck_test.py` |

Assumptions: shrine spacing is clamped to a third of the map diagonal (a full in-game day of walking exceeds any map); the engine `MAP_MAX` is still 500, so the 1100x1100 world needs that cap raised and performance-tested.
