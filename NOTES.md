# Methodology

## Same-seed cross-version comparison is not a valid verification method

Discovered while refactoring ice_age's resource-clumping threshold from a
mean-based split to a percentile-based one (same measured average
fraction, same multipliers — intended to be behavior-neutral). Rescue
counts diverged sharply from the pre-refactor baseline anyway (e.g. one
seed went from 33 rescues to 9), and not just in severity — the number
of shock windows themselves changed (7 windows became 4 on the same
seed), meaning the entire shock-timing schedule reshuffled, not just
in-window outcomes.

Root cause: this is a chaotic system. Once any tick-level behavior
differs — even a handful of resource cells being redistributed
slightly differently — exactly which creatures live, die, move, or
reproduce differs that tick, which changes how many `random()` calls
get consumed, which changes every subsequent `random.random()` draw,
including the per-tick shock-probability check. The entire downstream
trajectory (including unrelated future shock timing) reshuffles. "Same
seed" only guarantees identical *initial* conditions, not a comparable
trajectory once any code in the tick loop changes.

**Standing rule from here: all verification is distributional, not
per-seed.** Minimum 10 seeds. Report the distribution (median, spread,
min/max) of the relevant metric, normalized appropriately (e.g. rescues
per shock window, not raw rescue count, since window counts vary
seed-to-seed and version-to-version). Never compare the same seed
across two code versions and treat the result as signal.

This applies to the Section 1.2 validation harness too, when it's
built: the punctuated-equilibrium rolling-variance check and the
fixed-mutation-rate baseline comparison both need to be distributional
across seeds for the same reason — a single-seed comparison between the
evolving-mutation-rate run and the fixed-rate baseline could show a
difference that's just RNG-schedule reshuffling, not a real effect of
the mechanism being tested.

# Candidate knobs for the ice_age severity pass (not yet tuned)

- `refugia_fraction` (currently 0.15, set to match the retired
  mean-based mechanism's measured average — not yet tuned for
  severity).
- `refugia_bonus_mult` / `refugia_penalty_mult` (currently 2.0 / 0.2,
  surfaced from hardcoded values — not yet tuned).
- **Onset ramping** (new candidate, promoted from a rejected bug-shape
  reproduction idea): the old mean-based split started wide (~26% of
  cells qualified) and narrowed to ~12-15% over the first ~700 ticks of
  a shock, as clumping self-reinforcement fed back on itself. That
  narrowing was itself a symptom of the defect being fixed and isn't
  being reproduced. But an ice age plausibly *should* ramp up in
  severity rather than hit full effect on tick 1 — that's a defensible
  idea on its own merits, independent of the old mechanism's accidental
  shape. If pursued, it needs its own reasoning and its own
  distributional verification, not a target of matching the old
  profile.

# Parked ideas

Things considered, deliberately not built yet, so they don't get lost
or silently re-decided later.

## heat_wave resource scatter

`heat_wave` originally had a `resource_scatter: true` config key with no
implementation behind it — a dead flag describing behavior that was
never written. Removed from config (a declared-but-unread flag is the
same class of dishonesty as `ice_age`'s `resource_clump` used to be,
before that got wired up).

The intent, if this gets picked up later: ice_age's `resource_clump`
concentrates resources into refugia (a minority of cells get a bonus,
the rest get a penalty) — heat_wave's equivalent "scatter" would do the
opposite, spreading resources thinner and more evenly rather than
concentrating them, representing dispersed/degraded rather than
patchy/refugial conditions. Not a priority until ice_age's own severity
pass is done and heat_wave gets its own isolate-and-tune treatment.
