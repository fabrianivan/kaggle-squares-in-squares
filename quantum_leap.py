#!/usr/bin/env python3
"""
QUANTUM LEAP - Next-generation optimizer from NEW BASELINE
Strategy: Extreme exploration with guided random walks
Starting from: 22.250922 (latest best)
Features: Simulated annealing + gradient descent hybrid
Runtime: ~3-4 hours
"""
import sys
import math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'tools'))

import pandas as pd
import numpy as np
import packing_geometry as pg
import cpu_contact_polish as polish
import cpu_axis_reclosure as reclosure

def compute_score(df):
    total = 0.0
    for n in range(1, 1001):
        p = df[df['n'] == n][['x', 'y', 'angle']].values
        if len(p) == n:
            L = pg.side(p)
            total += L / math.sqrt(n) - 1
    return total

def optimize_quantum():
    baseline = pd.read_csv('output/submission_22.250922.csv')
    current_score = compute_score(baseline)
    print(f"QUANTUM LEAP - Starting from NEW BASELINE {current_score:.6f}")
    
    best_df = baseline.copy()
    wins = 0
    
    # Target high-value puzzles
    target_puzzles = list(range(15, 401))
    
    for puzzle_n in target_puzzles:
        p = baseline[baseline['n'] == puzzle_n][['x', 'y', 'angle']].values
        if len(p) == 0 or len(p) != puzzle_n:
            continue
            
        current_side = pg.side(p)
        best_p = p.copy()
        best_side = current_side
        
        print(f"Puzzle {puzzle_n}: starting {current_side:.10f}", flush=True)
        
        # 110 quantum attempts with annealing
        for attempt in range(110):
            seed = 10000 + attempt * 41
            
            # Temperature schedule (high → low)
            temperature = 1.0 - (attempt / 110.0)
            
            # Strategy selection with temperature
            if temperature > 0.7:
                # High temp: Extreme exploration
                strategy = attempt % 5
            elif temperature > 0.4:
                # Medium temp: Guided search
                strategy = 5 + (attempt % 5)
            else:
                # Low temp: Precision refinement
                strategy = 10 + (attempt % 5)
            
            try:
                if strategy == 0:
                    # Ultra-random exploration
                    trust = np.random.uniform(0.01, 0.06) * (1 + temperature)
                    reg = 10 ** np.random.uniform(-14, -11)
                    candidate, _, _ = polish.polish(p, seed=seed, 
                                            rounds=np.random.randint(10, 18),
                                            max_seconds=np.random.randint(30, 50),
                                            trust_start=trust, regularization=reg)
                
                elif strategy == 1:
                    # Random reclosure with temperature
                    trust = np.random.uniform(0.3, 0.58) * (0.8 + temperature * 0.4)
                    tie = np.random.uniform(0.14, 0.26)
                    candidate, _, _ = reclosure.reclose(p, seed=seed,
                                                trust=trust, tie=tie,
                                                rounds=np.random.randint(7, 12),
                                                seconds=np.random.randint(30, 50))
                
                elif strategy == 2:
                    # Wild combo
                    temp1, _, _ = polish.polish(p, seed=seed, rounds=8, max_seconds=22,
                                       trust_start=np.random.uniform(0.03, 0.07),
                                       regularization=10**np.random.uniform(-12.5, -11))
                    candidate, _, _ = reclosure.reclose(temp1, seed=seed+1,
                                                trust=np.random.uniform(0.35, 0.5),
                                                tie=np.random.uniform(0.17, 0.23),
                                                rounds=7, seconds=25)
                
                elif strategy == 3:
                    # Extreme perturbation
                    temp, _, _ = reclosure.reclose(p, seed=seed, trust=0.55,
                                            tie=0.15, rounds=10, seconds=35)
                    candidate, _, _ = polish.polish(temp, seed=seed+1, rounds=14, max_seconds=38,
                                            trust_start=0.018, regularization=5e-14)
                
                elif strategy == 4:
                    # Random multi-pass
                    temp1, _, _ = polish.polish(p, seed=seed, rounds=6, max_seconds=15,
                                       trust_start=np.random.uniform(0.05, 0.08),
                                       regularization=10**np.random.uniform(-12, -11))
                    temp2, _, _ = reclosure.reclose(temp1, seed=seed+1,
                                            trust=np.random.uniform(0.3, 0.45),
                                            tie=np.random.uniform(0.19, 0.24),
                                            rounds=5, seconds=15)
                    candidate, _, _ = polish.polish(temp2, seed=seed+2, rounds=6, max_seconds=15,
                                            trust_start=np.random.uniform(0.02, 0.04),
                                            regularization=10**np.random.uniform(-13, -12))
                
                elif strategy == 5:
                    # Guided by temperature
                    trust_mult = 0.5 + temperature * 0.5
                    candidate, _, _ = polish.polish(p, seed=seed, rounds=12, max_seconds=35,
                                            trust_start=0.025 * trust_mult,
                                            regularization=3e-13 / trust_mult)
                
                elif strategy == 6:
                    # Temperature annealing combo
                    temp1, _, _ = polish.polish(p, seed=seed, rounds=int(10*(1+temperature)), 
                                       max_seconds=int(30*(1+temperature*0.5)),
                                       trust_start=0.04*(0.5+temperature),
                                       regularization=1e-12*(0.3+temperature))
                    candidate, _, _ = reclosure.reclose(temp1, seed=seed+1,
                                                trust=0.4*(0.8+temperature*0.5),
                                                tie=0.2,
                                                rounds=int(7*(1+temperature*0.3)),
                                                seconds=int(30*(1+temperature*0.4)))
                
                elif strategy == 7:
                    # Balanced with noise
                    noise = np.random.normal(0, temperature * 0.05)
                    candidate, _, _ = polish.polish(p, seed=seed, rounds=13, max_seconds=36,
                                            trust_start=np.clip(0.022 + noise, 0.015, 0.05),
                                            regularization=np.clip(2e-13 * (1+noise), 1e-14, 1e-11))
                
                elif strategy == 8:
                    # Adaptive exploration
                    temp1, _, _ = reclosure.reclose(p, seed=seed,
                                            trust=0.42 + temperature*0.15,
                                            tie=0.19 - temperature*0.03,
                                            rounds=8, seconds=32)
                    temp2, _, _ = polish.polish(temp1, seed=seed+1, rounds=10, max_seconds=28,
                                       trust_start=0.028*(0.6+temperature*0.7),
                                       regularization=5e-13*(0.4+temperature))
                    candidate, _, _ = reclosure.reclose(temp2, seed=seed+2,
                                                trust=0.35*(0.9+temperature*0.3),
                                                tie=0.21,
                                                rounds=6, seconds=25)
                
                elif strategy == 9:
                    # Quantum fluctuation
                    if np.random.random() < temperature:
                        # Big jump
                        candidate, _, _ = reclosure.reclose(p, seed=seed, trust=0.56,
                                                    tie=0.145, rounds=12, seconds=45)
                    else:
                        # Small refinement
                        candidate, _, _ = polish.polish(p, seed=seed, rounds=16, max_seconds=42,
                                                trust_start=0.016, regularization=8e-14)
                
                elif strategy == 10:
                    # Low temp precision
                    candidate, _, _ = polish.polish(p, seed=seed, rounds=18, max_seconds=48,
                                            trust_start=0.013, regularization=2e-14)
                
                elif strategy == 11:
                    # Low temp tight reclosure
                    candidate, _, _ = reclosure.reclose(p, seed=seed, trust=0.52,
                                                tie=0.16, rounds=11, seconds=45)
                
                elif strategy == 12:
                    # Low temp quad combo
                    temp1, _, _ = polish.polish(p, seed=seed, rounds=6, max_seconds=14,
                                       trust_start=0.045, regularization=7e-12)
                    temp2, _, _ = reclosure.reclose(temp1, seed=seed+1, trust=0.38,
                                            tie=0.21, rounds=5, seconds=14)
                    temp3, _, _ = polish.polish(temp2, seed=seed+2, rounds=7, max_seconds=16,
                                        trust_start=0.025, regularization=4e-12)
                    candidate, _, _ = reclosure.reclose(temp3, seed=seed+3, trust=0.33,
                                                tie=0.22, rounds=5, seconds=14)
                
                elif strategy == 13:
                    # Low temp alternating
                    temp1, _, _ = reclosure.reclose(p, seed=seed, trust=0.46, tie=0.18,
                                            rounds=7, seconds=24)
                    temp2, _, _ = polish.polish(temp1, seed=seed+1, rounds=9, max_seconds=24,
                                       trust_start=0.026, regularization=6e-12)
                    temp3, _, _ = reclosure.reclose(temp2, seed=seed+2, trust=0.39, tie=0.20,
                                            rounds=6, seconds=24)
                    candidate, _, _ = polish.polish(temp3, seed=seed+3, rounds=9, max_seconds=24,
                                            trust_start=0.019, regularization=3e-13)
                
                else:  # strategy == 14
                    # Low temp extreme precision
                    candidate, _, _ = polish.polish(p, seed=seed, rounds=22, max_seconds=55,
                                            trust_start=0.01, regularization=1.5e-14)
                
                cand_side = pg.side(candidate)
                
                if cand_side < best_side - 1e-11:
                    improvement = current_side - cand_side
                    best_side = cand_side
                    best_p = candidate.copy()
                    print(f"  → WIN attempt {attempt} [T={temperature:.2f}, S={strategy}]: {cand_side:.10f} (Δ {improvement:.2e})", flush=True)
            
            except Exception as e:
                continue
        
        if best_side < current_side - 1e-11:
            mask = best_df['n'] == puzzle_n
            best_df.loc[mask, ['x', 'y', 'angle']] = best_p
            wins += 1
            print(f"Puzzle {puzzle_n}: IMPROVED {current_side:.10f} → {best_side:.10f}", flush=True)
    
    if wins > 0:
        new_score = compute_score(best_df)
        improvement = current_score - new_score
        print(f"\n{'='*60}")
        print(f"QUANTUM LEAP COMPLETE: {wins} puzzles improved")
        print(f"Score: {current_score:.6f} → {new_score:.6f}")
        print(f"Improvement: {improvement:.6f}")
        print(f"{'='*60}")
        
        output_path = f'output/submission_{new_score:.6f}.csv'
        best_df.to_csv(output_path, index=False)
        print(f"Saved: {output_path}")
    else:
        print(f"\nNo improvements found")

if __name__ == '__main__':
    optimize_quantum()
