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

# Post-result audit: sparsity-bias objection, tested and withdrawn

After the FAIL result above, a live question was raised: does gate 3's
failure (and, more importantly, gates 1/2's passes) reflect a real
effect, or a low-N artifact of `standardized_excess =
observed_S2 / median(null_S2)`? The concern: at extreme sparsity,
`median(null_S2)` is small and unstable, and dividing by it could
inflate the ratio regardless of arm -- which would threaten the
*passing* gates as much as excuse the failing one, since Arm A's
lowest-N seed (49) and Arm D's lowest (96) used the exact same
construction.

**Settled on synthetic ground truth, same method as the S1-vs-S2
choice, independent of these results.** Two synthetic process shapes,
each held at a *fixed* true structure while only N varied from 14 to
500 (matching the full observed range across all three arms), 30
realizations per N, 200-permutation null each:

- **Uniform (null-consistent) process:** mean standardized excess
  stayed at 0.982-1.016 across the entire N range -- flat, no trend.
  Confirms the ratio isn't inflated by construction when the true
  process matches the null.
- **Fixed 50% clustering fraction:** mean standardized excess *grew*
  monotonically with N -- 1.012 at N=14 up to 4.444 at N=500. The
  opposite of the suspected bias: a moderate, fixed-strength bursty
  signal is *harder* to detect at low N, not easier.
- **Single-burst-then-permanent-silence** (the actual frozen-seed
  shape -- matches what "plateaued" looks like as a raw count series):
  also grew monotonically with N -- 3.513 at N=14 up to 8.530 at
  N=500. Arm B's real observed range (2.6-4.9 at N=14-49) sits
  consistently within this curve's low-N region, meaning Arm B's
  numbers are exactly what a genuinely near-maximally-clustered
  sequence should produce at that N -- not an inflated artifact.

**Result: no N-dependent bias found, in either direction, for either
process shape tested.** Task 2's stated resolution applies: the
objection is withdrawn on the record, unqualified. Gates 1, 2, and 3
all stand exactly as computed in the results above; none needs
revision. Raising the objection was reasonable given the mechanism
was plausible on its face, but it doesn't survive the check, and the
check -- not the plausibility of the story -- is what decides it.

# Arm B collapse -- a new, unregistered hypothesis, not a rescued claim

**This was not pre-registered and is not a Section 1.2 result.** It is
what the run surfaced, reported as a candidate for the next
pre-registration, not smuggled into this one's conclusion.

Quantified directly from `data/section_1_2_raw_results.json`:

| | Arm A (evolving) | Arm B (fixed 0.0053) | Arm D (evolving, no shocks) |
|---|---|---|---|
| N per seed | 221,311,240,166,285,493,49,148,403,327 | 22,20,17,36,18,26,34,14,44,49 | 217,225,205,181,374,343,254,207,316,96 |
| N: min/max/median | 49/493/262.5 | 14/49/24.0 | 96/374/221.0 |
| freeze rate | 2/10 | **7/10** | 1/10 |
| time-to-freeze (plateaued seeds only, tick) | 9370, 17380 | 220, 290, 440, 550, 650, 3840, 7500 | 17620 |

Arm B's median N (24.0) is roughly a **tenth** of Arm A's (262.5).
70% of Arm B seeds froze, against 20% for Arm A and 10% for Arm D.
And Arm B doesn't just freeze more often -- when it does, it freezes
almost immediately: 5 of its 7 plateaued seeds stopped turning over at
or before tick 650 (out of a 40,000-tick run) -- ticks 220, 290, 440,
550, 650 -- while Arm A's and Arm D's plateaued seeds all froze much
later (9370-17620) -- roughly a quarter to nearly half the run in, not
the first two percent.

**Candidate hypothesis for the next pre-registration**: a fixed
mutation rate, unable to reduce itself the way an evolving one can,
still lets the population converge quickly to a locally-stable
genotype -- but then has no mechanism to sustain further turnover,
since it can neither adapt toward stability (like Arm A's typical
lineage) nor occasionally spike into an "explorer" regime (like Arm
A's rare high-mutation tail, up to 0.1). The evolving mechanism may
matter less for producing *burstiness* (which gate 3 tested and which
failed) and more for simply **keeping the system turning over at
all** -- a level/duration question, not a dispersion question.

If pursued, this needs its own pre-registration: a statistic like
sustained-turnover rate or time-to-freeze itself, validated on
synthetic ground truth the same way S2 was, with its own null and its
own arms -- not a re-litigation of this run's dispersion-based result.

# Corrected prediction record

Section 1.2's pre-registration predicted: "Arm D (shocks disabled) is
the most likely to fail... nothing perturbs a settling population in
this arm at all." **This was wrong.** Arm D passed 8/10, more than
Arm A's 7/10, and had the lowest freeze rate of any arm (1/10, vs
Arm A's 2/10 and Arm B's 7/10). Recorded here rather than dropped
quietly, per the standard set for this whole document.

**Honest one-line summary of Section 1.2, combining the FAIL result
with the corrected prediction**: turnover structure exists in this
world (Arms A and D both clear the within-arm dispersion test), it is
not shock-driven (D matches or exceeds A with shocks fully disabled),
and there is no evidence from this run that the *evolving* mutation
rate is what produces it (gate 3 fails, and fails in the direction of
B showing higher raw dispersion, not lower). What the evolving
mechanism may actually be doing -- keeping turnover alive at all,
rather than making it burstier -- is a different, unregistered
question the Arm B write-up above raises for next time.

# Section 1 definition-of-done amendment

Section 1.2's dispersion criterion (S2, punctuated equilibrium) failed
and is retired, not retried. Punctuated equilibrium was the original
hypothesis. It was pre-registered blind, validated on synthetic ground
truth, executed honestly, and audited for bias when the result looked
unfavorable -- the audit came back against the objection that would
have rescued it, not in its favor (see "Post-result audit" above).
The result stands: this world's turnover structure isn't burstier
under an evolving mutation rate than under a fixed one. Retuning the
simulation until a dispersion criterion passes would optimize toward
proving a hypothesis already fairly rejected, not toward understanding
the system.

**Replacement definition of done for Section 1**: does a heritable
mutation rate sustain evolutionary turnover materially longer than any
fixed rate? Grounded directly in the Arm B collapse above (median N a
tenth of Arm A's, 7/10 freeze rate vs 2/10, freezing almost
immediately when it does).

**Epistemic status, stated plainly rather than dressed up as a clean
prediction**: this hypothesis was formed after seeing Arm B's data.
The test below is confirmatory of an observation already made, not an
independent blind prediction the way the original punctuated-
equilibrium test was. A pass in the pre-registration below carries
less evidentiary weight than a blind pre-registration would have --
it is evidence consistent with a pattern already seen in the data that
generated the hypothesis, which is weaker confirmation than predicting
something not yet observed. This is not softened anywhere below.

# Section 1 (revised) pre-registration -- persistence/survival test

Pre-registered 2026-07-26, before any arm of this design has been run.
Config hash: `1b151603eb662fc4c94dcecf91ada7d08a34a181152dd8348aacf94475f45fb4`
(unchanged since the Section 1.2 pre-registration above -- no
simulation code or config has changed for this design).

## What's being tested

Not burstiness (retired above). Whether a heritable, evolving mutation
rate sustains turnover for materially longer than any single fixed
rate -- the hypothesis the Arm B collapse raised.

## Defeating the level confound: a fixed-rate sweep, not one point

Arm B's fixed 0.0053 confounded "evolving vs fixed" with "higher vs
lower than A's realized median (0.0020)." A single fixed comparison
point cannot separate those. Five fixed levels, spanning and exceeding
Arm A's observed range: **0.001, 0.002, 0.005, 0.02, 0.05**. Plus the
evolving arm. Six arms total.

**Floor-clamping checked directly, not assumed**: `fixed_mutation_rate`
overwrites the gene after `Genome.__init__`'s clip already ran,
bypassing both `GENE_MIN[MUT_RATE]` (0.001) and a separate, stricter
floor hardcoded inside `mutate()` (0.002) that only applies to
*evolving* genomes. Verified empirically: requesting 0.001, or even
0.0005, sticks exactly, unclamped. All five sweep levels are genuinely
distinct arms -- no wasted sweep point from an unnoticed floor
collision.

## Primary statistic: total turnover count over 40,000 ticks

**Changed from the original proposal (survival analysis) after a
specific, decisive objection**: log-rank power is driven by observed
*event* count (freezes), not seed count. Last round, the evolving arm
froze in only 2/10 seeds -- log-rank would have ~2 events to work
with against 8 censored observations, near-powerless, indistinguishable
from a true null regardless of the actual effect. Turnover count is
continuous and every seed contributes a value regardless of whether it
froze, which is why it's primary here instead.

**Power, checked directly against last round's actual data, not
assumed**: Mann-Whitney U on raw turnover count, Arm A (evolving) vs
Arm B (fixed 0.0053): U=99.5, **p=0.000106, r=0.990** -- a near-maximal
effect (the only rank overlap is A's minimum, 49, exactly equaling B's
maximum, 49). Bootstrap power simulation (resampling n=10 with
replacement from each arm's observed distribution, 2000 trials):
**power = 1.000 at n=10/arm, and still 1.000 at n=5/arm.** This
statistic is not underpowered for an effect of the size already
observed. Caveat: this benchmarks specifically against the 0.0053
comparison -- the other four sweep levels' true effect sizes are
unknown until run, but n=10/arm is well-justified given how large the
benchmark effect was.

**Test**: nonparametric (Mann-Whitney, pairwise) across the six arms.
Multiplicity handling (see below) governs how the six pairwise
contrasts combine into the overall claim.

## Secondary/corroborating statistic: survival analysis (Kaplan-Meier + log-rank)

Kept as corroborating evidence, not the gate. Time-to-event framing is
still the right model for *why* a seed stopped turning over, even
though it lacks power as the primary test.

**Freeze definition -- per-arm derived, not universal, per the bias
check below.** A seed's last-turnover-event tick is treated as an
*observed freeze* only if the trailing silence to run-end exceeds that
**arm's own** p99.9 of the healthy inter-event-gap distribution,
computed from that same arm's non-plateaued seeds once the sweep
finishes running. Otherwise the seed is right-censored.

**Why per-arm, not universal, stated with the evidence**: the
universal threshold from the original design (17,165 ticks) was
derived mostly from evolving-arm data. Checked directly: Arm A+D's
own (corrected, evolving-only) non-plateaued gap distribution has
mean 143.2, p95=370, p99.9=11,394 (built on only ~4.3 gaps out of
4336 -- an unstable estimate on its own). Arm B's non-plateaued gap
distribution (only 3 seeds, 94 gaps, but enough to make the point):
mean **1122** (~8x evolving arms'), p95=**10,924** (~29x evolving
arms'). The single largest gap in the entire dataset (23,110 ticks)
belongs to Arm B, not an evolving arm, and is an *internal* gap in a
still-active seed (8 more events followed it) -- not even the
seed's trailing gap. A universal threshold anywhere near evolving
arms' p99.9 sits inside Arm B's *normal* range, which would
systematically over-detect freezes in low-turnover fixed arms exactly
where the hypothesis needs a fair comparison.

**Retrospective flip-check, reported honestly**: re-classifying Arm
B's 7 already-plateaued seeds against an Arm-B-specific threshold (its
own observed max healthy gap, 23,110) instead of the universal one
produces **zero flips** -- their trailing silences (32,500-39,780
ticks) are extreme enough to read as frozen under any reasonable
threshold. The bias is real and demonstrated in the underlying
distributions; it didn't happen to change last round's classifications.
It is not assumed to be equally inconsequential for the other four
sweep levels, whose collapse severity (if any) is unknown until run --
per-arm derivation is required for this design regardless.

**Time variable and censoring, stated explicitly**: time variable is
the last-turnover-event tick. Effective censoring time is
`40,000 - K_arm`, where `K_arm` is that arm's own derived threshold --
*not* 40,000 uniformly, since a freeze in the last `K_arm` ticks of
the run cannot be confirmed (there isn't enough runway left to observe
the required silence). Because `K_arm` differs by arm, the six arms'
Kaplan-Meier curves will have different effective censoring
boundaries. This is a real limitation of the secondary analysis,
stated rather than smoothed over -- acceptable because survival
analysis is corroborating here, not the gate.

**Validation approach, scoped differently than S1-vs-S2's, and that
difference is stated rather than hidden**: Kaplan-Meier and log-rank
are decades-old, well-established methods, not novel statistics --
their validity isn't being re-derived from scratch the way S1 vs S2
needed. A lightweight synthetic sanity check (known-different survival
times between two synthetic groups -> confirm log-rank detects it;
known-identical distributions -> confirm no spurious significance)
substitutes for the full N-sweep bias audit S2 required. `lifelines`
is added as a new dependency for the implementation -- correctness on
censored data is exactly where a hand-rolled implementation risks a
subtle bug a well-tested library wouldn't have.

## Multiplicity handling

**"Evolving beats every fixed level"** is an intersection-union claim
requiring all five pairwise contrasts (evolving vs each of the five
levels) to hold. Conservative by construction, no multiple-comparison
correction needed for this claim specifically.

**Failure branch A ("evolving matches or is beaten by the best fixed
level") pre-specifies its comparator now, not after seeing which level
scores best**: the primary pairwise contrast for this branch is
**evolving vs. fixed 0.002** (matching Arm A's realized median from
the original run) -- chosen because it's a property of the system
already established before this design, not picked because it will
turn out to score best. The other four levels stay in the
intersection-union test and are reported descriptively; they are not
mined post-hoc for "the best" comparator.

## Seeds, run length, compute cost

40,000 ticks (unchanged -- already shown to give slower-freezing arms
room to either freeze or clearly not). 10 seeds per arm (power
analysis above supports this comfortably for an effect of the
benchmark size; not reduced, since compute cost was not the
constraint the power check flagged).

**Primary sweep: 6 arms x 10 seeds = 60 runs.** At ~186s/run measured
previously, 2-way parallel: ~62 minutes wall-clock.

**Floor-sensitivity follow-up, scoped as specified**: 2 additional
mutation-rate-floor values (half and double the current 0.002),
evolving arm only, 10 seeds each = 20 more runs (~62 more minutes).
Answers whether evolving-rate survival depends on where this wall is
set, without a full floor x fixed-rate combinatorial grid.

**Total: 80 runs, ~124 minutes (~2 hours).**

## Predicted outcomes and failure branches, stated before running

- Expected if the hypothesis holds: evolving's turnover count
  (primary) and survival time (secondary) exceed every fixed level's,
  with the evolving-vs-0.002 contrast significant and the
  intersection-union claim holding across all five levels.
- Failure branch A: evolving matches or is beaten by the pre-specified
  0.002 comparator -> a well-chosen static rate does as well; the
  evolving mechanism doesn't uniquely help.
- Failure branch B: evolving is beaten by *all* five levels, including
  very low ones -> the heritable mechanism is actively harmful for
  persistence, a stronger negative result than branch A.
- "Evolving does nothing useful" concretely means: the evolving-vs-
  0.002 Mann-Whitney is not significant, or favors 0.002.
- Floor-sensitivity failure mode: if evolving's advantage (if any)
  appears or disappears depending on the floor value tested, that is a
  finding about this config's floor placement, not about evolvability
  in general -- stated now so it reads as anticipated, not
  discovered.

## Epistemic status, restated from the amendment above

This entire pre-registration is confirmatory, not blind -- it was
designed after seeing the Arm B collapse that motivates it. A pass
below is evidence consistent with an already-observed pattern, not an
independent prediction verified against new information. Weighted
accordingly when interpreting any result.
# Section 1 (revised) results -- persistence/survival test

Run at 2026-07-26T17:12:22Z. 80 runs, 40000 ticks each, 113.3 minutes wall-clock.

## Phase 1: freeze-threshold derivation (computed before any turnover count was examined)

Naive pooled/universal threshold: 14526.8 ticks (from 10850 pooled gaps across all arms).

| arm | healthy seeds | gaps | mean gap | median gap | p95 gap | per-arm threshold (p99.9) |
|---|---|---|---|---|---|---|
| evolving_floor_0.001 | 7 | 1995 | 125.4 | 30.0 | 280.0 | 14943.6 |
| evolving_floor_0.002 | 8 | 2301 | 130.6 | 30.0 | 370.0 | 8304.0 |
| evolving_floor_0.004 | 9 | 2602 | 131.6 | 30.0 | 379.5 | 8571.6 |
| fixed_0.001 | 0 | 0 | 0.0 | 0.0 | n/a | 0.0 |
| fixed_0.002 | 1 | 41 | 972.7 | 20.0 | 1200.0 | 30492.4 |
| fixed_0.005 | 3 | 128 | 849.5 | 20.0 | 4030.0 | 28410.5 |
| fixed_0.02 | 7 | 874 | 304.6 | 50.0 | 850.0 | 19829.3 |
| fixed_0.05 | 10 | 2909 | 130.9 | 50.0 | 360.0 | 6078.9 |

**Flip count: 4 of 80 seeds' freeze classification changed between the universal and per-arm threshold** -- unlike the retrospective check on the prior round's data (which found zero flips), the bias mattered this time. Flipped seeds:

| arm | seed | trailing silence | arm threshold | universal threshold |
|---|---|---|---|---|
| evolving_floor_0.002 | 1 | 12900 | 8304.0 | 14526.8 |
| fixed_0.005 | 7 | 14830 | 28410.5 | 14526.8 |
| fixed_0.02 | 8 | 16100 | 19829.3 | 14526.8 |
| fixed_0.05 | 7 | 7750 | 6078.9 | 14526.8 |

## Phase 2: primary statistic -- total turnover count (N) over 40,000 ticks

| arm | N per seed | median | mean |
|---|---|---|---|
| evolving_floor_0.001 | [88, 92, 158, 259, 279, 291, 296, 319, 336, 421] | 285.0 | 253.9 |
| evolving_floor_0.002 | [49, 148, 166, 221, 240, 285, 311, 327, 403, 493] | 262.5 | 264.3 |
| evolving_floor_0.004 | [90, 146, 165, 170, 247, 254, 316, 415, 431, 467] | 250.5 | 270.1 |
| fixed_0.001 | [15, 16, 18, 21, 22, 22, 23, 27, 29, 46] | 22.0 | 23.9 |
| fixed_0.002 | [14, 14, 14, 15, 18, 18, 19, 20, 22, 42] | 18.0 | 19.6 |
| fixed_0.005 | [14, 20, 22, 25, 27, 27, 33, 41, 50, 63] | 27.0 | 32.2 |
| fixed_0.02 | [16, 17, 20, 29, 35, 108, 116, 147, 192, 254] | 71.5 | 93.4 |
| fixed_0.05 | [77, 149, 194, 263, 294, 348, 380, 383, 394, 437] | 321.0 | 291.9 |

Pairwise Mann-Whitney, evolving_floor_0.002 vs each fixed level (one-sided, evolving > fixed):

| comparator | U | p | r | significant (a=0.05) |
|---|---|---|---|---|
| fixed_0.001 | 100.0 | 0.00009 | 1.000 | yes |
| fixed_0.002 **(pre-specified primary comparator)** | 100.0 | 0.00009 | 1.000 | yes |
| fixed_0.005 | 98.0 | 0.00016 | 0.960 | yes |
| fixed_0.02 | 89.0 | 0.00181 | 0.780 | yes |
| fixed_0.05 | 42.0 | 0.73974 | -0.160 | **no** |

**Intersection-union claim (evolving beats all five fixed levels): FAILS**
Fails specifically on **fixed_0.05** (p=0.73974, r=-0.160) -- evolving does not significantly beat this level, and the point estimate (negative r) if anything slightly favors the fixed rate.

**Pre-specified primary contrast (evolving_floor_0.002 vs fixed_0.002): evolving wins, p=0.00009, r=1.000**

## Phase 3: secondary statistic -- survival analysis (corroborating)

| arm | observed freezes | median survival |
|---|---|---|
| evolving_floor_0.001 | 3/10 | inf |
| evolving_floor_0.002 | 3/10 | inf |
| evolving_floor_0.004 | 1/10 | inf |
| fixed_0.001 | 10/10 | 400.0 |
| fixed_0.002 | 9/10 | 410.0 |
| fixed_0.005 | 6/10 | 540.0 |
| fixed_0.02 | 2/10 | inf |
| fixed_0.05 | 1/10 | inf |

Log-rank, evolving_floor_0.002 vs fixed_0.002: p=0.00007
Multivariate log-rank, all 8 arms: p=0.00000

**Primary and secondary statistics agree**: fixed levels 0.001/0.002/0.005 (which the primary test shows evolving beating) show high freeze rates in the secondary analysis; fixed 0.02 and especially 0.05 (which the primary test shows evolving failing to beat) show low freeze rates comparable to the evolving arms. No disagreement between the two tests to report.

## Floor-sensitivity comparison (evolving arm only, as designed)

| floor | median N | mean N | observed freezes |
|---|---|---|---|
| 0.001 | 285.0 | 253.9 | 3/10 |
| 0.002 | 262.5 | 264.3 | 3/10 |
| 0.004 | 250.5 | 270.1 | 1/10 |

Floor value (0.001/0.002/0.004) does not produce a large or monotonic difference in either turnover count or freeze rate within this range -- median N spans 250.5-285.0 and freeze rate spans 1-3 of 10 across all three, no clear trend. The evolving mechanism's performance in this design does not appear sensitive to where this particular wall sits, at least across the range tested.

## Honest headline summary

**The intersection-union claim ("evolving beats every fixed level") FAILS, on fixed_0.05.** Evolving does decisively beat low fixed rates (0.001, 0.002, 0.005) and beats 0.02 too -- but fixed_0.05's median turnover count (321.0) is actually the *highest of all eight arms tested*, including every evolving-floor variant. The pre-specified primary contrast (evolving vs. its own realized median, 0.002) succeeds clearly (p=0.00009) -- this is not a null result across the board, it is a bounded one: **evolving beats a low/typical fixed rate, but does not beat a well-chosen high fixed rate.**

This means the heritable mutation-rate mechanism's real, demonstrated value in this world is *avoiding the low-rate collapse it would otherwise be prone to* (the Arm B finding that motivated this whole test) -- not *outperforming every possible alternative*. A constant rate near 0.05, chosen with no adaptation at all, sustains turnover just as well or better. This is a meaningfully weaker claim than "evolving mutation rate is what keeps this world alive," and it should be described that way going forward, not rounded up.

Per the epistemic-status paragraph above: this whole test was confirmatory, designed after seeing the Arm B collapse. A bounded pass here carries correspondingly bounded weight -- it neither vindicates nor refutes the original evolvability narrative cleanly; it narrows it.

Floor sensitivity (0.001/0.002/0.004): no material effect on either statistic within this range -- the evolving mechanism's performance doesn't depend on where this particular wall sits, at least here.

Per standing instruction: no tuning, no threshold revision, no arm added in response to these results until they are recorded, committed, and read.

## Process note: a pattern in the near-misses, worth watching

Two things were caught before commit this session, both by the same
mechanism (checking the actual numbers rather than trusting the
transcription), and both pointed in the *flattering* direction before
being caught:

- The S1 exposure numbers, first transcribed into the Section 1.2
  pre-registration, duplicated one value and dropped another.
- This round's "which comparator fails the intersection-union claim"
  logic had a broken `min()` that pointed at `fixed_0.001` (a level
  evolving beats decisively) instead of the actual culprit,
  `fixed_0.05` (the one that breaks the claim) -- the wrong answer
  here would have hidden the actual finding, not just misstated a
  number.

Neither was caught by care alone -- both were caught by a verification
step (re-checking against raw tool output, or re-deriving the logic
by hand) that happened to run before the commit, not by the writing
process itself. Worth treating as a standing prior: any generated or
transcribed number that happens to land in the flattering direction
gets the verification step *first*, not after something looks off.

# Section 1 extension pre-registration -- bracketing the sweep's maximum

Pre-registered 2026-07-26, before running, following the same
gate as every other test this session. Config hash unchanged:
`1b151603eb662fc4c94dcecf91ada7d08a34a181152dd8348aacf94475f45fb4`.

**The question.** `fixed_0.05` was the top of the five-level sweep,
chosen as the top of Arm A's *observed* range under a hypothesis about
where evolving populations settle -- not chosen as a candidate maximizer
of turnover. It won. That leaves the sweep's ceiling unbracketed: is
turnover monotonically increasing in fixed mutation rate over the
tested range, or does 0.05 sit near a genuine optimum? These have
different implications. Monotonic increase means the sweep never
found the top, and the comparison to evolving was never really fair in
the intended sense. A plateau or decline means 0.05 is a real ceiling
and the bounded-pass framing already recorded stands as the actual
answer, not a placeholder.

**Epistemic status, stated as plainly as the last amendment.** This
extension was chosen *after* seeing `fixed_0.05` win. It is not a
blind pre-registration -- it's confirmatory of the specific observation
that the sweep's top level was also its best performer, and it carries
correspondingly less weight than an independent prediction would.

**Design.** Two additional fixed levels, `0.1` and `0.2`, 10 seeds
each, same 40,000-tick run length, same primary statistic (turnover
count) and same phase-1-then-phase-2 discipline as the main survival
test. ~20 runs, measured throughput from the last round (~170s/run,
2-way parallel) implies roughly 28-30 minutes wall-clock.

**Predictions and both branches, stated before running:**
- If turnover keeps climbing (0.1 and/or 0.2 beat 0.05's median): the
  honest conclusion is that the sweep never bracketed the true maximum,
  and — combined with the fact that Arm A's evolving population
  converges toward the floor (0.002), roughly 25x below the
  level that already outperforms it — evolution is not finding
  whatever optimum exists either. That would sharpen, not soften,
  the bounded-pass framing: not just "a well-chosen high rate does as
  well," but "evolution is moving in the opposite direction from
  whatever is actually best for sustained turnover."
- If turnover plateaus or falls at 0.1/0.2: 0.05 is near-optimal within
  the range that matters, and the already-recorded bounded-pass result
  stands unchanged -- this extension would confirm the comparison was
  fair, not overturn it.

**What this cannot establish, regardless of outcome, stated before
running so neither branch gets over-read**: turnover count is not
fitness. Selection optimizes reproductive success, not turnover count
-- a constant rate beating the evolving mechanism on turnover is not,
by itself, evidence that evolution is failing at its own objective.
It is evidence about what sustains *this specific measured quantity*,
which was chosen as a proxy for "the world staying interesting," not
as a definition of what selection is actually for. Both outcomes below
should be read against that limit, not past it.
