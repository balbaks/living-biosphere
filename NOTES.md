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

# Ice_age severity pass — done

`refugia_penalty_mult` tuned 0.2 -> 0.9, `duration_ticks` tuned 800 ->
350 (see commits `1372943`, `42891fe`). `refugia_fraction` (0.15) and
`refugia_bonus_mult` (2.0) left untouched — genuine scarcity and an
already-survivable bonus, not severity dials. heat_wave checked
separately and needs no tuning (zero rescues at its current values,
10/10 seeds, isolated). famine tuned separately (`0.65`/`600`, commit
`0cd6c9e`). All three, combined, verified zero rescues across 10 seeds
x 20,000 ticks at the current `shock_probability: 0.0003`.

**Onset ramping** (candidate, not built): the old *retired* mean-based
clump split narrowed from ~26% to ~12-15% over a shock's first ~700
ticks, as self-reinforcement fed back on itself — that was a symptom of
the bug being fixed, not something worth reproducing. But an ice age
plausibly *should* ramp in severity rather than hit full effect
instantly — a defensible idea on its own merits. Not pursued; parked
here so it isn't lost.

# Section 1.2 pre-registration — punctuated equilibrium validation harness

Pre-registered 2026-07-26, before any arm has been run. Config hash at
registration time: `1b151603eb662fc4c94dcecf91ada7d08a34a181152dd8348aacf94475f45fb4`
(`config/world.yaml`, commit `42891fe` state plus the shock_probability
and severity fixes already landed — see git log for the exact tree).

## What's being tested

The plan's own definition of done: "the evolving-mutation-rate run
shows punctuated equilibrium behavior the fixed-rate baseline doesn't.
If it doesn't, the tuning is wrong."

## Statistic — S2, chosen on synthetic ground truth, not on our data

**Definition.** Bin turnover events (species_emergence + extinction
fossil records; rescues excluded, see below) into 10-tick epochs
(matching `_update_species`'s cadence — the finest resolution the
model can produce). For a sliding 100-tick (10-epoch) window, stepped
one epoch at a time, compute the window's *total* event count. S2 is
the Fano factor (variance/mean) of that window-totals series across
the whole run.

**Why not the originally-proposed statistic.** The original candidate,
p95 of *within-window* variance of epoch counts (call it S1), was
flagged as suspect after a same-day spot-check showed 3 of 4 seeds
below their own null's median (standardized excess 0.562-1.073) —
previewing failure. Investigated the mechanism rather than accepting
either the number or dismissing it: S1 is maximized by concentrating
events into a *single* epoch, not by clustering across the several
adjacent epochs a real 100-tick burst would actually span at 10-tick
resolution — it's structurally biased against detecting the kind of
clustering being tested for.

**Validated on synthetic ground truth before re-deciding anything**,
per the instruction that the choice be made on data where the answer
is known, not on ours: three synthetic epoch-count series (known-
bursty via clustered event placement, known-uniform via random
placement, known-regular via even spacing), at N=49/150/285 matching
the real observed range, 15 realizations each, tested against S1 and
S2 (Fano factor of window totals) with a 100-permutation null each.

Result: S1 detects known-bursty structure 0%/73%/13% of the time at
N=49/150/285 (unreliable, and non-monotonic with N — worse at N=285
than N=150, a failure mode not predicted in advance). S2 detects it
100% of the time at every N tested, mean margin ~3.8-4.0x over the
null threshold. Both correctly reject uniform/regular controls (0-13%
false-positive rate). S2 is adopted as the sole primary statistic. S1
is dropped entirely — not kept as a reported secondary, since carrying
a demonstrably unreliable statistic alongside a validated one invites
exactly the selective-reporting problem this process exists to avoid.

