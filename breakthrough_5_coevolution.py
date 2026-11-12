#!/usr/bin/env python3
"""
BREAKTHROUGH 5: Co-evolutionary Algorithm
Evolves both solutions AND optimization strategies simultaneously
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
print("BREAKTHROUGH ALGORITHM 5: CO-EVOLUTIONARY OPTIMIZATION")
print("Evolves solutions and strategies together")
print("=" * 80)

df = pd.read_csv("output/submission_final.csv")
targets = list(range(2, 151))

wins = {}

for idx, n in enumerate(targets, 1):
    rows = df[df['n'] == n]
    if len(rows) == 0: continue
    
    p_base = rows[['x', 'y', 'angle']].values
    
    print(f"[{idx}/{len(targets)}] n={n} - Co-evolution")
    
    # Population of (solution, strategy) pairs
    population = []
    pop_size = 8
    
    for i in range(pop_size):
        solution = p_base.copy() if i == 0 else pg.normalize(pg.repair(
            p_base + np.random.randn(n, 3) * np.array([0.01, 0.01, 5])
        ))
        
        # Random strategy genes
        strategy = {
            'method': np.random.choice(['polish', 'reclose']),
            'trust': 0.01 + 0.06 * np.random.random(),
            'reg_exp': -14 + 3 * np.random.random(),
            'tie': 0.15 + 0.25 * np.random.random()
        }
        
        population.append((solution, strategy))
    
    # Co-evolve for multiple generations
    for gen in range(20):
        # Evaluate fitness
        fitness = [(pg.side(sol), idx) for idx, (sol, strat) in enumerate(population)]
        fitness.sort()
        
        # Apply strategies to improve solutions
        for i in range(pop_size):
            solution, strategy = population[i]
            seed = np.random.randint(1e8)
            
            try:
                if strategy['method'] == 'polish':
                    improved, _, _ = polish.polish(solution, seed=seed, rounds=4,
                                                  max_seconds=8,
                                                  trust_start=strategy['trust'],
                                                  regularization=10**strategy['reg_exp'])
                else:
                    improved, _, _ = reclosure.reclose(solution, seed=seed,
                                                      trust=strategy['trust'],
                                                      tie=strategy['tie'],
                                                      rounds=4, seconds=8)
                
                if pg.side(improved) < pg.side(solution):
                    population[i] = (improved, strategy)
                    
            except:
                pass
        
        # Selection and reproduction every 5 generations
        if gen % 5 == 4:
            fitness = [(pg.side(sol), idx) for idx, (sol, strat) in enumerate(population)]
            fitness.sort()
            
            # Keep top half
            survivors = [population[idx] for _, idx in fitness[:pop_size//2]]
            
            # Create offspring by mixing strategies
            offspring = []
            for _ in range(pop_size//2):
                parent1, parent2 = np.random.choice(len(survivors), 2, replace=False)
                sol1, strat1 = survivors[parent1]
                sol2, strat2 = survivors[parent2]
                
                # Solution: copy better parent
                child_sol = sol1.copy() if pg.side(sol1) < pg.side(sol2) else sol2.copy()
                
                # Strategy: crossover and mutate
                child_strat = {
                    'method': np.random.choice([strat1['method'], strat2['method']]),
                    'trust': (strat1['trust'] + strat2['trust']) / 2 + np.random.randn() * 0.01,
                    'reg_exp': (strat1['reg_exp'] + strat2['reg_exp']) / 2 + np.random.randn() * 0.3,
                    'tie': (strat1['tie'] + strat2['tie']) / 2 + np.random.randn() * 0.03
                }
                
                # Clip to valid ranges
                child_strat['trust'] = max(0.01, min(0.07, child_strat['trust']))
                child_strat['reg_exp'] = max(-14, min(-11, child_strat['reg_exp']))
                child_strat['tie'] = max(0.15, min(0.4, child_strat['tie']))
                
                offspring.append((child_sol, child_strat))
            
            population = survivors + offspring
    
    # Get best
    best_solution = min(population, key=lambda p: pg.side(p[0]))[0]
    
    if pg.side(best_solution) < pg.side(p_base) - 1e-12:
        wins[n] = best_solution
        print(f"  ★★ n={n}: WIN!")

if wins:
    np.savez_compressed(f"output/coevo_wins_{len(wins)}.npz",
                       **{str(k): v for k, v in wins.items()})
    df_new = df.copy()
    for n, packing in wins.items():
        df_new.loc[df_new['n'] == n, ['x', 'y', 'angle']] = packing
    from src.tools.reference_sources.official_metric import score
    s = score(df_new, 'id', 'n')
    df_new.to_csv(f"output/submission_{s:.6f}.csv", index=False)
    print(f"\n✓ BREAKTHROUGH 5: Score {s:.12f}, {len(wins)} wins")
