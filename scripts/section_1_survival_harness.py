#!/usr/bin/env python3
"""Section 1 (revised) pre-registration harness -- persistence/survival
test. See NOTES.md, "Section 1 (revised) pre-registration" for the full
design and reasoning.

Deliberately phase-separated, matching an explicit instruction: freeze-
threshold derivation (Phase 1) is computed and reported in isolation,
BEFORE the primary turnover-count statistic is touched (Phase 2), so
threshold choices can't be steered by having already seen which arm
"wins." Phase 3 (secondary survival analysis) runs last, using Phase
1's thresholds.
"""
import sys
import json
import time
import hashlib
import multiprocessing as mp
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import yaml
from scipy import stats as scipy_stats
from lifelines import KaplanMeierFitter
from lifelines.statistics import logrank_test, multivariate_logrank_test

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.world import World

TICKS = 40000
DB_PATH = "data/section_1_survival_results.db"
CONFIG_PATH = Path(__file__).parent.parent / "config" / "world.yaml"
SEEDS = list(range(1, 11))

# 8 arms: 3 evolving (floor sweep) + 5 fixed-rate levels
FLOOR_ARMS = {
    "evolving_floor_0.001": 0.001,
    "evolving_floor_0.002": 0.002,  # the "main" evolving arm
    "evolving_floor_0.004": 0.004,
}
FIXED_ARMS = {
    "fixed_0.001": 0.001,
    "fixed_0.002": 0.002,
    "fixed_0.005": 0.005,
    "fixed_0.02": 0.02,
    "fixed_0.05": 0.05,
}
ALL_ARMS = list(FLOOR_ARMS.keys()) + list(FIXED_ARMS.keys())

PRIMARY_EVOLVING_ARM = "evolving_floor_0.002"
PRIMARY_COMPARATOR_ARM = "fixed_0.002"  # pre-specified, per item 5


def load_base_config() -> Dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def config_hash(config: Dict) -> str:
    return hashlib.sha256(yaml.dump(config).encode()).hexdigest()


def build_config(arm: str, seed: int) -> Dict:
    config = load_base_config()
    config["rng"] = {"seed": seed}
    config["world"]["db_path"] = DB_PATH
    if arm in FLOOR_ARMS:
        config.setdefault("genome", {})["mutation_rate_floor"] = FLOOR_ARMS[arm]
    elif arm in FIXED_ARMS:
        config.setdefault("genome", {})["fixed_mutation_rate"] = FIXED_ARMS[arm]
    else:
        raise ValueError(f"unknown arm {arm}")
    return config


def run_one(arm_seed) -> Dict:
    arm, seed = arm_seed
    config = build_config(arm, seed)
    the_hash = config_hash(config)

    world = World(config)
    for _ in range(TICKS):
        world.tick_step()
    world.shutdown()

    turnover_ticks = sorted(r.tick for r in world.fossil_record if r.event_type in ("species_emergence", "extinction"))
    N = len(turnover_ticks)
    last_tick = turnover_ticks[-1] if turnover_ticks else None
    gaps = np.diff(turnover_ticks).tolist() if len(turnover_ticks) >= 2 else []

    # crude filter only -- used to pool "probably healthy" gaps for Phase 1's
    # threshold derivation, NOT the final freeze classification
    third_start = TICKS * 2 // 3
    n_at_third = len([t for t in turnover_ticks if t <= third_start])
    crude_plateaued = (N == n_at_third)

    return {
        "arm": arm,
        "seed": seed,
        "run_id": world.run_id,
        "config_hash": the_hash,
        "N": N,
        "last_turnover_tick": last_tick,
        "gaps": gaps,
        "crude_plateaued": crude_plateaued,
        "rescue_count": world.rescue_count,
        "n_species_final": len(world.species_map),
    }


# ---------------------------------------------------------------------------
# PHASE 1: freeze-threshold derivation, in isolation
# ---------------------------------------------------------------------------

def phase1_derive_thresholds(results: List[Dict]) -> Dict:
    """Per-arm p99.9 healthy-gap threshold, derived ONLY from gaps, plus
    a naive pooled-universal threshold for comparison. Does not look at
    N (turnover count) at all."""
    by_arm = {arm: [] for arm in ALL_ARMS}
    for r in results:
        by_arm[r["arm"]].append(r)

    per_arm_threshold = {}
    per_arm_gap_stats = {}
    all_healthy_gaps = []
    for arm in ALL_ARMS:
        healthy_gaps = []
        for r in by_arm[arm]:
            if not r["crude_plateaued"]:
                healthy_gaps.extend(r["gaps"])
        g = np.array(healthy_gaps) if healthy_gaps else np.array([0.0])
        threshold = float(np.percentile(g, 99.9)) if len(g) >= 10 else float(g.max() if len(g) else 0.0)
        per_arm_threshold[arm] = threshold
        per_arm_gap_stats[arm] = {
            "n_gaps": len(healthy_gaps),
            "n_healthy_seeds": sum(1 for r in by_arm[arm] if not r["crude_plateaued"]),
            "mean": float(g.mean()),
            "median": float(np.median(g)),
            "p95": float(np.percentile(g, 95)) if len(g) >= 20 else None,
            "p99.9": threshold,
            "max": float(g.max()),
        }
        all_healthy_gaps.extend(healthy_gaps)

    universal_gaps = np.array(all_healthy_gaps) if all_healthy_gaps else np.array([0.0])
    universal_threshold = float(np.percentile(universal_gaps, 99.9))

    return {
        "per_arm_threshold": per_arm_threshold,
        "per_arm_gap_stats": per_arm_gap_stats,
        "universal_threshold": universal_threshold,
        "universal_n_gaps": len(all_healthy_gaps),
    }


