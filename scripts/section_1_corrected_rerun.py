#!/usr/bin/env python3
"""Corrected re-run of the Section 1 (revised) survival test plus its
fixed_0.1/0.2 extension, after fixing the species_emergence
fossilization bug (see NOTES.md, "Measurement bug found and fixed").

Same pre-registered design as before -- arms, seeds, run length,
primary/secondary statistics, per-arm freeze-threshold methodology,
and pass criteria are all unchanged. Only the measurement of N
changes, from silently-extinction-only to the true emergence+
extinction total. Runs all 10 arms (3 evolving-floor + 7 fixed-rate
levels including the 0.1/0.2 extension) together in one pass so the
phase-1-then-phase-2 discipline applies uniformly, rather than
reconciling two separate reports.

Fresh database (section_1_corrected_results.db), not appended to the
superseded one, so old (buggy) and new (corrected) runs are never
ambiguous about which is which.
"""
import sys
import json
import time
import statistics
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
DB_PATH = "data/section_1_corrected_results.db"
CONFIG_PATH = Path(__file__).parent.parent / "config" / "world.yaml"
SEEDS = list(range(1, 11))

FLOOR_ARMS = {
    "evolving_floor_0.001": 0.001,
    "evolving_floor_0.002": 0.002,
    "evolving_floor_0.004": 0.004,
}
FIXED_ARMS = {
    "fixed_0.001": 0.001,
    "fixed_0.002": 0.002,
    "fixed_0.005": 0.005,
    "fixed_0.02": 0.02,
    "fixed_0.05": 0.05,
    "fixed_0.1": 0.1,
    "fixed_0.2": 0.2,
}
ALL_ARMS = list(FLOOR_ARMS.keys()) + list(FIXED_ARMS.keys())
PRIMARY_EVOLVING_ARM = "evolving_floor_0.002"
PRIMARY_COMPARATOR_ARM = "fixed_0.002"


def load_base_config() -> Dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def config_hash(config: Dict) -> str:
    import hashlib
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

    emergences = [r.tick for r in world.fossil_record if r.event_type == "species_emergence"]
    extinctions = [r.tick for r in world.fossil_record if r.event_type == "extinction"]
    turnover_ticks = sorted(emergences + extinctions)
    N = len(turnover_ticks)
    n_emergences = len(emergences)
    n_extinctions = len(extinctions)
    last_tick = turnover_ticks[-1] if turnover_ticks else None
    gaps = np.diff(turnover_ticks).tolist() if len(turnover_ticks) >= 2 else []

    third_start = TICKS * 2 // 3
    n_at_third = len([t for t in turnover_ticks if t <= third_start])
    crude_plateaued = (N == n_at_third)

    return {
        "arm": arm, "seed": seed, "run_id": world.run_id, "config_hash": the_hash,
        "N": N, "n_emergences": n_emergences, "n_extinctions": n_extinctions,
        "last_turnover_tick": last_tick, "gaps": gaps, "crude_plateaued": crude_plateaued,
        "rescue_count": world.rescue_count, "n_species_final": len(world.species_map),
    }


def phase1_derive_thresholds(results: List[Dict]) -> Dict:
    by_arm = {arm: [] for arm in ALL_ARMS}
    for r in results:
        by_arm[r["arm"]].append(r)
    per_arm_threshold, per_arm_gap_stats = {}, {}
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
            "mean": float(g.mean()), "median": float(np.median(g)),
            "p95": float(np.percentile(g, 95)) if len(g) >= 20 else None,
            "p99.9": threshold, "max": float(g.max()),
        }
        all_healthy_gaps.extend(healthy_gaps)
    universal_gaps = np.array(all_healthy_gaps) if all_healthy_gaps else np.array([0.0])
    universal_threshold = float(np.percentile(universal_gaps, 99.9))
    return {"per_arm_threshold": per_arm_threshold, "per_arm_gap_stats": per_arm_gap_stats,
            "universal_threshold": universal_threshold, "universal_n_gaps": len(all_healthy_gaps)}


def phase1_flip_check(results: List[Dict], thresholds: Dict) -> List[Dict]:
    flips = []
    for r in results:
        if r["last_turnover_tick"] is None:
            continue
        trailing = TICKS - r["last_turnover_tick"]
        arm_thresh = thresholds["per_arm_threshold"][r["arm"]]
        univ_thresh = thresholds["universal_threshold"]
        freeze_per_arm = trailing > arm_thresh
        freeze_universal = trailing > univ_thresh
        flips.append({"arm": r["arm"], "seed": r["seed"], "trailing_silence": trailing,
                      "arm_threshold": arm_thresh, "universal_threshold": univ_thresh,
                      "freeze_per_arm": freeze_per_arm, "freeze_universal": freeze_universal,
                      "flipped": freeze_per_arm != freeze_universal})
    return flips


