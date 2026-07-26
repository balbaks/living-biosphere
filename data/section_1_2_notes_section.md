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