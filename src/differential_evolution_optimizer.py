#!/usr/bin/env python3
"""
DIFFERENTIAL EVOLUTION OPTIMIZER
Population-based stochastic search
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import json

sys.path.insert(0, str(Path(__file__).parent / 'tools'))
import packing_geometry as pg

def differential_evolution(n, p_base, pop_size=30, generations=150):
    """Differential evolution optimization"""
    try:
        L0 = pg.side(p_base)
        rng = np.random.default_rng(n * 13)
        
        # Initialize population
        population = []
        for i in range(pop_size):
            p = p_base.copy()
            if i > 0:
                scale = 0.003 * (1 + i/pop_size)
                p[:, 0] += rng.normal(0, scale, n)
                p[:, 1] += rng.normal(0, scale, n)
                p[:, 2] += rng.normal(0, scale * 2, n)
                p = pg.normalize(p)
            population.append(p)
        
        best_L = L0
        best_p = p_base.copy()
        
        F = 0.8  # Differential weight
        CR = 0.9  # Crossover probability
        
        for gen in range(generations):
            for i in range(pop_size):
                # Select three random distinct individuals
                indices = [j for j in range(pop_size) if j != i]
                a, b, c = rng.choice(indices, 3, replace=False)
                
                # Mutation
                mutant = population[a] + F * (population[b] - population[c])
                mutant = pg.normalize(mutant)
                
                # Crossover
                trial = population[i].copy()
                for j in range(n):
                    if rng.random() < CR:
                        trial[j] = mutant[j]
                
                trial = pg.repair(trial, clearance=1e-10)
                
                if trial is not None:
                    try:
                        L_trial = pg.side(trial)
                        L_current = pg.side(population[i])
                        
                        if L_trial < L_current:
                            population[i] = trial
                            if L_trial < best_L - 1e-11:
                                best_L = L_trial
                                best_p = trial.copy()
                    except:
                        pass
        
        if best_L < L0 - 1e-11:
            return (n, L0, best_L, best_p)
    except:
        pass
    return None

def main():
    print("=" * 80)
    print("DIFFERENTIAL EVOLUTION OPTIMIZER")
    print("=" * 80)
    
    baseline_path = 'output/submission_22.251122.csv'
    df = pd.read_csv(baseline_path)
    
    puzzles = []
    for n in range(350, 651, 3):  # Every 3rd puzzle
        g = df[df['n'] == n].sort_values('square_id')
        if len(g) > 0:
            p = g[['x', 'y', 'angle']].to_numpy(float)
            puzzles.append((n, p))
    
    print(f"\nTargeting {len(puzzles)} puzzles with differential evolution\n")
    
    wins = []
    for i, (n, p) in enumerate(puzzles):
        result = differential_evolution(n, p, pop_size=30, generations=150)
        if result is not None:
            wins.append(result)
            print(f"✓ n={n}: gain={result[1]-result[2]:.12e}")
        
        if (i+1) % 20 == 0:
            print(f"  Progress: {i+1}/{len(puzzles)}")
    
    print(f"\nDifferential evolution: {len(wins)} wins")
    if wins:
        np.savez('output/diffevo_wins.npz', **{str(n): p for n, _, _, p in wins})

if __name__ == '__main__':
    main()