**Known limitation, stated now rather than discovered in interpretation:**
S2 does not distinguish a single early burst followed by permanent
stasis from genuine repeated stasis-burst-stasis cycling — both
concentrate window-total mass away from a uniform spread and will
score as non-random. A statistical pass under S2 confirms non-random
clustering (the plan's literal "not pure noise" bar) but does not by
itself confirm the richer narrative of *repeated* punctuation. No
statistic distinguishing single-burst-then-freeze from repeated
cycling has been built; this is a real gap, not a solved problem.

## Pre-registration exposure — full disclosure, dated

Before this pre-registration was finalized, spot-check numbers were
seen on real seeds, twice, using two different (S1 then S2)
statistics. Recording both so the record is honest about what was and
wasn't blind:

- **S1-based spot check** (4 seeds, 20,000 ticks, isolated Arm-A-like
  config): standardized excess seed 1 = 1.000, seed 4 = 0.583, seed 5 =
  1.073, seed 7 = 0.562 — 3 of 4 at or below 1.0, previewing failure.
  This number motivated the investigation in item 1 above; it did not
  motivate the choice of S2 over S1 — that choice was made entirely on
  the synthetic ground-truth results, which contain no reference to
  real seed data.
- **S2-based spot check**, same 4 seeds, same runs: standardized excess
  2.076 (seed 1), 2.424 (seed 4), 1.738 (seed 5), 2.661 (seed 7) — all
  four pass. Given the known limitation above, seed 7's pass in
  particular reflects one early burst (49 events, all before tick 9370)
  followed by ~30,000+ ticks of total silence, not repeated cycling —
  worth remembering when the real 10-seed result comes in and looks
  favorable at a glance.

## The mutation-rate floor and the shock-frequency/mechanism tension

Arm A's evolved mutation rate (measured post-tuning, final config, 10
seeds, 20,000 ticks): mean 0.0053, **median 0.0020 — exactly the
genome floor** (`GENE_MIN[MUT_RATE] = 0.002` in `src/genome.py`,
originally set "to ensure mutation rate doesn't collapse to zero").
Selection is driving mutation rate down against a bound we chose; the
mean is pulled up entirely by a thin tail reaching the ceiling (max
0.1). This is the textbook stable-environment mutation-load result.

**Sensitivity check on the floor itself**, run directly rather than
assumed: with the floor lowered 10x to 0.0002, seed 7's population
converges to *that* floor instead (100% of population, mean=median=
0.00020) and reaches single-species stasis with *fewer* total events
(N=97 vs 146 at the original floor) over the same 20,000 ticks — a
lower floor makes the freeze happen faster, not slower. The central
claim ("evolving mutation rate produces punctuated equilibrium") is
demonstrably sensitive to where this wall is set, in a way that argues
for revisiting it, though no change is proposed here — that's a
Section-1.2-result-informed decision, not a pre-registration one.

**The frequency/mechanism tension, hypothesized then checked, not
confirmed as hypothesized:** the working theory was that dropping
shock coverage 48%->11% (for the independent, correct design-intent
reason — see the shock_probability commit) gave selection more stable
time to grind mutation rate to the floor, and that earlier high-
frequency runs showed rates reaching ~0.07 under stress. Checked
directly on 4 seeds, old (0.001) vs new (0.0003) shock_probability:
the pattern did not cleanly replicate. Seed 1 moved the *opposite*
direction (mean mutation rate 0.0101 -> 0.0271, higher at low
frequency). Seed 5 moved as hypothesized (0.0191 -> 0.0042). Seeds 4
and 7 showed little difference. This is noisy and seed-dependent, not
a confirmed systematic effect — recorded as an open, unsupported
hypothesis, not a finding. Two live candidate explanations, neither
confirmed: (a) the original high-rate observation was a transient
spike during/after a shock rather than a persistent population-mean
shift, which a whole-run average wouldn't capture either way; (b) it
was seed-specific noise with no systematic cause. Whichever it is,
**seeds 5 and 7 are independently confirmed frozen** into permanent
single-species stasis regardless of shock frequency (N unchanged
across 20k/30k/40k-tick runs for both — last turnover event for seed 7
was at tick 9370, nothing since), so mutation-load collapse halting
evolution entirely is a real, observed phenomenon in the current
config, whatever its relationship to shock frequency turns out to be.

## Arms, seeds, run length

