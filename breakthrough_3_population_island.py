#!/usr/bin/env python3
"""
BREAKTHROUGH 3: Island Population Model
Multiple populations evolve independently then share best solutions
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'tools'))

import numpy as np
import pandas as pd
import packing_geometry as pg
import cpu_contact_polish as polish
import cpu_axis_reclosure as reclosure

print("=" * 80)
print("BREAKTHROUGH ALGORITHM 3: ISLAND POPULATION MODEL")
print("Multiple independent populations with periodic migration")
print("=" * 80)

df = pd.read_csv("output/submission_final.csv")
targets = list(range(2, 151))

wins = {}

for idx, n in enumerate(targets, 1):
    rows = df[df['n'] == n]
    if len(rows) == 0: continue
    
    p_base = rows[['x', 'y', 'angle']].values
    
    print(f"[{idx}/{len(targets)}] n={n} - Island Model (5 islands)")
    
    # Create 5 islands
    num_islands = 5
    pop_per_island = 4
    
    islands = []
    for i in range(num_islands):
        population = []
        for j in range(pop_per_island):
            if j == 0:
                population.append(p_base.copy())
            else:
                # Create variant
                variant = p_base.copy()
                variant[:, :2] += np.random.randn(n, 2) * 0.01
                variant[:, 2] += np.random.randn(n) * 5
                variant = pg.normalize(pg.repair(variant))
                population.append(variant)
        islands.append(population)
    
    # Evolve islands
    for generation in range(15):
        # Each island evolves independently
        for island_idx, island in enumerate(islands):
            for member_idx in range(pop_per_island):
                seed = np.random.randint(1e8)
                
                # Alternate between methods
                if (generation + member_idx) % 2 == 0:
                    trust = 0.02 + 0.03 * island_idx / num_islands
                    reg = 10 ** (-13 + island_idx * 0.5 / num_islands)
                    try:
                        improved, _, _ = polish.polish(island[member_idx], 
                                                      seed=seed, rounds=4, 
                                                      max_seconds=8,
                                                      trust_start=trust,
                                                      regularization=reg)
                        if pg.side(improved) < pg.side(island[member_idx]):
                            island[member_idx] = improved
                    except:
                        pass
                else:
                    trust = 0.18 + 0.2 * island_idx / num_islands
                    tie = 0.18 + 0.15 * island_idx / num_islands
                    try:
                        improved, _, _ = reclosure.reclose(island[member_idx],
                                                          seed=seed,
                                                          trust=trust, tie=tie,
                                                          rounds=4, seconds=8)
                        if pg.side(improved) < pg.side(island[member_idx]):
                            island[member_idx] = improved
                    except:
                        pass
        
        # Migration every 5 generations
        if generation % 5 == 4:
            # Find best from each island
            island_best = [min(island, key=lambda p: pg.side(p)) for island in islands]
            
            # Share best solutions
            for island in islands:
                # Replace worst with copy of random island's best
                worst_idx = max(range(pop_per_island), 
                               key=lambda i: pg.side(island[i]))
                island[worst_idx] = island_best[np.random.randint(num_islands)].copy()
    
    # Find overall best
    all_solutions = [member for island in islands for member in island]
    best = min(all_solutions, key=lambda p: pg.side(p))
    best_L = pg.side(best)
    
    if best_L < pg.side(p_base) - 1e-12:
        wins[n] = best
        print(f"  ★★ n={n}: WIN! {pg.side(p_base):.12f} → {best_L:.12f}")

if wins:
    np.savez_compressed(f"output/island_wins_{len(wins)}.npz",
                       **{str(k): v for k, v in wins.items()})
    df_new = df.copy()
    for n, packing in wins.items():
        df_new.loc[df_new['n'] == n, ['x', 'y', 'angle']] = packing
    from src.tools.reference_sources.official_metric import score
    s = score(df_new, 'id', 'n')
    df_new.to_csv(f"output/submission_{s:.6f}.csv", index=False)
    print(f"\n✓ BREAKTHROUGH 3: Score {s:.12f}, {len(wins)} wins")
