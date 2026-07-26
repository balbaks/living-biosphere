#!/usr/bin/env python3
"""Section 1.2 validation harness -- runs the pre-registered arms
(NOTES.md, "Section 1.2 pre-registration"), computes S2 against a
permutation null per seed, applies the plateau adjudication, runs the
Arm A vs B cross-arm comparison, and generates the NOTES.md results
section programmatically from the raw output. No hand-transcription:
this script is the single source of truth for every number that ends
up in the record.
"""
import sys
import json
import time
import hashlib
import multiprocessing as mp
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import yaml
from scipy import stats as scipy_stats

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.world import World

TICKS = 40000
WINDOW_EPOCHS = 10
STEP_EPOCHS = 1
N_PERMS = 200
MIN_N = 150
RESCUE_BUFFER_EPOCHS = 20  # 200 ticks / 10
DB_PATH = "data/section_1_2_results.db"
CONFIG_PATH = Path(__file__).parent.parent / "config" / "world.yaml"
ARM_B_FIXED_RATE = 0.0053
ARM_B2_FIXED_RATE = 0.0020
SEEDS = list(range(1, 11))


def load_base_config() -> Dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def config_hash(config: Dict) -> str:
    return hashlib.sha256(yaml.dump(config).encode()).hexdigest()


def build_config(arm: str, seed: int) -> Dict:
    config = load_base_config()
    config["rng"] = {"seed": seed}
    config["world"]["db_path"] = DB_PATH
    if arm == "A":
        pass
    elif arm == "B":
        config.setdefault("genome", {})["fixed_mutation_rate"] = ARM_B_FIXED_RATE
    elif arm == "B2":
        config.setdefault("genome", {})["fixed_mutation_rate"] = ARM_B2_FIXED_RATE
    elif arm == "D":
        config["intervention"]["enabled"] = False
    else:
        raise ValueError(f"unknown arm {arm}")
    return config


def s2_fano(counts: np.ndarray, excluded_windows: Optional[set] = None) -> float:
    """Fano factor (variance/mean) of per-window event totals.
    Windows whose start index is in excluded_windows are skipped."""
    totals = []
    n = len(counts)
    for s in range(0, n - WINDOW_EPOCHS + 1, STEP_EPOCHS):
        if excluded_windows and s in excluded_windows:
            continue
        totals.append(counts[s:s + WINDOW_EPOCHS].sum())
    totals = np.array(totals)
    if len(totals) == 0 or totals.mean() == 0:
        return float("nan")
    return float(totals.var() / totals.mean())


