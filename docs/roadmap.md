# Crumbs HUD Roadmap

Sequenced for one developer and the quickest path to revenue. "Now" is
v5.16. Dates are intentionally absent — order matters more than dates
when it's one person.

## Now — v5.16: trust + sellable outputs

Ship these before asking anyone for money. Each is small, concrete, and
directly unblocks a sale or a classroom.

1. **Public-mode share key.** Write actions require a key when `--public`
   is on; without it, public mode is read-only. The single highest-value
   security control.
2. **Rate limiting + request-size limits** on asset/upload endpoints,
   plus stricter upload validation. Cheap, kills casual abuse.
3. **Backup/restore + corrupt-sidecar recovery.** One-tap restore from
   the backups the server already writes; automatic detection and repair
   (or quarantine) of corrupted map sidecars. Nobody buys a tool that
   can eat their work.
4. **Schema versioning + migrations.** Every map sidecar (missions,
   items, NPCs, gear, traits) gets a schema version; the editor migrates
   old sidecars forward and says what it changed.
5. **Tiled JSON export.** Alongside PNG export — the first export format
   another engine can actually consume.
6. **Shareable map bundles.** Map + embedded assets + version stamp in
   one file. The unit of "here, play my level."
7. **Template starters.** Dungeon-crawler and survival starter projects
   (beyond the current starter maps) so a new user gets an instant
   outcome, not a blank grid.
8. **Deterministic generation presets.** Seeded presets with distinct
   biome identity, reproducible every time.
9. **Entitlement-aware pack loading.** Free vs paid content gating in the
   pack system — the mechanism the Creator/Pro editions stand on.

## Next — after v5.16, in this order

10. **Export packs for engines.** Godot-ready and Unity-friendly bundles
    after Tiled JSON proves the pipeline.
11. **Reusable brushes/stamps + batch asset ops.** Tagging, advanced
    search/filter, batch operations on tiles — the creator pipeline
    upgrades that make big maps feasible.
12. **Local roles for public mode.** Viewer / editor / admin roles on top
    of the share key, so a classroom can share one session safely.
13. **Performance mode.** Render-budget presets and quality tiers for
    very large maps and older phones.
14. **Landing page + demo gallery + onboarding funnel.** Ship when the
    product is worth pointing at: hero, persona sections, playable demo
    maps, install → first map in 5 minutes.
15. **Storefront hooks for tile/adventure packs.** In-app hooks; actual
    store can start as a simple page.
16. **Privacy-safe analytics.** Which features drive conversion and
    retention — opt-in, no tracking pixels, no third parties.

## Later — needs decisions first

- **Payment provider** — needs decision. Pick one (itch.io, Gumroad,
  Stripe, Lemon Squeezy) before building purchase/entitlement flows.
  itch.io "pay what you want" fits the current audience best.
- **Real cloud backend** — needs decision. Optional cloud sync/backup
  for cross-device continuity is the most-requested-shaped feature and
  the biggest build. Don't start until editions are selling.
- **Plugin/extension points** — tile packs, rulesets, generation
  profiles as plugins. Worth doing only after the module split; don't
  design it in the abstract.
- **Server/editor module split** — API domains (maps, assets, play,
  missions, commerce) as modules. Do it when the single files become
  painful, not before.

## What we're NOT doing

- Accounts, logins, or social features.
- A cloud-first rewrite. Offline-first is the product.
- Chasing engine parity with Unity/Godot. Crumbs is the sketchbook.
