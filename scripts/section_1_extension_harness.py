#!/usr/bin/env python3
"""Section 1 extension: brackets the fixed-rate sweep's unbracketed
maximum. fixed_0.05 won the main sweep (it was chosen as the top of
Arm A's observed range, not as a candidate turnover-maximizer), so this
tests fixed_0.1 and fixed_0.2 against the same primary statistic and
phase discipline. See NOTES.md, "Section 1 extension pre-registration."

Appends to the same database as the main survival run (same run_id
sequence, same schema) so all runs stay in one place.
"""
import sys
import json
import time
from pathlib import Path

import numpy as np
import multiprocessing as mp
from scipy import stats as scipy_stats

sys.path.insert(0, str(Path(__file__).parent))
from section_1_survival_harness import (
    build_config, run_one, config_hash, DB_PATH, TICKS, SEEDS,
    PRIMARY_EVOLVING_ARM,
)

EXTENSION_ARMS = {
    "fixed_0.1": 0.1,
    "fixed_0.2": 0.2,
}


def build_extension_config(arm: str, seed: int):
    from section_1_survival_harness import load_base_config
    config = load_base_config()
    config["rng"] = {"seed": seed}
    config["world"]["db_path"] = DB_PATH
    config.setdefault("genome", {})["fixed_mutation_rate"] = EXTENSION_ARMS[arm]
    return config


def run_one_extension(arm_seed):
    import section_1_survival_harness as h
    arm, seed = arm_seed
    config = build_extension_config(arm, seed)
    the_hash = config_hash(config)

    world = h.World(config)
    for _ in range(TICKS):
        world.tick_step()
    world.shutdown()

    turnover_ticks = sorted(r.tick for r in world.fossil_record if r.event_type in ("species_emergence", "extinction"))
    N = len(turnover_ticks)
    last_tick = turnover_ticks[-1] if turnover_ticks else None
    gaps = np.diff(turnover_ticks).tolist() if len(turnover_ticks) >= 2 else []

    third_start = TICKS * 2 // 3
    n_at_third = len([t for t in turnover_ticks if t <= third_start])
    crude_plateaued = (N == n_at_third)

    return {
        "arm": arm, "seed": seed, "run_id": world.run_id, "config_hash": the_hash,
        "N": N, "last_turnover_tick": last_tick, "gaps": gaps,
        "crude_plateaued": crude_plateaued, "rescue_count": world.rescue_count,
        "n_species_final": len(world.species_map),
    }


def main():
    tasks = [(arm, seed) for arm in EXTENSION_ARMS for seed in SEEDS]
    print(f"Running {len(tasks)} extension simulations ({TICKS} ticks each) at 2-way parallelism...", flush=True)
    t0 = time.time()
    with mp.Pool(processes=2) as pool:
        results = pool.map(run_one_extension, tasks)
    elapsed_min = (time.time() - t0) / 60.0
    print(f"Done in {elapsed_min:.1f} minutes.\n", flush=True)

    # Phase 1: per-arm thresholds for the two new arms, in isolation
    print("=" * 70)
    print("PHASE 1: freeze-threshold derivation for the extension arms")
    print("=" * 70)
    per_arm_threshold = {}
    for arm in EXTENSION_ARMS:
        healthy_gaps = []
        for r in results:
            if r["arm"] == arm and not r["crude_plateaued"]:
                healthy_gaps.extend(r["gaps"])
        g = np.array(healthy_gaps) if healthy_gaps else np.array([0.0])
        threshold = float(np.percentile(g, 99.9)) if len(g) >= 10 else float(g.max() if len(g) else 0.0)
        per_arm_threshold[arm] = threshold
        n_healthy = sum(1 for r in results if r["arm"] == arm and not r["crude_plateaued"])
        print(f"  {arm}: n_healthy_seeds={n_healthy} n_gaps={len(healthy_gaps)} "
              f"mean={g.mean():.1f} median={np.median(g):.1f} threshold(p99.9)={threshold:.1f}")
    print()

    # Phase 2: primary statistic, only now
    print("=" * 70)
    print("PHASE 2: primary statistic -- turnover count, extension arms")
    print("=" * 70)
    by_arm = {arm: sorted(r["N"] for r in results if r["arm"] == arm) for arm in EXTENSION_ARMS}
    for arm, ns in by_arm.items():
        print(f"  {arm}: N={ns} median={np.median(ns):.1f} mean={np.mean(ns):.1f}")
    print()

    # Compare against evolving_floor_0.002 and fixed_0.05 from the main run
    with open(Path(__file__).parent.parent / "data" / "section_1_survival_raw_results.json") as f:
        main_data = json.load(f)
    evolving_n = sorted(r["N"] for r in main_data["results"] if r["arm"] == PRIMARY_EVOLVING_ARM)
    fixed_05_n = sorted(r["N"] for r in main_data["results"] if r["arm"] == "fixed_0.05")
    print(f"  (for reference) evolving_floor_0.002: N={evolving_n} median={np.median(evolving_n):.1f}")
    print(f"  (for reference) fixed_0.05: N={fixed_05_n} median={np.median(fixed_05_n):.1f}")
    print()

    pairwise = {}
    for arm in list(EXTENSION_ARMS.keys()):
        u, p = scipy_stats.mannwhitneyu(evolving_n, by_arm[arm], alternative="greater")
        n1, n2 = len(evolving_n), len(by_arm[arm])
        r_eff = (2 * u) / (n1 * n2) - 1
        pairwise[arm] = {"U": float(u), "p": float(p), "r": float(r_eff)}
        print(f"  evolving(0.002) vs {arm}: U={u:.1f} p={p:.5f} r={r_eff:.3f}")

    # Also: is 0.05 -> 0.1 -> 0.2 monotonically increasing, or plateaued/declining?
    medians = {"fixed_0.05": float(np.median(fixed_05_n))}
    medians.update({arm: float(np.median(ns)) for arm, ns in by_arm.items()})
    print()
    print(f"  Median N across the extended ceiling: fixed_0.05={medians['fixed_0.05']:.1f} -> "
          f"fixed_0.1={medians['fixed_0.1']:.1f} -> fixed_0.2={medians['fixed_0.2']:.1f}")

    out_dir = Path(__file__).parent.parent / "data"
    with open(out_dir / "section_1_extension_raw_results.json", "w") as f:
        json.dump({
            "results": results, "per_arm_threshold": per_arm_threshold,
            "pairwise_vs_evolving": pairwise, "medians_across_ceiling": medians,
            "meta": {"ticks": TICKS, "n_runs": len(tasks), "wall_clock_minutes": elapsed_min,
                     "run_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
        }, f, indent=2)
    print("\nRaw results written to data/section_1_extension_raw_results.json")


if __name__ == "__main__":
    main()
