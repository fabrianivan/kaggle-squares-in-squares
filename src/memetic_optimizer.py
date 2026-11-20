#!/usr/bin/env python3
"""
Memetic Algorithm Optimizer - Combines genetic evolution with local search
"""
import sys
sys.path.insert(0, '.')
import numpy as np
import pandas as pd
import time
from src.tools import packing_geometry as pg

def local_improve(packing, max_seconds=30):
    """Local improvement step"""
    from src.tools.cpu_contact_polish import polish
    try:
        return polish(packing, seed=np.random.randint(1e9), rounds=3,
                     max_seconds=max_seconds, trust_start=0.3, regularization=1e-11)
    except:
        return packing

def crossover(parent1, parent2):
    """Combine two packings"""
    n = len(parent1)
    mask = np.random.random(n) < 0.5
    child = parent1.copy()
    child[mask] = parent2[mask]
    return pg.normalize(pg.repair(child))

def mutate(packing, rate=0.1):
    """Random mutation"""
    n = len(packing)
    num_mutate = max(1, int(n * rate))
    indices = np.random.choice(n, num_mutate, replace=False)
    
    p = packing.copy()
    p[indices, :2] += np.random.randn(num_mutate, 2) * 0.03
    p[indices, 2] += np.random.randn(num_mutate) * 15
    return pg.normalize(pg.repair(p))

def memetic_optimize_puzzle(n, baseline_packing, population_size=15, generations=20):
    """Memetic algorithm: GA + local search"""
    
    # Initialize population
    population = [baseline_packing.copy()]
    
    # Create variants
    for i in range(population_size - 1):
        variant = baseline_packing.copy()
        variant[:, :2] += np.random.randn(n, 2) * 0.02
        variant[:, 2] += np.random.randn(n) * 10
        variant = pg.normalize(pg.repair(variant))
        population.append(variant)
    
    # Apply local search to initial population
    population = [local_improve(p, max_seconds=15) for p in population]
    
    best_ever = min(population, key=lambda p: pg.side(p))
    best_side = pg.side(best_ever)
    
    for gen in range(generations):
        # Evaluate fitness (lower side = better)
        fitness = [(pg.side(p), i) for i, p in enumerate(population)]
        fitness.sort()
        
        # Selection: keep top 50%
        num_keep = population_size // 2
        survivors_indices = [idx for _, idx in fitness[:num_keep]]
        survivors = [population[idx] for idx in survivors_indices]
        
        # Generate offspring
        offspring = []
        while len(offspring) < population_size - num_keep:
            # Select two random parents from survivors
            p1, p2 = np.random.choice(survivors, 2, replace=False)
            
            # Crossover
            child = crossover(p1, p2)
            
            # Mutation
            if np.random.random() < 0.8:
                child = mutate(child, rate=0.1)
            
            # Local search on child
            child = local_improve(child, max_seconds=10)
            offspring.append(child)
        
        # New population
        population = survivors + offspring
        
        # Track best
        gen_best = min(population, key=lambda p: pg.side(p))
        gen_best_side = pg.side(gen_best)
        
        if gen_best_side < best_side:
            best_ever = gen_best
            best_side = gen_best_side
            print(f"  n={n}: Gen {gen} improved to {best_side:.12f}")
    
    return best_ever, best_side

def main():
    baseline_path = "output/submission_final.csv"
    df = pd.read_csv(baseline_path)
    
    print("=" * 80)
    print("MEMETIC ALGORITHM OPTIMIZER")
    print("=" * 80)
    
    # Target 150 puzzles
    targets = list(range(2, 121)) + list(range(200, 501, 3)) + list(range(600, 751, 5))
    print(f"Targeting {len(targets)} puzzles with memetic algorithm")
    
    wins = {}
    start_time = time.time()
    
    for idx, n in enumerate(targets, 1):
        print(f"\n[{idx}/{len(targets)}] n={n}")
        
        baseline_row = df[df['n'] == n].iloc[0]
        baseline_packing = np.array(eval(baseline_row['squares']))
        baseline_side = pg.side(baseline_packing)
        
        # Larger population for small puzzles
        pop_size = 20 if n < 100 else 15
        gens = 25 if n < 100 else 20
        
        best, best_side = memetic_optimize_puzzle(n, baseline_packing, pop_size, gens)
        
        if best_side < baseline_side - 1e-12:
            improvement = baseline_side - best_side
            wins[n] = best
            print(f"  ★ WIN: {baseline_side:.12f} → {best_side:.12f} (Δ={improvement:.12e})")
        
        if idx % 15 == 0:
            print(f">>> {len(wins)} wins, {(time.time()-start_time)/60:.1f}m elapsed")
    
    if wins:
        out_path = f"output/memetic_wins_{len(wins)}.npz"
        np.savez_compressed(out_path, **{str(k): v for k, v in wins.items()})
        print(f"\n✓ Saved {len(wins)} wins to {out_path}")
        
        df_new = df.copy()
        for n, packing in wins.items():
            df_new.loc[df_new['n'] == n, 'squares'] = str(packing.tolist())
        
        from src.metric.metric import score as compute_score
        new_score = compute_score(df_new, 'n')
        sub_path = f"output/submission_{new_score:.6f}.csv"
        df_new.to_csv(sub_path, index=False)
        print(f"✓ New submission: {sub_path}")
    
    print(f"\nTotal: {(time.time()-start_time)/60:.1f} minutes")

if __name__ == "__main__":
    main()