| Arm | Config | Seeds | Purpose |
|---|---|---|---|
| A: evolving, shocks-on | current default config | 10 | primary system under test |
| B: fixed mutation rate at 0.0053 (Arm A's realized *mean*) | shocks-on otherwise unchanged | 10 | does evolving mutation rate matter? (primary gate) |
| B2: fixed mutation rate at 0.0020 (Arm A's realized *median*) | shocks-on otherwise unchanged | 10 | secondary, non-gating — brackets the level confound (see below) |
| D: evolving, shocks-off | `intervention.enabled: false` | 10 | is punctuation emergent or shock-forced? |
| Null | permutation of each real seed's own epoch sequence | 200 per real seed | falsification baseline, not a simulation |

**Run length: 40,000 ticks.** Derived from the observed N-vs-ticks
relationship (not guessed): seed 1 clears N>=150 by ~25-30k ticks, seed
4 by ~35-40k, seed 5 already clears it at 20k (and is separately
frozen — see above), seed 7 never clears it at any length tested
(frozen at N=49). 40,000 ticks lets genuinely-still-evolving seeds
catch up without pretending it rescues frozen ones.

**Arm B's residual level mismatch, documented as a known limitation:**
0.0053 matches Arm A's mean, but Arm A's *median* lineage sits at
0.0020 — a single fixed point cannot match a distribution, so Arm B is
~2.6x Arm A's typical realized rate even while matching its mean. B2
(fixed at 0.0020, the median) is added as a secondary, non-gating arm
specifically to bracket this — it does not affect the primary A-vs-B
gate, so it introduces no multiplicity problem for that test.

**heat_wave**: present, unmodified, in the shock pool for Arms A/B/B2
(temp_rise 1.5, duration_ticks 800); absent from Arm D
(`intervention.enabled: false` disables all three shock types, not
just ice_age/famine). Verified zero-rescue in isolation, 10/10 seeds —
not an uncontrolled element.

**Rescue handling:** rescues are logged as their own fossil
`event_type='rescue'` (permanent, commit `c09b066`) and excluded from
turnover-event counts. Backstop despite zero-rescue tuning: any
100-tick analysis window overlapping a rescue event, plus a 200-tick
buffer on each side, is dropped from that seed's RV/S2 computation.
Rescue counts per seed per arm are reported alongside every result; a
nonzero count qualifies that arm's result rather than invalidating it
silently.

**Persistence: all 30 arm runs are archived**, not run with
`db_path: null`. Each run writes to SQLite as normal, tagged by its
`run_id` and the `config_hash` on its `runs` row. Fossil records are a
few hundred rows per run — negligible I/O against ~186s of compute per
run. Running the definition-of-done experiment with no durable,
re-derivable record would contradict the entire reason persistence was
built in the first place.

**Compute cost, measured not assumed:** 20,000 ticks took 92.96s
wall-clock on this machine (~215 ticks/sec, no persistence overhead
measured separately). At 40,000 ticks, ~186s/run. Hardware: 2 CPU
cores, ~1.7GB available memory — not "embarrassingly parallel" in
practice, 2-way parallel at most. 30 runs (10A+10B+10D; B2 adds 10
more if run) at 2-way parallelism: ~15 sequential batches x 186s =
**~47 minutes wall-clock** for the required 30 (A/B/D); +~31 min if B2
is included.

## Test construction

**Within-arm (A vs its own null, D vs its own null):** per seed,
generate 200 permutations of that seed's own epoch-count sequence,
compute S2 on each. Seed individually passes if its real S2 exceeds
the 95th percentile of its own null distribution. **Pass bar: >=7 of
10 seeds individually pass**, unchanged from the original proposal.

**Minimum N and the plateaued-vs-climbing distinction.** A seed's
result requires N>=150 turnover events to be evaluated at all
(degenerate below that — measured directly: 65-89% of windows are
`RV=0` at N=49-146). Below N=150, the seed's status depends on whether
it's still accumulating events or has stopped:
- **Still climbing** at 40,000 ticks (event count still increasing
  over the run's final third) -> **inconclusive**, excluded from the
  pass count. **>=8 of 10 seeds must be conclusive** for the >=7/10 bar
  to be evaluated at all; if fewer than 8 are conclusive, the arm's
  result is reported as an underpowered harness result, not a
  pass/fail on the hypothesis.
- **Plateaued** (event count unchanged over the run's final third) ->
  **counts as a non-pass**, not excluded. A seed frozen into permanent
  single-species stasis has demonstrably failed to show punctuation —
  that's a real result about the mechanism under this config, not
  missing data. Excluding frozen seeds would discard exactly the cases
  most relevant to whether mutation-load collapse defeats the
  mechanism.

**Cross-arm (A vs B, the primary comparative gate):** raw S2 is not
comparable across arms with different realized mutation rates — it
scales with event count/rate, so a raw-value comparison would measure
rate difference as much as burstiness. Fix: compute each seed's
**standardized excess** = `observed_S2 / median(that seed's own 200
null S2 values)` — rate-controlled by construction, since both
numerator and denominator come from the same seed's own event count.
Validated directly: well-defined and finite on all 4 spot-check seeds
(0.562-1.073 under the old/wrong statistic; the null was never
degenerate for this ratio the way it was for the original p95/median
proposal). Mann-Whitney U on the standardized-excess distributions,
Arm A vs Arm B, **one-sided (A > B), alpha=0.05, effect-size floor
rank-biserial r >= 0.3**. B2 (0.0020) is reported descriptively
alongside but does not participate in this gate.

## Combined pass criterion for Section 1.2

1. Arm A: >=7/10 conclusive seeds individually pass vs. their own
   matched permutation null (with >=8/10 conclusive required for this
   to be evaluable).
2. Arm D: same test, same bar. This is the shock-confound check — if A
   passes but D doesn't, punctuation is shock-driven, not emergent, and
   the plan's central claim fails as originally framed.
3. Arm A vs Arm B: Mann-Whitney U on standardized excess, one-sided,
   alpha=0.05, r>=0.3, in favor of A.

If any of the three fails, Section 1.2 fails, per the plan's own
words: "the tuning is wrong — fix this before moving on." Nothing
about this criterion is adjusted after seeing the real arm results.

## Predicted outcomes, stated before running (item 7)

Written down now so a failure reads as a checked prediction, not a
retroactive excuse:

- **Arm D (shocks disabled) is the most likely to fail.** Nothing
  perturbs a settling population in this arm at all; mutation-load
  freeze should be most complete here of the three. A near-total D
  failure (0-2/10 passing) would confirm this risk, not surprise
  anyone reading this after the fact.
- **Arm A carries real risk despite the favorable spot-check.** Seed 7
  froze *with* shocks present in a config nearly identical to Arm A's,
  meaning shock_probability=0.0003 may already be too rare to reliably
  rescue populations from freezing before it sets in. The spot-check
  passing (all 4/4, standardized excess 1.7-2.7) is genuine evidence
  against this risk, but per the stated statistic limitation, a pass
  from a frozen seed's single early burst is weaker evidence for the
  *repeated*-punctuation narrative than the same pass from a seed still
  actively cycling.
- **Arm B might match or beat Arm A — a real possible outcome, not
  just a formality to rule out.** A fixed rate cannot collapse via
  mutation-load the way an evolving one demonstrably does (seeds 5, 7).
  If B's turnover proves more consistent than A's, that would invert
  the plan's original hypothesis and should be reported as exactly
  that, not explained away.
- **If Arms A and/or D fail**, the leading hypothesis, pre-registered
  here rather than reached for after the fact: mutation-load collapse
  against the 0.002 floor is suppressing the evolving-rate mechanism
  under the current (correctly, for design-intent reasons) rare shock
  schedule. The floor-sensitivity check above already shows the
  central claim is floor-dependent — that's the first thing to revisit,
  not shock_probability (which was fixed for an independent, already-
  verified reason and shouldn't be re-litigated to chase a statistical
  pass).

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
# Section 1.2 results

Run at 2026-07-26T13:59:01Z. Config hash: `630498f8c60e0ec51c31d2964ebc1a58bd83b0d7bae7bcd0d1ee9dc497b68f6b`. 30 runs, 40000 ticks each, 33.7 minutes wall-clock.

## Arm A

| seed | N | raw S2 | null p95 | std. excess | plateaued | raw pass | adjudicated | rescues |
|---|---|---|---|---|---|---|---|---|
| 1 | 221 | 2.9670 | 1.7026 | 1.905 | False | True | pass | 0 |
| 2 | 311 | 3.4598 | 1.5248 | 2.485 | False | True | pass | 0 |
| 3 | 240 | 2.2220 | 1.3618 | 1.777 | False | True | pass | 0 |
| 4 | 166 | 2.9212 | 1.5190 | 2.105 | False | True | pass | 0 |
| 5 | 285 | 2.5464 | 1.2392 | 2.253 | True | True | non-pass (plateaued) | 0 |
| 6 | 493 | 1.8033 | 1.1585 | 1.704 | False | True | pass | 0 |
| 7 | 49 | 3.8761 | 1.5672 | 2.714 | True | True | non-pass (plateaued) | 0 |
| 8 | 148 | 2.2214 | 1.4732 | 1.624 | False | True | inconclusive (climbing, N<150) | 0 |
| 9 | 403 | 2.5837 | 1.4008 | 1.999 | False | True | pass | 0 |
| 10 | 327 | 3.6067 | 1.5507 | 2.505 | False | True | pass | 0 |

Adjudicated: 7/10 pass (9/10 conclusive). Raw statistical pass (pre-adjudication): 10/10. Plateaued: 2/10.
**Raw and adjudicated results differ** (10/10 raw vs 7/10 adjudicated) -- 2 seed(s) passed the statistical test while plateaued, which the pre-registration treats as a non-pass regardless of the raw S2 result.

## Arm B

| seed | N | raw S2 | null p95 | std. excess | plateaued | raw pass | adjudicated | rescues |
|---|---|---|---|---|---|---|---|---|
| 1 | 22 | 4.6882 | 1.9721 | 2.659 | True | True | non-pass (plateaued) | 0 |
| 2 | 20 | 6.2556 | 2.4919 | 2.780 | True | True | non-pass (plateaued) | 0 |
| 3 | 17 | 5.2345 | 1.9103 | 3.147 | False | True | inconclusive (climbing, N<150) | 1 |
| 4 | 36 | 4.9670 | 1.7992 | 3.043 | False | True | inconclusive (climbing, N<150) | 0 |
| 5 | 18 | 4.7971 | 1.5771 | 3.428 | True | True | non-pass (plateaued) | 0 |
| 6 | 26 | 6.2025 | 2.1349 | 3.338 | True | True | non-pass (plateaued) | 0 |
| 7 | 34 | 4.0724 | 1.4795 | 3.043 | True | True | non-pass (plateaued) | 0 |
| 8 | 14 | 6.0763 | 1.4792 | 4.859 | True | True | non-pass (plateaued) | 1 |
| 9 | 44 | 3.8721 | 1.6261 | 2.615 | False | True | inconclusive (climbing, N<150) | 0 |
| 10 | 49 | 3.3526 | 1.4364 | 2.576 | True | True | non-pass (plateaued) | 0 |

Adjudicated: 0/10 pass (7/10 conclusive). Raw statistical pass (pre-adjudication): 10/10. Plateaued: 7/10.
**Raw and adjudicated results differ** (10/10 raw vs 0/10 adjudicated) -- 7 seed(s) passed the statistical test while plateaued, which the pre-registration treats as a non-pass regardless of the raw S2 result.

## Arm D

| seed | N | raw S2 | null p95 | std. excess | plateaued | raw pass | adjudicated | rescues |
|---|---|---|---|---|---|---|---|---|
| 1 | 217 | 2.3774 | 1.4039 | 1.826 | False | True | pass | 0 |
| 2 | 225 | 2.6273 | 1.3393 | 2.165 | False | True | pass | 0 |
| 3 | 205 | 2.6579 | 1.5654 | 1.864 | False | True | pass | 0 |
| 4 | 181 | 4.3762 | 1.8159 | 2.670 | False | True | pass | 0 |
| 5 | 374 | 2.7769 | 1.2716 | 2.376 | True | True | non-pass (plateaued) | 0 |
| 6 | 343 | 2.4634 | 1.2982 | 2.088 | False | True | pass | 0 |
| 7 | 254 | 1.9586 | 1.2202 | 1.771 | False | True | pass | 0 |
| 8 | 207 | 2.2719 | 1.3049 | 1.901 | False | True | pass | 0 |
| 9 | 316 | 3.0989 | 1.6355 | 2.049 | False | True | pass | 0 |
| 10 | 96 | 4.2493 | 1.8491 | 2.534 | False | True | inconclusive (climbing, N<150) | 0 |

Adjudicated: 8/10 pass (9/10 conclusive). Raw statistical pass (pre-adjudication): 10/10. Plateaued: 1/10.
**Raw and adjudicated results differ** (10/10 raw vs 8/10 adjudicated) -- 1 seed(s) passed the statistical test while plateaued, which the pre-registration treats as a non-pass regardless of the raw S2 result.

## Arm A vs Arm B (primary comparative gate)

Mann-Whitney U on standardized excess, one-sided (A > B): U=3.0, p=0.9998, rank-biserial r=-0.940.
Significant at alpha=0.05: False. Effect-size floor (|r|>=0.3) met: True.
Gate passes only if both are true: False.

## Combined Section 1.2 pass criterion

1. Arm A >=7/10: 7/10 -> PASS
2. Arm D >=7/10: 8/10 -> PASS
3. Arm A vs B Mann-Whitney gate: FAIL

**Section 1.2 overall: FAIL**

Per the pre-registration: this criterion is not adjusted after seeing these numbers. A FAIL here is a legitimate, informative result about the mutation-rate floor and/or shock frequency at the current config, not a defect in the harness.