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

    def offspring(self, next_id: int, world_w: int, world_h: int, fixed_mutation_rate: Optional[float] = None) -> "Creature":
        """Create a mutated child nearby.

        fixed_mutation_rate, if set (Arm B/B2 of the Section 1.2 harness),
        pins the child's mutation-rate gene instead of letting it evolve
        like every other gene -- the whole point of that arm."""
        child_genome = self.genome.mutate()
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
