import sqlite3
import json
import time
import hashlib
from pathlib import Path
from typing import Dict, Optional

import yaml

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rng_seed INTEGER NOT NULL,
    started_at_tick INTEGER NOT NULL,
    started_wall_time TEXT NOT NULL,
    ended_at_tick INTEGER,
    config_yaml TEXT NOT NULL,
    config_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fossil_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES runs(id),
    tick INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    species_id INTEGER,
    genome_snapshot TEXT NOT NULL,
    population INTEGER NOT NULL,
    parent_species_id INTEGER,
    metadata TEXT
);

CREATE INDEX IF NOT EXISTS idx_fossil_species ON fossil_records(species_id);
CREATE INDEX IF NOT EXISTS idx_fossil_tick ON fossil_records(tick);
CREATE INDEX IF NOT EXISTS idx_fossil_run ON fossil_records(run_id);
"""


def open_db(db_path: str) -> sqlite3.Connection:
    """One long-lived connection for the life of the process. Every
    write below commits immediately (event frequency here is low --
    species emergences, extinctions, periodic snapshots -- so
    per-write commit costs nothing and guarantees nothing written is
    lost to a later crash)."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def start_run(conn: sqlite3.Connection, config: Dict, rng_seed: int) -> int:
    config_yaml = yaml.dump(config)
    config_hash = hashlib.sha256(config_yaml.encode()).hexdigest()
    cur = conn.execute(
        "INSERT INTO runs (rng_seed, started_at_tick, started_wall_time, config_yaml, config_hash) "
        "VALUES (?, ?, ?, ?, ?)",
        (rng_seed, 0, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), config_yaml, config_hash),
    )
    conn.commit()
    return cur.lastrowid


def end_run(conn: sqlite3.Connection, run_id: int, ended_at_tick: int) -> None:
    """Only ever called from a clean exit path. A SIGKILL'd process
    never reaches this, which is the point: ended_at_tick stays NULL
    for a run that never got to say it finished."""
    conn.execute("UPDATE runs SET ended_at_tick = ? WHERE id = ?", (ended_at_tick, run_id))
    conn.commit()


def write_fossil(conn: sqlite3.Connection, run_id: int, record) -> None:
    conn.execute(
        "INSERT INTO fossil_records "
        "(run_id, tick, event_type, species_id, genome_snapshot, population, parent_species_id, metadata) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            run_id,
            record.tick,
            record.event_type,
            record.species_id,
            json.dumps(record.genome_snapshot),
            record.population,
            record.parent_species_id,
            json.dumps(record.metadata),
        ),
    )
    conn.commit()