def run_one(arm_seed) -> Dict:
    arm, seed = arm_seed
    config = build_config(arm, seed)
    the_config_hash = config_hash(config)

    world = World(config)
    for _ in range(TICKS):
        world.tick_step()
    world.shutdown()

    n_epochs = TICKS // 10
    turnover_ticks = [r.tick for r in world.fossil_record if r.event_type in ("species_emergence", "extinction")]
    rescue_ticks = [r.tick for r in world.fossil_record if r.event_type == "rescue"]
    rescue_count = world.rescue_count

    epoch_counts = np.zeros(n_epochs, dtype=int)
    for t in turnover_ticks:
        epoch_counts[min((t - 1) // 10, n_epochs - 1)] += 1

    # rescue-window exclusion backstop (no-op if rescue_count == 0, which
    # is expected given the ice_age/famine/heat_wave severity tuning, but
    # applied regardless per the pre-registration)
    excluded_epochs = set()
    for rt in rescue_ticks:
        re_ = min((rt - 1) // 10, n_epochs - 1)
        for e in range(max(0, re_ - RESCUE_BUFFER_EPOCHS), min(n_epochs, re_ + RESCUE_BUFFER_EPOCHS + 1)):
            excluded_epochs.add(e)
    excluded_windows = set()
    if excluded_epochs:
        for s in range(0, n_epochs - WINDOW_EPOCHS + 1, STEP_EPOCHS):
            if any((s + off) in excluded_epochs for off in range(WINDOW_EPOCHS)):
                excluded_windows.add(s)

    N = len(turnover_ticks)

    # plateau check: turnover count over the run's final third
    third_start_tick = TICKS * 2 // 3
    n_at_third_start = len([t for t in turnover_ticks if t <= third_start_tick])
    plateaued = (N == n_at_third_start)

    observed_s2 = s2_fano(epoch_counts, excluded_windows if excluded_windows else None)

    rng = np.random.default_rng((seed * 1000) + (hash(arm) % 997))
    null_s2s = np.array([s2_fano(rng.permutation(epoch_counts)) for _ in range(N_PERMS)])
    null_median = float(np.median(null_s2s))
    null_p95 = float(np.percentile(null_s2s, 95))
    standardized_excess = (observed_s2 / null_median) if null_median > 0 else float("inf")
    raw_pass = bool(observed_s2 > null_p95)

    # adjudication -- plateau overrides the raw statistical result,
    # applied as its own step and reported alongside the raw result,
    # not folded into it silently
    if plateaued:
        adjudicated = "non-pass (plateaued)"
    elif N < MIN_N:
        adjudicated = "inconclusive (climbing, N<150)"
    else:
        adjudicated = "pass" if raw_pass else "non-pass"

    n_species_final = len(world.species_map)

    return {
        "arm": arm,
        "seed": seed,
        "run_id": world.run_id,
        "config_hash": the_config_hash,
        "N": N,
        "n_at_third_start": n_at_third_start,
        "plateaued": plateaued,
        "observed_s2": observed_s2,
        "null_median_s2": null_median,
        "null_p95_s2": null_p95,
        "standardized_excess": standardized_excess,
        "raw_pass": raw_pass,
        "adjudicated": adjudicated,
        "rescue_count": rescue_count,
        "n_species_final": n_species_final,
        "last_turnover_tick": max(turnover_ticks) if turnover_ticks else None,
    }


def mann_whitney_a_vs_b(a_results: List[Dict], b_results: List[Dict]) -> Dict:
    a_vals = np.array([r["standardized_excess"] for r in a_results])
    b_vals = np.array([r["standardized_excess"] for r in b_results])
    u_stat, p_value = scipy_stats.mannwhitneyu(a_vals, b_vals, alternative="greater")
    n1, n2 = len(a_vals), len(b_vals)
    # rank_biserial = (2U)/(n1*n2) - 1, where U is scipy's U-for-a_vals
    # under alternative='greater' (counts pairs where a_i > b_j). +1 means
    # a always exceeds b; -1 means the reverse. (Not 1 - 2U/n1n2 -- that
    # sign convention was verified backwards against a known-separated
    # test case before this fix landed.)
    rank_biserial = (2 * u_stat) / (n1 * n2) - 1
    return {
        "u_statistic": float(u_stat),
        "p_value": float(p_value),
        "rank_biserial_r": float(rank_biserial),
        "n1": n1,
        "n2": n2,
        "significant_at_0.05": bool(p_value < 0.05),
        "effect_floor_met_r>=0.3": bool(abs(rank_biserial) >= 0.3),
    }


def generate_notes_section(all_results: Dict[str, List[Dict]], mw_result: Dict, meta: Dict) -> str:
    """Builds the NOTES.md results markdown directly from computed data.
    No manual transcription -- every number here is an f-string reference
    into the actual result dicts."""
    lines = []
    lines.append("# Section 1.2 results")
    lines.append("")
    lines.append(f"Run at {meta['run_timestamp']}. Config hash: `{meta['config_hash']}`. "
                  f"{meta['n_runs']} runs, {meta['ticks']} ticks each, "
                  f"{meta['wall_clock_minutes']:.1f} minutes wall-clock.")
    lines.append("")

    for arm in ["A", "B", "D"]:
        results = all_results[arm]
        lines.append(f"## Arm {arm}")
        lines.append("")
        lines.append("| seed | N | raw S2 | null p95 | std. excess | plateaued | raw pass | adjudicated | rescues |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for r in sorted(results, key=lambda x: x["seed"]):
            lines.append(
                f"| {r['seed']} | {r['N']} | {r['observed_s2']:.4f} | {r['null_p95_s2']:.4f} | "
                f"{r['standardized_excess']:.3f} | {r['plateaued']} | {r['raw_pass']} | "
                f"{r['adjudicated']} | {r['rescue_count']} |"
            )
        n_pass = sum(1 for r in results if r["adjudicated"] == "pass")
        n_conclusive = sum(1 for r in results if r["adjudicated"] != "inconclusive (climbing, N<150)")
        n_raw_pass = sum(1 for r in results if r["raw_pass"])
        n_plateaued = sum(1 for r in results if r["plateaued"])
        lines.append("")
        lines.append(f"Adjudicated: {n_pass}/10 pass ({n_conclusive}/10 conclusive). "
                      f"Raw statistical pass (pre-adjudication): {n_raw_pass}/10. "
                      f"Plateaued: {n_plateaued}/10.")
        if n_raw_pass != n_pass:
            lines.append(
                f"**Raw and adjudicated results differ** ({n_raw_pass}/10 raw vs {n_pass}/10 adjudicated) "
                f"-- {n_plateaued} seed(s) passed the statistical test while plateaued, "
                f"which the pre-registration treats as a non-pass regardless of the raw S2 result."
            )
        lines.append("")

    lines.append("## Arm A vs Arm B (primary comparative gate)")
    lines.append("")
    lines.append(f"Mann-Whitney U on standardized excess, one-sided (A > B): "
                  f"U={mw_result['u_statistic']:.1f}, p={mw_result['p_value']:.4f}, "
                  f"rank-biserial r={mw_result['rank_biserial_r']:.3f}.")
    lines.append(f"Significant at alpha=0.05: {mw_result['significant_at_0.05']}. "
                  f"Effect-size floor (|r|>=0.3) met: {mw_result['effect_floor_met_r>=0.3']}.")
    lines.append(f"Gate passes only if both are true: "
                  f"{mw_result['significant_at_0.05'] and mw_result['effect_floor_met_r>=0.3']}.")
    lines.append("")

    d_results = all_results["D"]
    n_d_pass = sum(1 for r in d_results if r["adjudicated"] == "pass")
    lines.append("## Combined Section 1.2 pass criterion")
    lines.append("")
    a_pass = sum(1 for r in all_results["A"] if r["adjudicated"] == "pass")
    lines.append(f"1. Arm A >=7/10: {a_pass}/10 -> {'PASS' if a_pass >= 7 else 'FAIL'}")
    lines.append(f"2. Arm D >=7/10: {n_d_pass}/10 -> {'PASS' if n_d_pass >= 7 else 'FAIL'}")
    ab_gate = mw_result['significant_at_0.05'] and mw_result['effect_floor_met_r>=0.3']
    lines.append(f"3. Arm A vs B Mann-Whitney gate: {'PASS' if ab_gate else 'FAIL'}")
    overall = (a_pass >= 7) and (n_d_pass >= 7) and ab_gate
    lines.append("")
    lines.append(f"**Section 1.2 overall: {'PASS' if overall else 'FAIL'}**")
    lines.append("")
    lines.append(
        "Per the pre-registration: this criterion is not adjusted after seeing these numbers. "
        "A FAIL here is a legitimate, informative result about the mutation-rate floor and/or "
        "shock frequency at the current config, not a defect in the harness."
    )

    return "\n".join(lines)


def main():
    tasks = [(arm, seed) for arm in ["A", "B", "D"] for seed in SEEDS]
    print(f"Running {len(tasks)} simulations ({TICKS} ticks each) at 2-way parallelism...", flush=True)
    t0 = time.time()
    with mp.Pool(processes=2) as pool:
        raw_results = pool.map(run_one, tasks)
    elapsed_min = (time.time() - t0) / 60.0
    print(f"Done in {elapsed_min:.1f} minutes.", flush=True)

    all_results: Dict[str, List[Dict]] = {"A": [], "B": [], "D": []}
    for r in raw_results:
        all_results[r["arm"]].append(r)

    mw_result = mann_whitney_a_vs_b(all_results["A"], all_results["B"])

    base_config = load_base_config()
    meta = {
        "run_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "config_hash": config_hash({**base_config, "world": {**base_config["world"], "db_path": DB_PATH}}),
        "n_runs": len(tasks),
        "ticks": TICKS,
        "wall_clock_minutes": elapsed_min,
    }

    out_dir = Path(__file__).parent.parent / "data"
    out_dir.mkdir(exist_ok=True)
    with open(out_dir / "section_1_2_raw_results.json", "w") as f:
        json.dump({"results": raw_results, "mann_whitney_a_vs_b": mw_result, "meta": meta}, f, indent=2)

    notes_section = generate_notes_section(all_results, mw_result, meta)
    with open(out_dir / "section_1_2_notes_section.md", "w") as f:
        f.write(notes_section)

    print(notes_section)


if __name__ == "__main__":
    main()
