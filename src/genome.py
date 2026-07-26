import numpy as np

# Genome indices
MOVE_EFF = 0
SIZE = 1
DIET = 2
REPRO_THRESH = 3
AGGRESSION = 4
MUT_RATE = 5

GENE_NAMES = [
    "move_eff", "size", "diet", "repro_thresh",
    "aggression", "mut_rate"
]

GENE_MIN = np.array([0.1, 0.5, 0.0, 30.0, 0.0, 0.001])
GENE_MAX = np.array([2.0, 3.0, 1.0, 100.0, 1.0, 0.1])
GENE_WEIGHTS = np.array([1.0, 1.0, 2.0, 0.5, 1.0, 3.0])


class Genome:
    """Float-array genome with heritable mutation rate."""

    def __init__(self, genes: np.ndarray = None):
        if genes is None:
            self.genes = np.random.uniform(GENE_MIN, GENE_MAX)
        else:
            self.genes = np.clip(genes.copy(), GENE_MIN, GENE_MAX)

    def mutate(self, floor: float = 0.002) -> "Genome":
        """Return a mutated copy. Mutation rate itself is gene 5.

        floor is a parameter, not a global/class constant, specifically
        so the Section 1 floor-sensitivity sweep can vary it per-arm
        under multiprocessing without any shared mutable state across
        worker processes."""
        mut_rate = float(self.genes[MUT_RATE])
        mask = np.random.random(len(self.genes)) < mut_rate
        if not mask.any():
            return Genome(self.genes)

        child = self.genes.copy()
        noise = np.random.normal(0, 0.1, len(self.genes))
        child[mask] += noise[mask]
        child = np.clip(child, GENE_MIN, GENE_MAX)

        # Ensure mut_rate doesn't collapse to zero
        if child[MUT_RATE] < floor:
            child[MUT_RATE] = floor

        return Genome(child)

    def compat_distance(self, other: "Genome") -> float:
        """NEAT-style weighted compatibility distance."""
        diff = np.abs(self.genes - other.genes)
        scaled = diff / (GENE_MAX - GENE_MIN)
        return float(np.sum(scaled * GENE_WEIGHTS))

    def diet_type(self) -> str:
        """herbivore (<0.5), omnivore, carnivore (>0.5)"""
        d = self.genes[DIET]
        if d < 0.33:
            return "herbivore"
        elif d < 0.66:
            return "omnivore"
        return "carnivore"

    def __repr__(self):
        parts = [f"{n}={self.genes[i]:.3f}" for i, n in enumerate(GENE_NAMES)]
        return f"Genome({', '.join(parts)})"


def random_genome() -> Genome:
    return Genome()
