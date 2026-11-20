#!/usr/bin/env python3
"""
Neural Evolution Strategy (NES) - Advanced optimization combining:
- Natural Evolution Strategies
- Covariance Matrix Adaptation (CMA-ES inspired)
- Self-adaptive parameter control
- Fitness shaping
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'tools'))

import numpy as np
import pandas as pd
import packing_geometry as pg
import cpu_axis_reclosure as reclosure
import cpu_contact_polish as polish
import time

class CovarianceMatrixAdaptation:
    """CMA-ES inspired optimizer for packing problems"""
    
    def __init__(self, dim, sigma=0.1, popsize=None):
        self.dim = dim
        self.sigma = sigma
        self.popsize = popsize or (4 + int(3 * np.log(dim)))
        
        # Initialize distribution
        self.mean = np.zeros(dim)
        self.C = np.eye(dim)  # Covariance matrix
        self.pc = np.zeros(dim)  # Evolution path for C
        self.ps = np.zeros(dim)  # Evolution path for sigma
        
        # Strategy parameters
        self.mu = self.popsize // 2
        self.weights = np.log(self.mu + 0.5) - np.log(np.arange(1, self.mu + 1))
        self.weights /= self.weights.sum()
        
        self.mueff = 1 / (self.weights ** 2).sum()
        self.cc = 4 / (dim + 4)
        self.cs = (self.mueff + 2) / (dim + self.mueff + 5)
        self.c1 = 2 / ((dim + 1.3) ** 2 + self.mueff)
        self.cmu = min(1 - self.c1, 2 * (self.mueff - 2 + 1/self.mueff) / ((dim + 2) ** 2 + self.mueff))
        self.damps = 1 + 2 * max(0, np.sqrt((self.mueff - 1) / (dim + 1)) - 1) + self.cs
        
        self.eigeneval = 0
        self.B = np.eye(dim)
        self.D = np.ones(dim)
        self.BD = self.B * self.D
        self.chiN = dim ** 0.5 * (1 - 1 / (4 * dim) + 1 / (21 * dim ** 2))
        
        self.gen = 0
    
    def ask(self):
        """Generate new population"""
        arz = np.random.randn(self.popsize, self.dim)
        ary = arz @ self.BD.T
        arx = self.mean + self.sigma * ary
        return arx, arz
    
    def tell(self, arx, fitness):
        """Update distribution based on fitness"""
        # Sort by fitness
        arindex = np.argsort(fitness)[::-1]  # Maximize
        
        # Update mean
        old_mean = self.mean.copy()
        self.mean = (self.weights @ arx[arindex[:self.mu]])
        
        # Cumulation
        ps_factor = np.sqrt(self.cs * (2 - self.cs) * self.mueff)
        self.ps = (1 - self.cs) * self.ps + ps_factor * np.linalg.inv(self.BD) @ (self.mean - old_mean) / self.sigma
        
        hsig = (np.linalg.norm(self.ps) / np.sqrt(1 - (1 - self.cs) ** (2 * self.gen)) 
                < 1.4 + 2 / (self.dim + 1) * self.chiN)
        
        pc_factor = np.sqrt(self.cc * (2 - self.cc) * self.mueff)
        self.pc = (1 - self.cc) * self.pc + hsig * pc_factor * (self.mean - old_mean) / self.sigma
        
        # Update covariance matrix
        artmp = (arx[arindex[:self.mu]] - old_mean) / self.sigma
        self.C = ((1 - self.c1 - self.cmu) * self.C + 
                  self.c1 * (self.pc[:, None] @ self.pc[None, :] + 
                            (1 - hsig) * self.cc * (2 - self.cc) * self.C) +
                  self.cmu * (artmp.T @ np.diag(self.weights) @ artmp))
        
        # Update sigma
        self.sigma *= np.exp((self.cs / self.damps) * (np.linalg.norm(self.ps) / self.chiN - 1))
        
        # Update eigendecomposition
        if self.gen % (1 / (self.c1 + self.cmu) / self.dim / 10) < 1:
            self.C = np.triu(self.C) + np.triu(self.C, 1).T
            self.D, self.B = np.linalg.eigh(self.C)
            self.D = np.sqrt(np.maximum(self.D, 0))
            self.BD = self.B * self.D
        
        self.gen += 1

def natural_evolution_strategy(packing, n_generations=30, popsize=20):
    """Natural Evolution Strategy optimizer"""
    n = len(packing)
    dim = n * 3  # x, y, angle for each square
    
    # Initialize CMA-ES
    cma = CovarianceMatrixAdaptation(dim, sigma=0.05, popsize=popsize)
    cma.mean = packing.flatten()
    
    best_pack = packing.copy()
    best_L = pg.side(best_pack)
    
    for gen in range(n_generations):
        # Generate population
        candidates, _ = cma.ask()
        
        # Evaluate fitness
        fitness = []
        valid_candidates = []
        
        for i, candidate in enumerate(candidates):
            pack = candidate.reshape(n, 3)
            
            # Quick polish
            try:
                if gen > 10 and i < popsize // 3:  # Polish best third in later generations
                    pack, _, _ = polish.polish(pack, seed=gen*100+i,
                                              rounds=3, max_seconds=5,
                                              trust_start=0.02,
                                              regularization=1e-12)
                
                L = pg.side(pack)
                fitness.append(-L)  # Negative for minimization
                valid_candidates.append(pack)
                
                if L < best_L:
                    best_L = L
                    best_pack = pack.copy()
            except:
                fitness.append(-1e10)  # Invalid
                valid_candidates.append(pack)
        
        # Update distribution
        cma.tell(candidates, np.array(fitness))
        
        if gen % 5 == 0:
            print(f"      Gen {gen:2d}: L={best_L:.9f}", end="\r", flush=True)
    
    print()
    return best_pack, best_L

def fitness_shaping(fitness_values, method='rank'):
    """Shape fitness landscape for better optimization"""
    if method == 'rank':
        # Rank-based fitness
        ranks = np.argsort(np.argsort(fitness_values))
        return ranks / len(fitness_values)
    elif method == 'boltzmann':
        # Boltzmann selection
        T = 1.0
        exp_fitness = np.exp(fitness_values / T)
        return exp_fitness / exp_fitness.sum()
    else:
        return fitness_values

def self_adaptive_optimize(packing, n_iters=100):
    """Self-adaptive parameter optimization"""
    n = len(packing)
    
    # Each individual carries its own strategy parameters
    population = []
    for i in range(15):
        ind = {
            'pack': packing.copy(),
            'trust': 0.15 + 0.25 * np.random.random(),
            'tie': 0.15 + 0.25 * np.random.random(),
            'reg': 10 ** (-13 + 2 * np.random.random()),
            'fitness': None
        }
        
        # Evaluate
        try:
            optimized, _, _ = reclosure.reclose(ind['pack'], seed=i*100,
                                               trust=ind['trust'], 
                                               tie=ind['tie'],
                                               rounds=4, seconds=8)
            ind['pack'] = optimized
            ind['fitness'] = -pg.side(optimized)
        except:
            ind['fitness'] = -1e10
        
        population.append(ind)
    
    best_pack = max(population, key=lambda x: x['fitness'])['pack']
    best_L = pg.side(best_pack)
    
    # Evolve
    for iteration in range(20):
        # Sort by fitness
        population.sort(key=lambda x: x['fitness'], reverse=True)
        
        # Generate offspring
        new_pop = population[:5]  # Keep elite
        
        while len(new_pop) < 15:
            # Select parent
            parent = population[np.random.randint(7)]
            
            # Create offspring with mutated parameters
            child = {
                'pack': parent['pack'].copy(),
                'trust': parent['trust'] * np.exp(0.2 * np.random.randn()),
                'tie': parent['tie'] * np.exp(0.2 * np.random.randn()),
                'reg': parent['reg'] * np.exp(0.5 * np.random.randn()),
            }
            
            # Clip parameters
            child['trust'] = np.clip(child['trust'], 0.1, 0.6)
            child['tie'] = np.clip(child['tie'], 0.1, 0.5)
            child['reg'] = np.clip(child['reg'], 1e-14, 1e-9)
            
            # Optimize
            try:
                optimized, _, _ = reclosure.reclose(child['pack'], 
                                                   seed=iteration*1000,
                                                   trust=child['trust'],
                                                   tie=child['tie'],
                                                   rounds=4, seconds=8)
                child['pack'] = optimized
                child['fitness'] = -pg.side(optimized)
                
                if -child['fitness'] < best_L:
                    best_L = -child['fitness']
                    best_pack = child['pack'].copy()
            except:
                child['fitness'] = -1e10
            
            new_pop.append(child)
        
        population = new_pop
    
    return best_pack, best_L

def optimize_puzzle_nes(args):
    """Neural evolution strategy for single puzzle"""
    n, p_base = args
    
    print(f"  n={n:4d} L_start={pg.side(p_base):.9f}")
    
    original_L = pg.side(p_base)
    best_p = p_base.copy()
    best_L = original_L
    
    # Strategy 1: Natural Evolution Strategy (CMA-ES)
    if n < 300:  # CMA-ES works best for smaller problems
        try:
            print(f"    Running NES/CMA-ES...")
            candidate, candidate_L = natural_evolution_strategy(best_p, n_generations=20, popsize=15)
            if candidate_L < best_L:
                best_L = candidate_L
                best_p = candidate.copy()
                print(f"    NES improved: {candidate_L:.9f}")
        except Exception as e:
            print(f"    NES failed: {e}")
    
    # Strategy 2: Self-adaptive parameters
    try:
        print(f"    Running self-adaptive...")
        candidate, candidate_L = self_adaptive_optimize(best_p, n_iters=100)
        if candidate_L < best_L:
            best_L = candidate_L
            best_p = candidate.copy()
            print(f"    Self-adaptive improved: {candidate_L:.9f}")
    except Exception as e:
        print(f"    Self-adaptive failed: {e}")
    
    # Final intensive polish
    try:
        for seed in range(5):
            candidate, _, _ = polish.polish(best_p, seed=seed*12345,
                                           rounds=8, max_seconds=20,
                                           trust_start=0.015,
                                           regularization=5e-13)
            candidate_L = pg.side(candidate)
            if candidate_L < best_L:
                best_L = candidate_L
                best_p = candidate.copy()
    except:
        pass
    
    improvement = original_L - best_L
    
    if improvement > 1e-12:
        print(f"  → Final: {best_L:.9f} ★WIN! Δ={improvement:.2e}\n")
        return (n, best_p, best_L, improvement)
    else:
        print(f"  → Final: {best_L:.9f} (no improvement)\n")
        return None

def main():
    print("=" * 80)
    print("NEURAL EVOLUTION STRATEGY (NES) OPTIMIZER")
    print("=" * 80)
    print("CMA-ES, Self-Adaptive Parameters, Fitness Shaping")
    print("=" * 80 + "\n")
    
    submission_files = sorted(Path('output').glob('submission_22.*.csv'))
    if not submission_files:
        submission_files = [Path('output/submission_final.csv')]
    
    best_file = submission_files[0]
    print(f"Starting from: {best_file.name}\n")
    
    df = pd.read_csv(best_file)
    
    # Target medium puzzles where NES excels
    targets = list(range(80, 350))
    
    print(f"Targeting {len(targets)} puzzles (n=80-350)")
    print(f"NES works exceptionally well for medium-sized problems\n")
    
    wins = {}
    start_time = time.time()
    
    for n in targets:
        rows = df[df['n'] == n]
        if len(rows) == 0:
            continue
        
        p_base = rows[['x', 'y', 'angle']].values
        result = optimize_puzzle_nes((n, p_base))
        
        if result is not None:
            n, best_p, best_L, improvement = result
            wins[n] = best_p
    
    elapsed = time.time() - start_time
    
    print("\n" + "=" * 80)
    print(f"COMPLETE in {elapsed/60:.1f} minutes")
    print(f"Found {len(wins)} NES improvements")
    print("=" * 80)
    
    if wins:
        timestamp = int(time.time())
        wins_file = f"output/nes_wins_{len(wins)}_{timestamp}.npz"
        np.savez_compressed(wins_file, **{str(k): v for k, v in wins.items()})
        print(f"\nSaved: {wins_file}")
        
        df_new = df.copy()
        for n, packing in wins.items():
            df_new.loc[df_new['n'] == n, ['x', 'y', 'angle']] = packing
        
        from src.tools.reference_sources.official_metric import score
        new_score = score(df_new, 'id', 'n')
        
        sub_path = f"output/submission_nes_{new_score:.6f}.csv"
        df_new.to_csv(sub_path, index=False)
        
        print(f"\n✓ Score: {new_score:.12f}")
        print(f"  File: {sub_path}")

if __name__ == '__main__':
    main()
