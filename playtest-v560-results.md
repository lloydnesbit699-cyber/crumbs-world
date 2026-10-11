# CRUMBS WORLD v5.60 PLAYTEST — RESULTS

**Date:** 2026-10-11
**Tester:** Lloyd

## Summary
- **PASS:** 16/31
- **FRICTION:** 11/31
- **FAIL:** 4/31

## FAIL (must fix)
| Check | Issue | Notes |
|-------|-------|-------|
| 03: Login persists | PR-up404 | persistence = false |
| 28: Portal/interior nav | MR-ml604 | untested = nav unclear |
| 30: World graph/studio | — | (no notes) |
| 31: Users list | — | "Users" under File tray lists ALL registered players. Should be friends list, not all users. |

## FRICTION (harden)
| Check | Issue | Notes |
|-------|-------|-------|
| 04: Install to home screen | HS-sa204 | mobile = pass / desktop = untested |
| 05: Fresh-install nav | GR-hn104 | crowded, nav unclear |
| 09: Map movement | GR-cm304 | needs hardening/testing |
| 12: Close panel | GR-pn504 | panels not closing 25% of the time |
| 16: Not color-only | — | needs hardening |
| 17: Panel nav history | — | hardening around advanced |
| 18: Suggest tab | — | req hardening |
| 20: Bottom-layout crowding | — | preview area glitch / crowded |
| 22: Long content scroll | — | persists (black-void) |
| 25: Save and reopen | — | hardening between devices/sessions/shared maps |
| 29: Recovery | — | hardening around server/game failures |

## PASS (verified)
01, 02, 06, 07, 08, 10, 11, 13, 14, 15, 19, 21, 23, 24, 26, 27

## Notes carried forward
- Check 01: Profile persistence across devices/sessions needs hardening (PR-up404).
- Check 08: Start/default map size needed adjusting → **FIXED in v5.61 (500x500 default)**.
- Check 14: Tap target hardening → **FIXED in v5.61 (44px minimum)**.
