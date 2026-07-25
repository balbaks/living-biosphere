import numpy as np
import random
import time
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from src.creature import Creature
from src.genome import Genome, GENE_NAMES
from src import persistence

@dataclass
class ShockEvent:
    name: str
    announced_tick: int
    trigger_tick: int
    params: Dict
    triggered: bool = False

@dataclass
class ActiveShock:
    """A temperature-affecting shock currently in effect. Expires and
    reverts on its own schedule; multiple can overlap and stack
    multiplicatively while active."""
    name: str
    end_tick: int
    multiplier: float
    clump: bool = False
    refugia_fraction: float = 0.0
    refugia_bonus_mult: float = 1.0
    refugia_penalty_mult: float = 1.0

@dataclass
class FossilRecord:
    tick: int
    event_type: str
    species_id: Optional[int]
    genome_snapshot: Dict[str, float]
    population: int
    parent_species_id: Optional[int]
    metadata: Dict = field(default_factory=dict)

class World:
    def __init__(self, config: Dict):
        self.cfg = config
        self.tick = 0
        self.creatures: Dict[int, Creature] = {}
        self.next_creature_id = 1
        self.next_species_id = 1
        self.species_map: Dict[int, List[int]] = {}
        self.species_reps: Dict[int, Genome] = {}
        self.species_ages: Dict[int, int] = {}
        self.species_extinct: Dict[int, int] = {}
        self.species_parent: Dict[int, Optional[int]] = {}
        self.fossil_record: List[FossilRecord] = []
        self.shocks: List[ShockEvent] = []
        self.pending_shock: Optional[ShockEvent] = None
        self.events_log: List[Dict] = []
        self.rescue_count = 0

        self.rng_seed = config.get("rng", {}).get("seed")
        if self.rng_seed is None:
            self.rng_seed = random.randint(0, 2**32 - 1)
        random.seed(self.rng_seed)
        np.random.seed(self.rng_seed % (2**32 - 1))
        self.run_rng_seed = self.rng_seed

        w = config["world"]["width"]
        h = config["world"]["height"]
        self.resources = np.zeros((w, h), dtype=np.float32)
        self.temperature = np.ones((w, h), dtype=np.float32)
        self.base_regen = config["resources"]["base_regen_rate"]
        self.current_regen_mult = 1.0
        self.shock_end_tick = 0

        self.temp_baseline = 1.0
        self.active_temp_shocks: List[ActiveShock] = []
        icfg = config.get("intervention", {})
        self.temp_floor = icfg.get("temp_floor", 0.15)
        self.temp_ceiling = icfg.get("temp_ceiling", 2.5)

        db_path = config["world"].get("db_path")
        if db_path:
            self.db_conn = persistence.open_db(db_path)
            self.run_id = persistence.start_run(self.db_conn, config, self.rng_seed)
        else:
            self.db_conn = None
            self.run_id = None

        self._seed_resources()
        self._spawn_initial()
        self._update_species()

    def shutdown(self):
        """Call on clean exit only. A killed process never reaches
        this, which is the point: ended_at_tick distinguishes a run
        that finished from one that just stopped."""
        if self.db_conn is not None:
            persistence.end_run(self.db_conn, self.run_id, self.tick)
            self.db_conn.close()

    def _seed_resources(self):
        cfg = self.cfg["resources"]
        w, h = self.resources.shape
        self.resources[:] = self.base_regen * 30

        if cfg.get("regen_clusters", True):
            n_clusters = max(4, (w * h) // 300)
            for _ in range(n_clusters):
                cx, cy = random.randint(0, w-1), random.randint(0, h-1)
                sz = cfg.get("cluster_size", 5)
                for dx in range(-sz, sz+1):
                    for dy in range(-sz, sz+1):
                        if dx*dx + dy*dy <= sz*sz:
                            nx, ny = (cx+dx) % w, (cy+dy) % h
                            self.resources[nx, ny] += random.uniform(30, 80)

        self.resources = np.clip(self.resources, 0, cfg["max_cell_energy"])

    def _spawn_initial(self):
        n = self.cfg["creatures"]["initial_population"]
        w, h = self.resources.shape
        for _ in range(n):
            x, y = random.randint(0, w-1), random.randint(0, h-1)
            c = Creature(
                id=self.next_creature_id,
                x=x, y=y,
                genome=Genome(),
                energy=self.cfg["creatures"]["base_energy"],
                generation=0,
            )
            self.creatures[c.id] = c
            self.next_creature_id += 1

    def tick_step(self) -> Dict:
        self.tick += 1

        self._handle_shocks()
        self._update_temperature()
        self._regen_resources()
        self._creature_actions()
        self._remove_dead()

        if self.tick % 10 == 0:
            self._update_species()

        if self.tick % self.cfg["world"]["save_interval"] == 0:
            self._snapshot_fossils()

        max_pop = self.cfg["creatures"]["max_population"]
        if len(self.creatures) > int(max_pop * 1.2):
            to_cull = len(self.creatures) - max_pop
            victims = random.sample(list(self.creatures.keys()), to_cull)
            for vid in victims:
                self.creatures[vid].alive = False

        if len(self.creatures) < 5 and self.tick > 100:
            self._rescue_population()

        return self._stats()

    def _rescue_population(self):
        w, h = self.resources.shape
        new_creatures = []
        for _ in range(8):
            x, y = random.randint(0, w-1), random.randint(0, h-1)
            c = Creature(
                id=self.next_creature_id,
                x=x, y=y,
                genome=Genome(),
                energy=self.cfg["creatures"]["base_energy"] * 1.5,
                generation=0,
            )
            self.creatures[c.id] = c
            new_creatures.append(c)
            self.next_creature_id += 1
        self.rescue_count += 1
        self._log_event("rescue", f"Population rescue #{self.rescue_count} at tick {self.tick}")

        # Permanent, unconditional: rescues manufacture creatures with
        # random genomes far from existing clusters, which the species
        # clustering will likely register as emergences on the next
        # _update_species() pass. Logging the rescue itself as its own
        # fossil event_type means any downstream analysis can identify
        # and exclude turnover caused by life support rather than
        # evolvability, instead of silently conflating the two.
        avg_genes = np.mean([c.genome.genes for c in new_creatures], axis=0)
        record = FossilRecord(
            tick=self.tick,
            event_type="rescue",
            species_id=None,
            genome_snapshot=dict(zip(GENE_NAMES, avg_genes.tolist())),
            population=len(new_creatures),
            parent_species_id=None,
            metadata={"rescue_number": self.rescue_count, "temp_mean": float(self.temperature.mean())}
        )
        self.fossil_record.append(record)
        if self.db_conn is not None:
            persistence.write_fossil(self.db_conn, self.run_id, record)

    def _update_temperature(self):
        """Expire any temperature shocks past their end_tick, then
        recompute temperature from baseline * still-active multipliers.
        Multiple active shocks stack multiplicatively; each reverts
        independently on its own end_tick."""
        still_active = []
        for shock in self.active_temp_shocks:
            if self.tick >= shock.end_tick:
                self._log_event("shock_end", f"{shock.name.replace('_', ' ').title()} ends, temperature recovering")
            else:
                still_active.append(shock)
        self.active_temp_shocks = still_active

        combined = self.temp_baseline
        for shock in self.active_temp_shocks:
            combined *= shock.multiplier
        combined = float(np.clip(combined, self.temp_floor, self.temp_ceiling))
        self.temperature = np.full(self.temperature.shape, combined, dtype=np.float32)

    def _regen_resources(self):
        cfg = self.cfg["resources"]
        regen = self.base_regen * self.current_regen_mult * float(self.temperature.mean())

        clumping_shock = next((s for s in self.active_temp_shocks if s.clump), None)
        if clumping_shock:
            cutoff = np.percentile(self.resources, (1 - clumping_shock.refugia_fraction) * 100)
            mask = self.resources >= cutoff
            self.resources[mask] += regen * clumping_shock.refugia_bonus_mult
            self.resources[~mask] += regen * clumping_shock.refugia_penalty_mult
        else:
            self.resources += regen

        self.resources = np.clip(self.resources, 0, cfg["max_cell_energy"])

        if self.tick >= self.shock_end_tick and self.current_regen_mult < 1.0:
            self.current_regen_mult = 1.0
            self._log_event("shock_end", "Famine ended, resources recovering")

    def _handle_shocks(self):
        cfg = self.cfg["intervention"]
        if not cfg.get("enabled", True):
            return

        if self.pending_shock is None and random.random() < cfg["shock_probability"]:
            shock_type = random.choice(cfg["shock_types"])
            lead = cfg["announcement_lead_ticks"]
            trigger = self.tick + lead + random.randint(0, lead // 2)
            self.pending_shock = ShockEvent(
                name=shock_type["name"],
                announced_tick=self.tick,
                trigger_tick=trigger,
                params=shock_type,
            )
            self.shocks.append(self.pending_shock)
            self._log_event("shock_announce", f"Incoming: {shock_type['name']} at tick {trigger}")

        if self.pending_shock and self.tick >= self.pending_shock.trigger_tick:
            self._apply_shock(self.pending_shock)
            self.pending_shock.triggered = True
            self.pending_shock = None

    def _apply_shock(self, shock: ShockEvent):
        if shock.name == "ice_age":
            mult = shock.params.get("temp_drop", 0.5)
            duration = shock.params.get("duration_ticks", 800)
            self.active_temp_shocks.append(ActiveShock(
                name="ice_age", end_tick=self.tick + duration, multiplier=mult,
                clump=shock.params.get("resource_clump", False),
                refugia_fraction=shock.params.get("refugia_fraction", 0.15),
                refugia_bonus_mult=shock.params.get("refugia_bonus_mult", 2.0),
                refugia_penalty_mult=shock.params.get("refugia_penalty_mult", 0.2),
            ))
            self._log_event("shock", f"Ice Age begins (lasts {duration} ticks)")
        elif shock.name == "heat_wave":
            mult = shock.params.get("temp_rise", 1.4)
            duration = shock.params.get("duration_ticks", 800)
            self.active_temp_shocks.append(ActiveShock(name="heat_wave", end_tick=self.tick + duration, multiplier=mult))
            self._log_event("shock", f"Heat wave strikes (lasts {duration} ticks)")
        elif shock.name == "famine":
            self.current_regen_mult = shock.params.get("resource_regen_mult", 0.3)
            self.shock_end_tick = self.tick + shock.params.get("duration_ticks", 500)
            self._log_event("shock", "Famine spreads")

    def _creature_actions(self):
        w, h = self.resources.shape
        energy_cost = self.cfg["creatures"]["energy_cost_live"]
        move_cost = self.cfg["creatures"]["energy_cost_move"]
        eat_gain = self.cfg["creatures"]["energy_gain_eat"]

        creature_list = list(self.creatures.values())
        random.shuffle(creature_list)

        for c in creature_list:
            if not c.alive:
                continue

            c.age += 1
            c.energy -= energy_cost * c.genome.genes[1]

            if c.energy > move_cost:
                mx = random.randint(-c.move_range, c.move_range)
                my = random.randint(-c.move_range, c.move_range)
                c.x = (c.x + mx) % w
                c.y = (c.y + my) % h
                c.energy -= move_cost

            cell_res = self.resources[c.x, c.y]
            diet = c.genome.diet_type()

            if diet == "herbivore":
                amount = min(cell_res, eat_gain)
                c.energy += amount
                self.resources[c.x, c.y] -= amount
            elif diet == "carnivore":
                prey = self._find_prey(c)
                if prey:
                    c.energy += prey.energy * 0.4
                    prey.alive = False
                else:
                    amount = min(cell_res, eat_gain * 0.2)
                    c.energy += amount
                    self.resources[c.x, c.y] -= amount
            else:
                if cell_res > 3:
                    amount = min(cell_res, eat_gain * 0.6)
                    c.energy += amount
                    self.resources[c.x, c.y] -= amount
                else:
                    prey = self._find_prey(c)
                    if prey:
                        c.energy += prey.energy * 0.3
                        prey.alive = False

            if c.energy <= 0 or c.age > self.cfg["creatures"]["max_age"]:
                c.alive = False
                continue

            if c.can_reproduce() and len(self.creatures) < self.cfg["creatures"]["max_population"]:
                child = c.offspring(self.next_creature_id, w, h)
                self.next_creature_id += 1
                c.energy -= c.reproduce_cost()
                self.creatures[child.id] = child

    def _find_prey(self, predator: Creature) -> Optional[Creature]:
        w, h = self.resources.shape
        agg = predator.genome.genes[4]
        search_range = max(1, int(agg * 2))

        candidates = []
        for c in self.creatures.values():
            if c.id == predator.id or not c.alive:
                continue
            dx = min(abs(c.x - predator.x), w - abs(c.x - predator.x))
            dy = min(abs(c.y - predator.y), h - abs(c.y - predator.y))
            if dx <= search_range and dy <= search_range:
                if c.genome.genes[1] < predator.genome.genes[1] * 1.3:
                    candidates.append(c)

        return random.choice(candidates) if candidates else None

    def _remove_dead(self):
        dead = [cid for cid, c in self.creatures.items() if not c.alive]
        for cid in dead:
            del self.creatures[cid]

    def _update_species(self):
        if not self.creatures:
            self.species_map = {}
            return

        target_min = self.cfg["species"]["target_count_min"]
        target_max = self.cfg["species"]["target_count_max"]
        base_thresh = self.cfg["species"]["neat_compat_threshold"]
        min_cluster = self.cfg["species"]["min_cluster_size"]

        creatures_list = list(self.creatures.values())
        best_threshold = base_thresh
        best_clusters = []

        for thresh in np.linspace(0.5, 8.0, 30):
            clusters = self._cluster_at_threshold(creatures_list, thresh, min_cluster)
            n_species = len(clusters)
            if target_min <= n_species <= target_max:
                best_threshold = thresh
                best_clusters = clusters
                break
            elif n_species < target_min:
                best_threshold = thresh
                best_clusters = clusters
            elif n_species > target_max and not best_clusters:
                best_threshold = thresh
                best_clusters = clusters

        new_map: Dict[int, List[int]] = {}
        new_reps: Dict[int, Genome] = {}

        for cluster in best_clusters:
            rep = cluster[0].genome
            matched = False
            for sid, old_rep in self.species_reps.items():
                if rep.compat_distance(old_rep) < best_threshold * 1.5:
                    new_map[sid] = [c.id for c in cluster]
                    new_reps[sid] = Genome(rep.genes)
                    matched = True
                    break

            if not matched:
                sid = self.next_species_id
                self.next_species_id += 1
                new_map[sid] = [c.id for c in cluster]
                new_reps[sid] = Genome(rep.genes)
                self.species_ages[sid] = self.tick

                # Exact lineage, not inferred: majority non-null
                # parent_species_id among the founding cluster's
                # creatures. Each creature was stamped with its
                # parent's species_id at the moment of birth (the only
                # point both exist, since dead creatures are removed).
                parent_counts: Dict[Optional[int], int] = {}
                for c in cluster:
                    psid = c.parent_species_id
                    if psid is not None:
                        parent_counts[psid] = parent_counts.get(psid, 0) + 1
                self.species_parent[sid] = max(parent_counts, key=parent_counts.get) if parent_counts else None

        old_ids = set(self.species_map.keys())
        new_ids = set(new_map.keys())

        for extinct_sid in old_ids - new_ids:
            if extinct_sid not in self.species_extinct:
                self.species_extinct[extinct_sid] = self.tick
                self._fossilize(extinct_sid, "extinction")

        for new_sid in new_ids - old_ids:
            self._fossilize(new_sid, "species_emergence", parent_species_id=self.species_parent.get(new_sid))

        self.species_map = new_map
        self.species_reps = new_reps

        for sid, cids in self.species_map.items():
            for cid in cids:
                self.creatures[cid].species_id = sid

    def _cluster_at_threshold(self, creatures, threshold, min_size):
        unassigned = set(range(len(creatures)))
        clusters = []

        while unassigned:
            seed_idx = unassigned.pop()
            seed = creatures[seed_idx]
            cluster = [seed]
            to_remove = []

            for idx in unassigned:
                if seed.genome.compat_distance(creatures[idx].genome) < threshold:
                    cluster.append(creatures[idx])
                    to_remove.append(idx)

            for idx in to_remove:
                unassigned.remove(idx)

            if len(cluster) >= min_size:
                clusters.append(cluster)
            elif clusters:
                nearest = min(clusters, key=lambda cl: seed.genome.compat_distance(cl[0].genome))
                nearest.extend(cluster)

        return clusters

    def _fossilize(self, species_id: int, event_type: str, parent_species_id: Optional[int] = None):
        if species_id not in self.species_reps:
            return
        rep = self.species_reps[species_id]
        pop = len(self.species_map.get(species_id, []))

        record = FossilRecord(
            tick=self.tick,
            event_type=event_type,
            species_id=species_id,
            genome_snapshot=dict(zip(GENE_NAMES, rep.genes.tolist())),
            population=pop,
            parent_species_id=parent_species_id if parent_species_id is not None else self.species_parent.get(species_id),
            metadata={"temp_mean": float(self.temperature.mean())}
        )
        self.fossil_record.append(record)
        if self.db_conn is not None:
            persistence.write_fossil(self.db_conn, self.run_id, record)

    def _snapshot_fossils(self):
        for sid in self.species_map:
            self._fossilize(sid, "snapshot")

    def _log_event(self, event_type: str, message: str):
        self.events_log.append({"tick": self.tick, "type": event_type, "msg": message})

    def _stats(self) -> Dict:
        n_creatures = len(self.creatures)
        n_species = len(self.species_map)
        avg_energy = np.mean([c.energy for c in self.creatures.values()]) if self.creatures else 0
        avg_mut_rate = np.mean([c.genome.genes[5] for c in self.creatures.values()]) if self.creatures else 0

        return {
            "tick": self.tick,
            "creatures": n_creatures,
            "species": n_species,
            "avg_energy": round(float(avg_energy), 2),
            "avg_mut_rate": round(float(avg_mut_rate), 5),
            "temperature": round(float(self.temperature.mean()), 3),
            "pending_shock": self.pending_shock.name if self.pending_shock else None,
            "rescues": self.rescue_count,
        }
