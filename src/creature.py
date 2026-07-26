import numpy as np
from dataclasses import dataclass, field
from typing import Optional
from src.genome import Genome, MOVE_EFF, SIZE, REPRO_THRESH, AGGRESSION, MUT_RATE

@dataclass
class Creature:
    id: int
    x: int
    y: int
    genome: Genome
    energy: float
    age: int = 0
    generation: int = 0
    species_id: Optional[int] = None
    parent_id: Optional[int] = None
    parent_species_id: Optional[int] = None
    alive: bool = True

    @property
    def move_range(self) -> int:
        """Larger creatures move slower but have more energy capacity."""
        eff = self.genome.genes[MOVE_EFF]
        sz = self.genome.genes[SIZE]
        return max(1, int(eff * 2 / max(sz, 0.5)))

    @property
    def max_energy(self) -> float:
        return 50.0 + self.genome.genes[SIZE] * 30.0

    @property
    def repro_threshold(self) -> float:
        return self.genome.genes[REPRO_THRESH]

    def can_reproduce(self) -> bool:
        return self.energy >= self.repro_threshold and self.age > 10

    def reproduce_cost(self) -> float:
        return self.energy * 0.4

    def offspring(self, next_id: int, world_w: int, world_h: int,
                  fixed_mutation_rate: Optional[float] = None,
                  mutation_rate_floor: float = 0.002) -> "Creature":
        """Create a mutated child nearby.

        fixed_mutation_rate, if set (fixed-rate arms), pins the child's
        mutation-rate gene instead of letting it evolve like every other
        gene. mutation_rate_floor (evolving arms only -- ignored when
        fixed_mutation_rate is set) is the Section 1 floor-sensitivity
        sweep's knob, threaded through rather than a module-level
        constant so it stays safe under multiprocessing."""
        child_genome = self.genome.mutate(floor=mutation_rate_floor)
        if fixed_mutation_rate is not None:
            child_genome.genes[MUT_RATE] = fixed_mutation_rate
        dx = np.random.randint(-1, 2)
        dy = np.random.randint(-1, 2)
        nx = (self.x + dx) % world_w
        ny = (self.y + dy) % world_h

        return Creature(
            id=next_id,
            x=nx,
            y=ny,
            genome=child_genome,
            energy=self.reproduce_cost(),
            age=0,
            generation=self.generation + 1,
            parent_id=self.id,
            parent_species_id=self.species_id,
        )

    def __hash__(self):
        return self.id

    def __eq__(self, other):
        if isinstance(other, Creature):
            return self.id == other.id
        return False
