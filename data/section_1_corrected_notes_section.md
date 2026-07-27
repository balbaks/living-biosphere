Run at 2026-07-26T23:20:34Z. 100 runs, 40000 ticks each, 122.6 minutes wall-clock. Fresh database (`data/section_1_corrected_results.db`), not appended to the superseded one.

## Prediction check (stated before this ran)

| arm | old implied median N | new direct median N | match |
|---|---|---|---|
| evolving_floor_0.001 | 571.0 | 571.0 | MATCH |
| evolving_floor_0.002 | 527.0 | 527.0 | MATCH |
| evolving_floor_0.004 | 503.0 | 503.0 | MATCH |
| fixed_0.001 | 45.0 | 45.0 | MATCH |
| fixed_0.002 | 37.0 | 37.0 | MATCH |
| fixed_0.005 | 55.0 | 55.0 | MATCH |
| fixed_0.02 | 144.0 | 144.0 | MATCH |
| fixed_0.05 | 643.5 | 643.5 | MATCH |
| fixed_0.1 | 1269.0 | 1269.0 | MATCH |
| fixed_0.2 | 38163.0 | 38163.0 | MATCH |

**All ten arms matched exactly** -- confirms the fix changed only fossil-record bookkeeping, not simulation physics or RNG consumption, exactly as predicted.

## Phase 1: freeze-threshold derivation (corrected N)

Universal threshold: 510.0 ticks (from 391475 pooled gaps).

Flip count (per-arm vs universal): **24 of 100** -- higher than either prior round (4/80 in the buggy main run, 0/80 retrospectively on the very first round), consistent with the corrected, larger N values giving the per-arm gap distributions more data and more spread.

## Phase 2: primary statistic -- total turnover count (N), CORRECTED

| arm | median N | mean N | median emergences | median extinctions |
|---|---|---|---|---|
| evolving_floor_0.001 | 571.0 | 508.9 | 286.0 | 285.0 |
| evolving_floor_0.002 | 527.0 | 530.1 | 264.5 | 262.5 |
| evolving_floor_0.004 | 503.0 | 541.8 | 252.5 | 250.5 |
| fixed_0.001 | 45.0 | 48.8 | 23.0 | 22.0 |
| fixed_0.002 | 37.0 | 40.3 | 19.0 | 18.0 |
| fixed_0.005 | 55.0 | 65.4 | 28.0 | 27.0 |
| fixed_0.02 | 144.0 | 187.8 | 72.5 | 71.5 |
| fixed_0.05 | 643.5 | 585.3 | 322.5 | 321.0 |
| fixed_0.1 | 1269.0 | 1107.7 | 636.5 | 632.5 |
| fixed_0.2 | 38163.0 | 35861.0 | 19083.5 | 19079.5 |

| comparator | U | p | r | significant | unchanged from buggy run? |
|---|---|---|---|---|---|
| fixed_0.001 | 100.0 | 0.00009 | 1.000 | yes | yes |
| fixed_0.002 **(pre-specified primary comparator)** | 100.0 | 0.00009 | 1.000 | yes | yes |
| fixed_0.005 | 98.0 | 0.00016 | 0.960 | yes | yes |
| fixed_0.02 | 89.0 | 0.00181 | 0.780 | yes | yes |
| fixed_0.05 | 42.0 | 0.73974 | -0.160 | **no** | yes |
| fixed_0.1 | 7.0 | 0.99950 | -0.860 | **no** | yes |
| fixed_0.2 | 0.0 | 0.99993 | -1.000 | **no** | yes |

**Intersection-union claim: FAILS** -- same as the buggy run, failing on the same comparator (fixed_0.05).
**Pre-specified primary contrast: evolving wins, p=0.00009, r=1.000** -- identical to the buggy run.

Median N across the extended ceiling: fixed_0.05=643.5 -> fixed_0.1=1269.0 -> fixed_0.2=38163.0 -- same monotonic-climb pattern as before, now at roughly double the absolute values.

## Phase 3: secondary statistic -- survival analysis (corroborating)

| arm | observed freezes | median survival |
|---|---|---|
| evolving_floor_0.001 | 5/10 | 31820.0 |
| evolving_floor_0.002 | 3/10 | inf |
| evolving_floor_0.004 | 2/10 | inf |
| fixed_0.001 | 10/10 | 400.0 |
| fixed_0.002 | 9/10 | 410.0 |
| fixed_0.005 | 6/10 | 540.0 |
| fixed_0.02 | 3/10 | inf |
| fixed_0.05 | 1/10 | inf |
| fixed_0.1 | 0/10 | inf |
| fixed_0.2 | 0/10 | inf |

Log-rank, evolving(0.002) vs fixed_0.002: p=0.00007 (buggy run: p=0.00007 -- effectively identical)
Multivariate log-rank, all 10 arms: p=0.00000

## Verdict: the bug did not change any conclusion, but had to be fixed regardless

Every pairwise Mann-Whitney p-value and effect size in Phase 2 is unchanged (to the precision reported) between the buggy and corrected runs -- the intersection-union claim fails on exactly the same comparator (fixed_0.05), the pre-specified primary contrast succeeds identically, and the monotonic-climb-through-0.2 pattern from the extension is preserved at the same relative magnitudes. Mann-Whitney is rank-based, and the correction (roughly doubling N per the near-uniform ~50% undercount) preserved rank order almost perfectly within and across arms -- which is why the numbers moved and the conclusions didn't.

This does not make the bug acceptable to have shipped. It was a real defect, present since Section 1.1, that silently discarded half the intended signal in every turnover measurement this session -- it happened not to change these particular comparisons, but there was no way to know that without finding and fixing it and checking. A different set of arms, or a comparison closer to the fixed_0.05 boundary, could easily have gone the other way.

**All 'Superseded results' sections above are now formally replaced by this corrected run. The bounded-pass framing, the fixed_0.05 finding, and the monotonic-climb-through-0.2 finding all stand -- now on a verified-correct instrument, not an assumed-correct one.**