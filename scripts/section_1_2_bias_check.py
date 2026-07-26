#!/usr/bin/env python3
"""Synthetic ground-truth check for whether standardized_excess
(observed_S2 / median(null_S2)) is systematically biased as a function
of N. Run after the Section 1.2 results (data/section_1_2_raw_results.json)
raised the question of whether gate 3's failure -- or gates 1/2's
passes -- reflected a low-N artifact rather than a real effect.

Tests three synthetic process shapes at fixed structure across N=14..500
(the full range observed across all three arms): uniform (null-consistent),
fixed 50% clustering fraction, and single-burst-then-permanent-silence
(the actual shape of a "plateaued" seed). If the ratio were biased at low
N, a FIXED true process should show a margin that shrinks as N shrinks.
It doesn't, for either bursty shape tested -- see NOTES.md, "Post-result
audit" section, for the numbers and the resulting withdrawal of the
low-N-bias objection.
"""
import sys
from pathlib import Path

import numpy as np

WINDOW = 10
STEP = 1
N_EPOCHS = 4000
N_PERMS = 200
N_REALIZATIONS = 30
NS = [14, 20, 30, 49, 75, 100, 150, 200, 285, 350, 500]


def make_uniform(n_epochs, n_events, seed):
    r = np.random.default_rng(seed)
    counts = np.zeros(n_epochs, dtype=int)
    for p in r.integers(0, n_epochs, size=n_events):
        counts[p] += 1
    return counts


def make_bursty_fixed_fraction(n_epochs, n_events, seed, burst_fraction=0.5, n_clusters=8, cluster_span=10):
    r = np.random.default_rng(seed)
    counts = np.zeros(n_epochs, dtype=int)
    n_burst = int(n_events * burst_fraction)
    n_scatter = n_events - n_burst
    nc = max(1, min(n_clusters, n_epochs - cluster_span))
    epc = max(1, n_burst // nc)
    rem = n_burst - epc * nc
    starts = r.choice(max(1, n_epochs - cluster_span), size=nc, replace=False)
    for i, start in enumerate(starts):
        n_this = epc + (1 if i < rem else 0)
        for o in r.integers(0, cluster_span, size=n_this):
            counts[start + o] += 1
    for p in r.integers(0, n_epochs, size=n_scatter):
        counts[p] += 1
    return counts


def make_single_burst_then_silence(n_epochs, n_events, seed, cluster_span=30):
    """The 'plateaued' shape: all events in one early dense cluster,
    then nothing for the rest of the run."""
    r = np.random.default_rng(seed)
    counts = np.zeros(n_epochs, dtype=int)
    start = r.integers(0, n_epochs // 4)
    for o in r.integers(0, cluster_span, size=n_events):
        counts[start + o] += 1
    return counts


def s2_fano(counts):
    totals = np.array([counts[s:s + WINDOW].sum() for s in range(0, len(counts) - WINDOW + 1, STEP)])
    return totals.var() / totals.mean() if totals.mean() > 0 else float("nan")


def standardized_excess(counts, seed, n_perms=N_PERMS):
    r = np.random.default_rng(seed + 555555)
    obs = s2_fano(counts)
    nulls = np.array([s2_fano(r.permutation(counts)) for _ in range(n_perms)])
    med = np.median(nulls)
    return obs / med if med > 0 else float("inf")


def run_series(name, generator, **kwargs):
    print(f"=== {name} ===")
    print(f'{"N":>5} {"mean_std_excess":>16} {"median":>8} {"std":>8}')
    for N in NS:
        vals = np.array([
            standardized_excess(generator(N_EPOCHS, N, real, **kwargs), real)
            for real in range(N_REALIZATIONS)
        ])
        print(f"{N:>5} {vals.mean():>16.3f} {np.median(vals):>8.3f} {vals.std():>8.3f}")
    print()


def main():
    run_series("UNIFORM process (true excess should be ~1.0 regardless of N if unbiased)", make_uniform)
    run_series("BURSTY process, FIXED 50% clustering fraction across all N", make_bursty_fixed_fraction, burst_fraction=0.5, n_clusters=8)
    run_series("SINGLE-BURST-THEN-SILENCE process (the frozen-seed shape)", make_single_burst_then_silence)


if __name__ == "__main__":
    main()
