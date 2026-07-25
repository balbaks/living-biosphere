# Living Biosphere

A persistent, self-running artificial-life ecosystem. One continuous,
never-reset world, meant to run indefinitely. Solo-built, in public.

This is currently mid-build on Section 1 (the simulation engine) of a
larger plan. It is not a finished product — the sections below are
honest about what's working, what's tuned, and what's still open.

## What it is

A 2D grid world of creatures with a float-array genome (movement
efficiency, size, diet type, reproduction threshold, aggression, and a
**heritable mutation rate** — letting mutation rate itself evolve is the
centerpiece design choice, aimed at producing punctuated-equilibrium
dynamics: long stable stretches interrupted by bursts when high-mutation
lineages take over after an environmental shock).

Species are identified with a NEAT-style compatibility-distance
clustering (not a fixed Euclidean threshold), adapted each tick to keep
the species count in a target range. A shock/intervention system
(ice age, heat wave, famine) fires on a randomized schedule but is
telegraphed ahead of time — an "incoming" event is logged before the
shock actually lands.

This is well-trodden artificial-life territory (Tierra, Avida,
Polyworld, evolvability research) — the goal here isn't a novel
mechanism, it's packaging that mechanism into something worth watching
and narrating over a long time horizon.

## What's built and verified

- Grid world, energy economy, predation, reproduction with mutation.
- NEAT-style adaptive species clustering.
- Shock system with telegraphed announcements and randomized trigger
  timing.
- Shocks properly expire and revert (each shock carries its own
  `end_tick`; overlapping shocks stack multiplicatively and each
  reverts independently — verified with a direct forced-overlap test).
- Famine's severity/duration has been isolate-tuned across three seeds
  to produce a real, visible population trough without needing the
  emergency rescue mechanism.

## What's known-broken or untuned right now

- **ice_age has not been isolate-tuned.** It was fixed so it correctly
  *expires* (this was a real bug — it used to compound permanently and
  never revert), but its severity/duration (`temp_drop: 0.5` for 800
  ticks) has not been swept and validated for zero-rescue survivability
  the way famine has. A combined-shock test surfaced solo ice_age
  windows still triggering the emergency rescue mechanism in 2 of 3
  test seeds. heat_wave is in the same untested position. This is the
  next diagnostic step.
- **No SQLite persistence yet.** Fossil records and event logs are
  in-memory only; nothing survives a process restart.
- **`lineage_parent_id` is stubbed to `None`.** Species-emergence fossil
  records don't yet resolve which existing species a new one split
  from.
- **No validation harness yet** (rolling-variance punctuated-equilibrium
  check, fixed-mutation-rate baseline comparison run) — deliberately
  sequenced after persistence and lineage tracking land, so it isn't
  built against data that would need to be thrown away.
- No dashboard, API, or narration layer yet — those come later in the
  plan.

## Running it

```
python -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/python -m src.main --ticks 5000 --seed 42
```

Config lives in `config/world.yaml`.
