# CRUMBS WORLD v5.61 PLAYTEST — CHECKLIST

**Tester:** _______________
**Date:** _______________
**Device:** _______________

For each check: Result (PASS / FRICTION / FAIL), Taps (count), Notes, Issue ID (if any).

---

## SECTION A: v5.60 FAIL RE-TESTS (did we fix them?)

**CHECK 01: LOGIN PERSISTS ACROSS SESSIONS**
Result:
Taps:
Notes:
Issue ID: PR-up404

**CHECK 02: PORTAL / INTERIOR NAVIGATION**
Result:
Taps:
Notes:
Issue ID: MR-ml604

**CHECK 03: WORLD GRAPH / STUDIO CONCEPT**
Result:
Taps:
Notes:
Issue ID:

**CHECK 04: USERS LIST = FRIENDS, NOT ALL PLAYERS**
Result:
Taps:
Notes: "Users" under File tray should show friends list, not all registered users.

---

## SECTION B: v5.60 FRICTION RE-TESTS (did they improve?)

**CHECK 05: FRESH-INSTALL NAVIGATION (crowding)**
Result:
Taps:
Notes:
Issue ID: GR-hn104

**CHECK 06: PANEL CLOSE RELIABILITY**
Result:
Taps:
Notes: Previously failed 25% of the time.
Issue ID: GR-pn504

**CHECK 07: MAP MOVEMENT**
Result:
Taps:
Notes:
Issue ID: GR-cm304

**CHECK 08: SAVE AND REOPEN ACROSS DEVICES**
Result:
Taps:
Notes:
Issue ID:

**CHECK 09: BOTTOM-LAYOUT CROWDING**
Result:
Taps:
Notes:

**CHECK 10: LONG CONTENT SCROLL (black-void)**
Result:
Taps:
Notes:

---

## SECTION C: v5.61 NEW — MAP GEN & WORLD SIZE

**CHECK 11: NEW MAP DEFAULTS TO 500x500**
Result:
Taps:
Notes: Create new map, verify dimensions.

**CHECK 12: "MAP GEN" BUTTON LABEL**
Result:
Taps:
Notes: Should say "Map gen" not "Generate".

**CHECK 13: BIOME ENTITY SELECTORS**
Result:
Taps:
Notes: Animals / Trees / Creatures / Characters checkboxes appear and toggle.

**CHECK 14: AUTO-PLACED ENTITIES APPEAR**
Result:
Taps:
Notes: Generate with entities checked, verify they spawn on suitable terrain.

**CHECK 15: AUTO-PATROLS FOR MOVERS**
Result:
Taps:
Notes: Animals/creatures/characters have patrol routes. Trees do NOT move.

---

## SECTION D: v5.61 NEW — MINIMAP

**CHECK 16: MINIMAP VISIBLE**
Result:
Taps:
Notes: Bottom-left, 120x120.

**CHECK 17: MINIMAP LIVE-UPDATES**
Result:
Taps:
Notes: Paint tiles, verify minimap refreshes.

**CHECK 18: MINIMAP STATIC TOGGLE**
Result:
Taps:
Notes: Toggle freezes/unfreezes. Icon changes.

**CHECK 19: MINIMAP TAP-TO-JUMP**
Result:
Taps:
Notes: Tap minimap, main viewport centers there.

**CHECK 20: MINIMAP VIEWPORT RECTANGLE**
Result:
Taps:
Notes: Gold rect shows current view.

---

## SECTION E: v5.61 NEW — ANIMATION RIG

**CHECK 21: RIG EDITOR OPENS**
Result:
Taps:
Notes: Animation panel → Rig section.

**CHECK 22: ADD ACTION**
Result:
Taps:
Notes: Add "walk", verify 4 direction rows appear.

**CHECK 23: SET FRAMES PER DIRECTION**
Result:
Taps:
Notes: Set frame ranges for down/up/left/right.

**CHECK 24: RIG PREVIEW PLAYS**
Result:
Taps:
Notes: Preview button plays the clip.

**CHECK 25: NPC FACES MOVEMENT DIRECTION**
Result:
Taps:
Notes: Place NPC, verify sprite faces where it moves.

---

## SECTION F: v5.61 NEW — PALETTE-SWAP

**CHECK 26: ANALYZE CHARACTER COLORS**
Result:
Taps:
Notes: "Analyze" extracts color slots with suggested names.

**CHECK 27: RECOLOR A SLOT**
Result:
Taps:
Notes: Pick a slot, use color wheel to change it, verify sprite updates.

**CHECK 28: SLOT RENAMING**
Result:
Taps:
Notes: Rename "Robe" to custom name.

---

## SECTION G: v5.61 NEW — ASSET MANAGER

**CHECK 29: ASSETS VIEW OPENS**
Result:
Taps:
Notes: Bottom sheet → Assets tab.

**CHECK 30: IMPORT PNG**
Result:
Taps:
Notes: Import shows preview BEFORE importing. Set name, preset, cell size.

**CHECK 31: SEARCH AND FILTER**
Result:
Taps:
Notes: Search by name, filter by tag.

**CHECK 32: DELETE ASSET**
Result:
Taps:
Notes: Confirmation appears.

**CHECK 33: TAP-TO-SELECT BRUSH**
Result:
Taps:
Notes: Tapping asset card selects it as paint brush.

---

## SECTION H: v5.61 NEW — COLOR WHEEL

**CHECK 34: EYEDROPPER OPENS WHEEL IMMEDIATELY**
Result:
Taps:
Notes: No map tap needed first.

**CHECK 35: "FROM MAP" BUTTON**
Result:
Taps:
Notes: Hides wheel, tap map, returns with color.

**CHECK 36: CANCEL RETURNS TO PREVIOUS BRUSH**
Result:
Taps:
Notes: Cancel → back to stamp, NOT eyedropper. Next map tap does NOT reopen wheel.

**CHECK 37: SHIELD WATERMARK VISIBLE**
Result:
Taps:
Notes: Faint logo behind wheel.

**CHECK 38: SWATCHES UPDATE**
Result:
Taps:
Notes: "From map" and "Your color" both visibly change.

---

## SECTION I: v5.61 POLISH

**CHECK 39: TOUCH TARGETS (44px)**
Result:
Taps:
Notes: Buttons feel tappable, no mis-taps.

**CHECK 40: FINAL NATURAL-USE SESSION**
Result:
Taps:
Notes: 10 minutes free play. Note anything awkward.