def print_phase1_report(thresholds, flips):
    print("=" * 70)
    print("PHASE 1: FREEZE-THRESHOLD DERIVATION (before touching N)")
    print("=" * 70)
    print(f"Universal threshold: {thresholds['universal_threshold']:.1f} ticks (from {thresholds['universal_n_gaps']} pooled gaps)")
    for arm in ALL_ARMS:
        s = thresholds["per_arm_gap_stats"][arm]
        print(f"  {arm:<22} n_healthy={s['n_healthy_seeds']:>2} n_gaps={s['n_gaps']:>6} "
              f"mean={s['mean']:>8.1f} median={s['median']:>7.1f} threshold={s['p99.9']:.1f}")
    n_flipped = sum(1 for f in flips if f["flipped"])
    print(f"\nFlip count: {n_flipped} of {len(flips)}")
    for f in flips:
        if f["flipped"]:
            print(f"  FLIPPED: {f['arm']} seed={f['seed']} trailing={f['trailing_silence']}")
    print()


def print_phase2_report(results) -> Dict:
    print("=" * 70)
    print("PHASE 2: PRIMARY STATISTIC -- total turnover count (N), CORRECTED")
    print("=" * 70)
    by_arm = {arm: [] for arm in ALL_ARMS}
    for r in results:
        by_arm[r["arm"]].append(r)
    for arm in ALL_ARMS:
        ns = sorted(r["N"] for r in by_arm[arm])
        n_emerg = sorted(r["n_emergences"] for r in by_arm[arm])
        n_ext = sorted(r["n_extinctions"] for r in by_arm[arm])
        print(f"  {arm:<22} N={ns}")
        print(f"  {'':<22} median={statistics.median(ns):.1f} mean={statistics.mean(ns):.1f}  "
              f"(emergences median={statistics.median(n_emerg)}, extinctions median={statistics.median(n_ext)})")
    print()
    evolving_n = [r["N"] for r in by_arm[PRIMARY_EVOLVING_ARM]]
    pairwise = {}
    for arm in FIXED_ARMS:
        fixed_n = [r["N"] for r in by_arm[arm]]
        u, p = scipy_stats.mannwhitneyu(evolving_n, fixed_n, alternative="greater")
        n1, n2 = len(evolving_n), len(fixed_n)
        r_eff = (2 * u) / (n1 * n2) - 1
        pairwise[arm] = {"U": float(u), "p": float(p), "r": float(r_eff)}
        flag = " <-- PRE-SPECIFIED PRIMARY COMPARATOR" if arm == PRIMARY_COMPARATOR_ARM else ""
        print(f"  evolving(0.002) vs {arm:<14}: U={u:.1f} p={p:.5f} r={r_eff:.3f}{flag}")
    five_level_keys = ["fixed_0.001", "fixed_0.002", "fixed_0.005", "fixed_0.02", "fixed_0.05"]
    all_five_significant = all(pairwise[a]["p"] < 0.05 for a in five_level_keys)
    print(f"\nIntersection-union (evolving beats all FIVE original levels): {'HOLDS' if all_five_significant else 'FAILS'}")
    primary_p = pairwise[PRIMARY_COMPARATOR_ARM]["p"]
    print(f"Pre-specified primary contrast (evolving vs {PRIMARY_COMPARATOR_ARM}): "
          f"{'wins, p=' + format(primary_p, '.5f') if primary_p < 0.05 else 'FAILS, p=' + format(primary_p, '.5f')}")
    medians = {arm: statistics.median(by_arm[arm][i]["N"] if False else [r["N"] for r in by_arm[arm]]) for arm in ALL_ARMS}
    print(f"\nMedian N across the ceiling: fixed_0.05={medians['fixed_0.05']:.1f} -> "
          f"fixed_0.1={medians['fixed_0.1']:.1f} -> fixed_0.2={medians['fixed_0.2']:.1f}")
    print()
    return {"pairwise": pairwise, "intersection_union_holds": all_five_significant, "medians": medians}


def build_survival_frame(results, thresholds) -> pd.DataFrame:
    rows = []
    for r in results:
        arm_thresh = thresholds["per_arm_threshold"][r["arm"]]
        effective_censor_time = TICKS - arm_thresh
        last_tick = r["last_turnover_tick"] if r["last_turnover_tick"] is not None else 0
        if last_tick <= effective_censor_time:
            duration, event_observed = last_tick, 1
        else:
            duration, event_observed = effective_censor_time, 0
        rows.append({"arm": r["arm"], "seed": r["seed"], "duration": duration, "event_observed": event_observed})
    return pd.DataFrame(rows)


