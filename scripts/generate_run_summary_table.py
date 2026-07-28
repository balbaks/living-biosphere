#!/usr/bin/env python3
"""Generates a per-run summary table (CSV) directly from
data/section_1_corrected_results.db -- one row per run, every input to
every statistic reported in the corrected Section 1 survival re-run.

This is the artifact that gets committed to git in place of the raw
database (too large for GitHub -- see NOTES.md, "Persistence decision:
raw DBs are not git-tracked"). Generated programmatically, no
hand-assembly, same rule as every NOTES.md results section this
session.
"""
import csv
import sqlite3
import sys
from pathlib import Path

import numpy as np
import yaml

DB_PATH = Path(__file__).parent.parent / "data" / "section_1_corrected_results.db"
OUT_PATH = Path(__file__).parent.parent / "data" / "section_1_corrected_run_summary.csv"
TICKS = 40000
WINDOW = 10
STEP = 1


def identify_arm(config: dict) -> str:
    genome_cfg = config.get("genome", {})
    if "fixed_mutation_rate" in genome_cfg:
        return f"fixed_{genome_cfg['fixed_mutation_rate']}"
    floor = genome_cfg.get("mutation_rate_floor", 0.002)
    return f"evolving_floor_{floor}"


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    runs = conn.execute("SELECT id, rng_seed, config_hash, config_yaml FROM runs ORDER BY id").fetchall()

    per_run = {}
    for run in runs:
        config = yaml.safe_load(run["config_yaml"])
        arm = identify_arm(config)

        events = conn.execute(
            "SELECT tick, event_type, species_id FROM fossil_records WHERE run_id=? "
            "AND event_type IN ('species_emergence','extinction') ORDER BY tick",
            (run["id"],),
        ).fetchall()
        emergence_ids = {e["species_id"] for e in events if e["event_type"] == "species_emergence"}
        extinction_ids = {e["species_id"] for e in events if e["event_type"] == "extinction"}
        n_emergence = len(emergence_ids)
        n_extinction = len(extinction_ids)
        species_alive_at_end = len(emergence_ids - extinction_ids)  # exact, from the event log itself

        turnover_ticks = sorted(e["tick"] for e in events)
        total_turnover = len(turnover_ticks)
        last_event_tick = turnover_ticks[-1] if turnover_ticks else None
        gaps = np.diff(turnover_ticks).tolist() if len(turnover_ticks) >= 2 else []

        third_start = TICKS * 2 // 3
        n_at_third = len([t for t in turnover_ticks if t <= third_start])
        crude_plateaued = (total_turnover == n_at_third)

        rescue_count = conn.execute(
            "SELECT COUNT(*) FROM fossil_records WHERE run_id=? AND event_type='rescue'", (run["id"],)
        ).fetchone()[0]

        per_run[run["id"]] = {
            "run_id": run["id"], "config_hash": run["config_hash"], "seed": run["rng_seed"], "arm": arm,
            "extinction_count": n_extinction, "emergence_count": n_emergence,
            "species_alive_at_end": species_alive_at_end, "total_turnover": total_turnover,
            "last_event_tick": last_event_tick, "gaps": gaps, "crude_plateaued": crude_plateaued,
            "rescue_count": rescue_count,
        }

    # per-arm freeze threshold, same methodology as the harness's Phase 1
    by_arm = {}
    for r in per_run.values():
        by_arm.setdefault(r["arm"], []).append(r)

    per_arm_threshold = {}
    for arm, rows in by_arm.items():
        healthy_gaps = []
        for r in rows:
            if not r["crude_plateaued"]:
                healthy_gaps.extend(r["gaps"])
        g = np.array(healthy_gaps) if healthy_gaps else np.array([0.0])
        threshold = float(np.percentile(g, 99.9)) if len(g) >= 10 else float(g.max() if len(g) else 0.0)
        per_arm_threshold[arm] = threshold

    for r in per_run.values():
        arm_thresh = per_arm_threshold[r["arm"]]
        if r["last_event_tick"] is None:
            r["freeze_classification"] = "no_turnover"
        else:
            trailing = TICKS - r["last_event_tick"]
            r["freeze_classification"] = "observed_freeze" if trailing > arm_thresh else "censored_active"

    fieldnames = ["run_id", "config_hash", "seed", "arm", "extinction_count", "emergence_count",
                  "species_alive_at_end", "total_turnover", "last_event_tick", "freeze_classification",
                  "rescue_count"]
    with open(OUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in sorted(per_run.values(), key=lambda x: x["run_id"]):
            writer.writerow({k: r[k] for k in fieldnames})

    print(f"Wrote {len(per_run)} rows to {OUT_PATH}")


if __name__ == "__main__":
    main()