def phase1_flip_check(results: List[Dict], thresholds: Dict) -> List[Dict]:
    """For every seed, classify freeze status under the per-arm threshold
    vs the naive universal one, and report where they disagree."""
    flips = []
    for r in results:
        if r["last_turnover_tick"] is None:
            continue
        trailing = TICKS - r["last_turnover_tick"]
        arm_thresh = thresholds["per_arm_threshold"][r["arm"]]
        univ_thresh = thresholds["universal_threshold"]
        freeze_per_arm = trailing > arm_thresh
        freeze_universal = trailing > univ_thresh
        flips.append({
            "arm": r["arm"], "seed": r["seed"], "trailing_silence": trailing,
            "arm_threshold": arm_thresh, "universal_threshold": univ_thresh,
            "freeze_per_arm": freeze_per_arm, "freeze_universal": freeze_universal,
            "flipped": freeze_per_arm != freeze_universal,
        })
    return flips


def print_phase1_report(thresholds: Dict, flips: List[Dict]):
    print("=" * 70)
    print("PHASE 1: FREEZE-THRESHOLD DERIVATION (computed before touching N)")
    print("=" * 70)
    print(f"Universal (naive pooled) threshold: {thresholds['universal_threshold']:.1f} ticks "
          f"(from {thresholds['universal_n_gaps']} pooled gaps)")
    print()
    for arm in ALL_ARMS:
        s = thresholds["per_arm_gap_stats"][arm]
        print(f"  {arm:<22} n_healthy_seeds={s['n_healthy_seeds']:>2} n_gaps={s['n_gaps']:>5} "
              f"mean={s['mean']:>8.1f} median={s['median']:>7.1f} p95={s['p95']} "
              f"threshold(p99.9)={s['p99.9']:.1f}")
    print()
    n_flipped = sum(1 for f in flips if f["flipped"])
    print(f"Flip count (per-arm vs universal classification): {n_flipped} of {len(flips)} seeds")
    for f in flips:
        if f["flipped"]:
            print(f"  FLIPPED: {f['arm']} seed={f['seed']} trailing={f['trailing_silence']} "
                  f"arm_thresh={f['arm_threshold']:.1f} universal_thresh={f['universal_threshold']:.1f}")
    print()


# ---------------------------------------------------------------------------
# PHASE 2: primary statistic -- total turnover count
# ---------------------------------------------------------------------------

def print_phase2_report(results: List[Dict]) -> Dict:
    print("=" * 70)
    print("PHASE 2: PRIMARY STATISTIC -- total turnover count (N) over 40,000 ticks")
    print("=" * 70)
    by_arm = {arm: [] for arm in ALL_ARMS}
    for r in results:
        by_arm[r["arm"]].append(r["N"])

    for arm in ALL_ARMS:
        ns = sorted(by_arm[arm])
        print(f"  {arm:<22} N={ns}")
        print(f"  {'':<22} median={np.median(ns):.1f} mean={np.mean(ns):.1f}")
    print()

    evolving_n = by_arm[PRIMARY_EVOLVING_ARM]
    pairwise = {}
    for arm in FIXED_ARMS:
        u, p = scipy_stats.mannwhitneyu(evolving_n, by_arm[arm], alternative="greater")
        n1, n2 = len(evolving_n), len(by_arm[arm])
        r_eff = (2 * u) / (n1 * n2) - 1
        pairwise[arm] = {"U": float(u), "p": float(p), "r": float(r_eff)}
        flag = " <-- PRE-SPECIFIED PRIMARY COMPARATOR" if arm == PRIMARY_COMPARATOR_ARM else ""
        print(f"  evolving(0.002) vs {arm:<14}: U={u:.1f} p={p:.5f} r={r_eff:.3f}{flag}")

    all_five_significant = all(pw["p"] < 0.05 for pw in pairwise.values())
    print()
    print(f"Intersection-union claim (evolving beats ALL five fixed levels, alpha=0.05 each): "
          f"{'HOLDS' if all_five_significant else 'FAILS'}")
    primary_p = pairwise[PRIMARY_COMPARATOR_ARM]["p"]
    print(f"Pre-specified primary contrast (evolving vs {PRIMARY_COMPARATOR_ARM}): "
          f"{'evolving wins, p=' + format(primary_p, '.5f') if primary_p < 0.05 else 'FAILS to show evolving ahead, p=' + format(primary_p, '.5f')}")
    print()
    return {"pairwise": pairwise, "intersection_union_holds": all_five_significant}