def print_phase3_report(surv_df) -> Dict:
    print("=" * 70)
    print("PHASE 3: SECONDARY STATISTIC -- survival analysis (corroborating)")
    print("=" * 70)
    for arm in ALL_ARMS:
        sub = surv_df[surv_df["arm"] == arm]
        kmf = KaplanMeierFitter()
        kmf.fit(sub["duration"], sub["event_observed"])
        n_events = int(sub["event_observed"].sum())
        print(f"  {arm:<22} n_observed_freezes={n_events}/{len(sub)} median_survival={kmf.median_survival_time_}")
    evolving_sub = surv_df[surv_df["arm"] == PRIMARY_EVOLVING_ARM]
    comparator_sub = surv_df[surv_df["arm"] == PRIMARY_COMPARATOR_ARM]
    lr = logrank_test(evolving_sub["duration"], comparator_sub["duration"],
                       evolving_sub["event_observed"], comparator_sub["event_observed"])
    print(f"\nLog-rank, evolving(0.002) vs {PRIMARY_COMPARATOR_ARM}: p={lr.p_value:.5f}")
    all_sub = surv_df[surv_df["arm"].isin(ALL_ARMS)]
    mlr = multivariate_logrank_test(all_sub["duration"], all_sub["arm"], all_sub["event_observed"])
    print(f"Multivariate log-rank, all 10 arms: p={mlr.p_value:.5f}")
    print()
    return {"logrank_evolving_vs_primary_comparator_p": float(lr.p_value), "multivariate_logrank_p": float(mlr.p_value)}


def check_prediction_against_old_data(results):
    """Compares this corrected run's direct N against the implied true N
    computed from the old buggy databases (2*extinctions + alive_at_end),
    per the falsifiable prediction stated in NOTES.md before this ran."""
    print("=" * 70)
    print("PREDICTION CHECK: does corrected N match the pre-stated implied-true-N estimate?")
    print("=" * 70)
    old_paths = [Path(__file__).parent.parent / "data" / "section_1_survival_raw_results.json",
                 Path(__file__).parent.parent / "data" / "section_1_extension_raw_results.json"]
    old_results = []
    for p in old_paths:
        if p.exists():
            with open(p) as f:
                old_results.extend(json.load(f)["results"])
    old_by_arm = {}
    for r in old_results:
        old_by_arm.setdefault(r["arm"], []).append(r)

    new_by_arm = {}
    for r in results:
        new_by_arm.setdefault(r["arm"], []).append(r)

    for arm in ALL_ARMS:
        if arm not in old_by_arm:
            continue
        old_implied = [2 * r["N"] + r["n_species_final"] for r in old_by_arm[arm]]
        new_direct = [r["N"] for r in new_by_arm[arm]]
        med_old_implied = statistics.median(old_implied)
        med_new_direct = statistics.median(new_direct)
        match = "MATCH" if abs(med_old_implied - med_new_direct) / max(med_old_implied, 1) < 0.05 else "MISMATCH"
        print(f"  {arm:<22} old_implied_median={med_old_implied:.1f} new_direct_median={med_new_direct:.1f} [{match}]")
    print()


def main():
    tasks = [(arm, seed) for arm in ALL_ARMS for seed in SEEDS]
    print(f"Running {len(tasks)} CORRECTED simulations ({TICKS} ticks each) at 2-way parallelism...", flush=True)
    t0 = time.time()
    with mp.Pool(processes=2) as pool:
        results = pool.map(run_one, tasks)
    elapsed_min = (time.time() - t0) / 60.0
    print(f"Done in {elapsed_min:.1f} minutes.\n", flush=True)

    check_prediction_against_old_data(results)

    thresholds = phase1_derive_thresholds(results)
    flips = phase1_flip_check(results, thresholds)
    print_phase1_report(thresholds, flips)

    phase2_summary = print_phase2_report(results)

    surv_df = build_survival_frame(results, thresholds)
    phase3_summary = print_phase3_report(surv_df)

    out_dir = Path(__file__).parent.parent / "data"
    with open(out_dir / "section_1_corrected_raw_results.json", "w") as f:
        json.dump({
            "results": results, "thresholds": thresholds, "flips": flips,
            "phase2_summary": phase2_summary, "phase3_summary": phase3_summary,
            "meta": {"ticks": TICKS, "n_runs": len(tasks), "wall_clock_minutes": elapsed_min,
                     "run_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
        }, f, indent=2)
    print("Raw results written to data/section_1_corrected_raw_results.json")


if __name__ == "__main__":
    main()
