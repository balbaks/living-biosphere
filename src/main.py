#!/usr/bin/env python3
"""Living Biosphere — Section 1 simulation runner."""

import sys
import time
import yaml
from pathlib import Path

# Add project root to path so src imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.world import World


def load_config():
    cfg_path = Path(__file__).parent.parent / "config" / "world.yaml"
    with open(cfg_path) as f:
        return yaml.safe_load(f)


def run_simulation(config, max_ticks=None, print_interval=100):
    """Run the world and print stats."""
    if max_ticks is None:
        max_ticks = config["world"].get("max_ticks", 0)
    
    world = World(config)
    print(f"RNG seed: {world.rng_seed}")
    print("=" * 60)
    print(f"{'Tick':>8} {'Creatures':>10} {'Species':>8} {'AvgEnergy':>10} {'MutRate':>10} {'Temp':>6}")
    print("-" * 60)
    
    start_time = time.time()
    
    try:
        while True:
            if max_ticks > 0 and world.tick >= max_ticks:
                break
            
            stats = world.tick_step()
            
            if world.tick % print_interval == 0:
                print(f"{stats['tick']:>8} {stats['creatures']:>10} {stats['species']:>8} "
                      f"{stats['avg_energy']:>10.1f} {stats['avg_mut_rate']:>10.5f} {stats['temperature']:>6.3f}")
                
                if stats.get("pending_shock"):
                    print(f"  >>> SHOCK ANNOUNCED: {stats['pending_shock']}")
            
            # Small sleep so you can watch it
            time.sleep(config["world"].get("tick_speed_ms", 100) / 1000.0)
    
    except KeyboardInterrupt:
        print("\n" + "=" * 60)
        print("Simulation stopped by user.")
    
    elapsed = time.time() - start_time
    print(f"\nRan {world.tick} ticks in {elapsed:.1f}s ({world.tick/elapsed:.0f} ticks/sec)")
    print(f"Final: {stats['creatures']} creatures, {stats['species']} species")
    print(f"Fossil records: {len(world.fossil_record)}")
    print(f"Extinctions logged: {len(world.species_extinct)}")
    
    return world


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Living Biosphere sim runner")
    parser.add_argument("--ticks", "-t", type=int, default=5000, help="Ticks to run (0=forever)")
    parser.add_argument("--interval", "-i", type=int, default=100, help="Print every N ticks")
    parser.add_argument("--seed", "-s", type=int, default=None, help="RNG seed")
    args = parser.parse_args()
    
    config = load_config()
    if args.seed is not None:
        config["rng"] = {"seed": args.seed}
    
    world = run_simulation(config, max_ticks=args.ticks, print_interval=args.interval)