# ---------------------------------------------------------------------------
# PHASE 3: secondary -- survival analysis, using Phase 1's thresholds
# ---------------------------------------------------------------------------

def build_survival_frame(results: List[Dict], thresholds: Dict) -> pd.DataFrame:
    rows = []
    for r in results:
        arm_thresh = thresholds["per_arm_threshold"][r["arm"]]
        effective_censor_time = TICKS - arm_thresh
        last_tick = r["last_turnover_tick"] if r["last_turnover_tick"] is not None else 0
        if last_tick <= effective_censor_time:
            duration = last_tick
            event_observed = 1
        else:
            duration = effective_censor_time
            event_observed = 0
        rows.append({"arm": r["arm"], "seed": r["seed"], "duration": duration, "event_observed": event_observed})
    return pd.DataFrame(rows)


def print_phase3_report(surv_df: pd.DataFrame):
    print("=" * 70)
    print("PHASE 3: SECONDARY STATISTIC -- survival analysis (corroborating only)")
    print("=" * 70)
    for arm in ALL_ARMS:
        sub = surv_df[surv_df["arm"] == arm]
        kmf = KaplanMeierFitter()
        kmf.fit(sub["duration"], sub["event_observed"])
        median_surv = kmf.median_survival_time_
        n_events = int(sub["event_observed"].sum())
        print(f"  {arm:<22} n_observed_freezes={n_events}/{len(sub)} median_survival={median_surv}")
    print()

    evolving_sub = surv_df[surv_df["arm"] == PRIMARY_EVOLVING_ARM]
    comparator_sub = surv_df[surv_df["arm"] == PRIMARY_COMPARATOR_ARM]
    lr = logrank_test(evolving_sub["duration"], comparator_sub["duration"],
                       evolving_sub["event_observed"], comparator_sub["event_observed"])
    print(f"Log-rank, evolving(0.002) vs {PRIMARY_COMPARATOR_ARM}: p={lr.p_value:.5f}")

    all_sub = surv_df[surv_df["arm"].isin(ALL_ARMS)]
    mlr = multivariate_logrank_test(all_sub["duration"], all_sub["arm"], all_sub["event_observed"])
    print(f"Multivariate log-rank, all 8 arms: p={mlr.p_value:.5f}")
    print()
    return {"logrank_evolving_vs_primary_comparator_p": float(lr.p_value),
            "multivariate_logrank_p": float(mlr.p_value)}


def main():
    print(f"Power check (from pre-registration, restated before compute starts):")
    print(f"  Mann-Whitney on last round's raw N, Arm A vs Arm B: p=0.000106, r=0.990")
    print(f"  Bootstrap power at n=10/arm: 1.000. Proceeding.")
    print()

    tasks = [(arm, seed) for arm in ALL_ARMS for seed in SEEDS]
    print(f"Running {len(tasks)} simulations ({TICKS} ticks each) at 2-way parallelism...", flush=True)
    t0 = time.time()
    with mp.Pool(processes=2) as pool:
        results = pool.map(run_one, tasks)
    elapsed_min = (time.time() - t0) / 60.0
    print(f"Done in {elapsed_min:.1f} minutes.\n", flush=True)

    # Phase 1 first, in isolation, before any N is examined
    thresholds = phase1_derive_thresholds(results)
    flips = phase1_flip_check(results, thresholds)
    print_phase1_report(thresholds, flips)

    # Phase 2, only now
    phase2_summary = print_phase2_report(results)

    # Phase 3, using Phase 1's thresholds
    surv_df = build_survival_frame(results, thresholds)
    phase3_summary = print_phase3_report(surv_df)

    out_dir = Path(__file__).parent.parent / "data"
    out_dir.mkdir(exist_ok=True)
    with open(out_dir / "section_1_survival_raw_results.json", "w") as f:
        json.dump({
            "results": [{k: v for k, v in r.items()} for r in results],
            "thresholds": thresholds,
            "flips": flips,
            "phase2_summary": phase2_summary,
            "phase3_summary": phase3_summary,
            "meta": {"ticks": TICKS, "n_runs": len(tasks), "wall_clock_minutes": elapsed_min,
                     "run_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
        }, f, indent=2)

    print("Raw results written to data/section_1_survival_raw_results.json")


if __name__ == "__main__":
    main()
