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
