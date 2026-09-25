# The Crumbs Repair Laws

*Learned the hard way, 2026-09-23/24. These govern every fix, every update,
every recovery in the Crumbs HUD. Break one and you get a midnight debugging
session. Follow them and the system heals itself.*

---

### 1. The Banner Tells The Truth
The version in the banner is the version of the code running RIGHT NOW.
Not the version on disk. Not the version git knows about. The running code.
If the banner lies, nothing else can be trusted.

### 2. A Restart Must Actually Restart
When anything triggers a restart (button, updater, API), the new process
must load the new files. If the restart mechanism can't guarantee this, it
must say so and tell the user to kill the process manually.
A restart that silently keeps old code is worse than no restart at all.

### 3. Pull Is Not Proof
`git pull` saying "up to date" doesn't mean you have the latest code.
If the local branch diverged — Replit's "Published your App" commits,
local edits, anything — the pull can't merge and won't tell you why.
Check `git log --oneline -3`. If the top commit isn't what you expect,
`git reset --hard origin/main` puts you back on truth.

### 4. Reset Means Clean Slate
A reset button must produce a clean next boot. Archive the old (never
delete), clear ALL evidence — journal, reports, heartbeat, dirty/clean
flags — so the next assessment starts from zero.
If the next boot still shows the old state, the reset was a lie.

### 5. One Port, One Server
Never run two servers on the same port. If the port is taken, say what's
running there and refuse to start a ghost that masks the real one.

### 6. Never Downgrade Silently
The updater must refuse to install anything older than what's running.
A stale CDN edge or a cached download is not an excuse.

### 7. Pushed ≠ Verified
Code pushed to GitHub is not code running on the device. Never claim a fix
works until it's confirmed on the actual hardware. The only verification
that counts is the user's eyes on their screen.

### 8. Cache Is Guilty Until Proven Innocent
After any update, assume the browser cached the old page. Hard-refresh.
The updater should force this, not hope for it.

### 9. Archive, Don't Delete
User data, journals, backups — archive with a timestamp, never delete.
A fix that destroys history is not a fix.

### 10. Evidence Over Assumptions
When something's wrong, check the actual state: `git log`, the banner
version, the running process, the files on disk. Don't assume the last
command worked. Trust the evidence, not the expectation.

### 11. The Button Must Work
If a button is in the UI, it must do what it says. Dead buttons —
"empty hooks" that can't function no matter how much you wish —
get removed. No placeholders, no wishes.

### 12. Failures Expire, But State Doesn't Lie
Old failures shouldn't hold the shield red forever (24-hour decay).
But the current state assessment must always reflect reality:
no verified checkpoint + no usable save IS critical,
no matter how old the failures are.

### 13. The Update Finishes The Job
An update isn't done when the files land — it's done when the new code is
*running and verified*. Swap, restart into the new files, and prove the new
instance is the one answering; never leave the user between versions, and
never let a button declare success off the old process still answering.
(Lloyd's diagnosis, 2026-09-25: the updater swapped files then waited on a
manual restart — the "stuck between commits" state.)

### 14. Ship The Art With The App
A feature isn't shipped when its code lands — it's shipped when everything
the code *points at* lands too. The updater shipped code only, so phones
carried registry entries for art that never arrived, and a hundred tiles
painted permanently blank swatches: the "missing thumbnails" were never a
rendering bug, they were an incomplete shipment. Data, art, and registries
travel with the installer; a registry entry whose file is absent is a
broken promise — detect it, say so honestly (a "?" beats a blank), and
repair it on demand.
(Lloyd's call, 2026-09-25: fix the missing thumbnails at the root, don't
patch the symptoms.)

### 15. One Tile, One Home
Every tile has exactly one home tab, decided by what it IS — not by how
it arrived. A floor is a floor: it lives in Tiles under the Floors chip,
even though it's a "made thing" like an object. When "everything else"
becomes a junk drawer, harden the taxonomy: a single routing table both
sides share, automatic names derived from the data, no tile in two places
and none in none. Categories are promises — keep them so a user can trust
them.
(Lloyd's direction, 2026-09-25: hardened naming, distinctions,
categorization — floors belong in the tiles menu where the floor menu is.)

### 16. Cache What You Crop
If the server builds it from scratch on every request, the client will
feel it hang. A thumbnail cropped and PNG-encoded per request took ~3s on
a slow host — a full tab of them never finished. Cache the bytes in memory
and tell the browser to cache them too; only ever cache successes, and
only when the underlying data can't go stale beneath the cache.
(Lloyd's report, 2026-09-25: thumbnails still hanging.)

---

*When a new midnight lesson arrives, it becomes Law 17.*

### 17. Don't Serialize What Doesn't Share State
A lock must guard only what it protects. v5.27 put every `/api/*` request
— including 80 thumbnail images that touch no vault state at all — into a
single-file line behind the vault lock, and the palette sat blank on slow
hosts. The fix wasn't a faster lock; it was no lock: prove each endpoint's
independence (thumbnails render from the global art registry) and exempt
it. When you add a global lock, audit every path it now covers — the
innocent ones will be the ones your users feel.
(Lloyd's report, 2026-09-25: palette thumbnails blank, never arriving.)
