#!/usr/bin/env python3
"""
GENETIC ALGORITHM OPTIMIZER - Evolutionary approach
Uses population-based optimization with crossover and mutation
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import time
import json

sys.path.insert(0, str(Path(__file__).parent / 'tools'))
import packing_geometry as pg
import cpu_contact_polish as polish

def genetic_optimize(n, p_base, population_size=50, generations=200):
    """Genetic algorithm optimization"""
    try:
        L0 = pg.side(p_base)
        
        # Initialize population
        population = [p_base.copy()]
        rng = np.random.default_rng(42)
        
        for i in range(population_size - 1):
            p = p_base.copy()
            scale = 0.005 * (1 + i/population_size)
            p[:, 0] += rng.normal(0, scale, n)
            p[:, 1] += rng.normal(0, scale, n)
            p[:, 2] += rng.normal(0, scale * 2, n)
            p = pg.normalize(p)
            population.append(p)
        
        best_L = L0
        best_p = p_base.copy()
        
        for gen in range(generations):
            # Evaluate population
            fitness = []
            for p in population:
                try:
                    L = pg.side(p)
                    fitness.append(L)
                    if L < best_L - 1e-11:
                        best_L = L
                        best_p = p.copy()
                except:
                    fitness.append(1e10)
            
            # Selection (tournament)
            selected = []
            for _ in range(population_size):
                i1, i2 = rng.integers(0, population_size, 2)
                selected.append(population[i1] if fitness[i1] < fitness[i2] else population[i2])
            
            # Crossover and mutation
            next_pop = [best_p.copy()]  # Elitism
            for i in range(0, population_size - 1, 2):
                if i + 1 < len(selected):
                    # Crossover
                    alpha = rng.random()
                    child1 = alpha * selected[i] + (1-alpha) * selected[i+1]
                    child2 = (1-alpha) * selected[i] + alpha * selected[i+1]
                    
                    # Mutation
                    if rng.random() < 0.3:
                        child1[:, 2] += rng.normal(0, 0.01, n)
                    if rng.random() < 0.3:
                        child2[:, 2] += rng.normal(0, 0.01, n)
                    
                    child1 = pg.normalize(child1)
                    child2 = pg.normalize(child2)
                    
                    # Polish offspring
                    try:
                        child1, _, _ = polish.polish(child1, seed=gen, rounds=30, max_seconds=2.0, trust_start=0.02)
                        child1 = pg.repair(child1, clearance=1e-10)
                    except:
                        pass
                    
                    if child1 is not None:
                        next_pop.append(child1)
                    if child2 is not None and len(next_pop) < population_size:
                        next_pop.append(child2)
            
            population = next_pop[:population_size]
            
            if (gen + 1) % 50 == 0:
                print(f"    Gen {gen+1}: best_L={best_L:.12f}")
        
        if best_L < L0 - 1e-11:
            return (n, L0, best_L, best_p)
    except Exception as e:
        pass
    return None

def main():
    print("=" * 80)
    print("GENETIC ALGORITHM OPTIMIZER")
    print("=" * 80)
    
    baseline_path = 'output/submission_22.251122.csv'
    df = pd.read_csv(baseline_path)
    
    # Target medium-large puzzles
    puzzles = []
    for n in range(250, 501):
        g = df[df['n'] == n].sort_values('square_id')
        if len(g) > 0:
            p = g[['x', 'y', 'angle']].to_numpy(float)
            L = pg.side(p)
            waste = L / np.sqrt(n) - 1
            puzzles.append((waste, n, p))
    
    puzzles.sort(reverse=True)
    targets = puzzles[:60]
    
    print(f"\nTargeting {len(targets)} puzzles with genetic algorithm")
    print(f"Top 10: {[n for _, n, _ in targets[:10]]}\n")
    
    wins = []
    for i, (waste, n, p) in enumerate(targets):
        print(f"[{i+1}/{len(targets)}] Evolving n={n}...")
        result = genetic_optimize(n, p, population_size=50, generations=200)
        if result is not None:
            wins.append(result)
            print(f"  ✓ WIN: gain={result[1]-result[2]:.12e}")
    
    print(f"\nGenetic: {len(wins)} wins")
    if wins:
        np.savez('output/genetic_wins.npz', **{str(n): p for n, _, _, p in wins})
        with open('output/genetic_summary.json', 'w') as f:
            json.dump({'wins': len(wins), 'total_gain': float(sum(L0-L for n,L0,L,p in wins))}, f)

if __name__ == '__main__':
    main()
