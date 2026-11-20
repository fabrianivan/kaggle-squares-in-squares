#!/usr/bin/env python3
"""
TITAN OPTIMIZER - Ultra-focused on n=700-1000 (highest score impact)
These puzzles have the most weight due to 1/√n scaling
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'tools'))

import numpy as np
import pandas as pd
import packing_geometry as pg
import cpu_contact_polish as polish
import cpu_axis_reclosure as reclosure
import time

def titan_level_optimization(packing, puzzle_n):
    """Titan-level: 2000+ attempts on single high-value puzzle"""
    best_p = packing.copy()
    best_L = pg.side(best_p)
    
    print(f"\n{'='*60}")
    print(f"  TITAN attacking n={puzzle_n} (weight: {1/np.sqrt(puzzle_n):.6f})")
    print(f"  Starting L = {best_L:.9f}")
    print(f"{'='*60}")
    
    improvements = []
    
    # 2000 ultra-intensive attempts
    for attempt in range(2000):
        seed = attempt * 97531
        
        # Progress indicator
        if attempt % 100 == 0:
            print(f"  [{attempt:4d}/2000] Best so far: {best_L:.9f}")
        
        # Cycle through 10 different strategies
        strategy = attempt % 10
        
        try:
            if strategy == 0:
                # Ultra-precision polish (tightest possible)
                candidate, _, _ = polish.polish(best_p, seed=seed,
                                               rounds=20, max_seconds=90,
                                               trust_start=0.003 + 0.012*np.random.random(),
                                               regularization=10**(-16 + 2*np.random.random()))
            
            elif strategy == 1:
                # Maximum reclose range
                trust = 0.10 + 0.50 * np.random.random()
                tie = 0.10 + 0.45 * np.random.random()
                candidate, _, _ = reclosure.reclose(best_p, seed=seed,
                                                   trust=trust, tie=tie,
                                                   rounds=20, seconds=90)
            
            elif strategy == 2:
                # Four-stage cascade
                temp1, _, _ = polish.polish(best_p, seed=seed, rounds=5, max_seconds=20,
                                           trust_start=0.010, regularization=1e-12)
                temp2, _, _ = reclosure.reclose(temp1, seed=seed+1, trust=0.22, tie=0.22,
                                               rounds=5, seconds=20)
                temp3, _, _ = polish.polish(temp2, seed=seed+2, rounds=5, max_seconds=20,
                                           trust_start=0.018, regularization=7e-13)
                candidate, _, _ = reclosure.reclose(temp3, seed=seed+3, trust=0.25, tie=0.20,
                                                   rounds=5, seconds=20)
            
            elif strategy == 3:
                # Dense rotation sampling
                rotation_candidates = []
                for angle in np.linspace(0, np.pi, 16):
                    rotated = best_p.copy()
                    rotated[:, 2] += angle
                    try:
                        opt, _, _ = polish.polish(rotated, seed=seed, rounds=5, max_seconds=15,
                                                 trust_start=0.016, regularization=8e-13)
                        rotation_candidates.append(opt)
                    except:
                        pass
                
                if rotation_candidates:
                    best_rot = min(rotation_candidates, key=lambda p: pg.side(p))
                    candidate, _, _ = reclosure.reclose(best_rot, seed=seed,
                                                       trust=0.22, tie=0.22,
                                                       rounds=8, seconds=30)
                else:
                    candidate = best_p
            
            elif strategy == 4:
                # Gradient descent with momentum
                epsilon = 0.0005
                momentum = 0.0
                beta = 0.9
                
                for gd_iter in range(10):
                    gradient = np.zeros_like(best_p)
                    current_L = pg.side(best_p)
                    
                    # Compute gradient (sample)
                    indices = np.random.choice(len(best_p), min(15, len(best_p)), replace=False)
                    for i in indices:
                        for j in range(2):
                            perturbed = best_p.copy()
                            perturbed[i, j] += epsilon
                            try:
                                L_plus = pg.side(perturbed)
                                gradient[i, j] = (L_plus - current_L) / epsilon
                            except:
                                gradient[i, j] = 0
                    
                    # Momentum update
                    momentum = beta * momentum + (1 - beta) * gradient
                    lr = 0.02 * (1 - gd_iter / 10)
                    best_p = best_p - lr * momentum
                
                candidate, _, _ = polish.polish(best_p, seed=seed, rounds=8, max_seconds=30,
                                               trust_start=0.015, regularization=1e-12)
            
            elif strategy == 5:
                # Adaptive temperature annealing
                T = 2.0 * np.exp(-attempt / 400)
                noise = T * 0.03 * np.random.randn(*best_p.shape)
                
                perturbed = best_p + noise
                candidate, _, _ = reclosure.reclose(perturbed, seed=seed,
                                                   trust=0.15 + 0.30*T,
                                                   tie=0.15 + 0.25*T,
                                                   rounds=12, seconds=50)
            
            elif strategy == 6:
                # Population ensemble (mini genetic algorithm)
                population = [best_p]
                for _ in range(7):
                    noise = 0.02 * np.random.randn(*best_p.shape)
                    perturbed = best_p + noise
                    try:
                        opt, _, _ = polish.polish(perturbed, seed=seed+_, rounds=4, max_seconds=12,
                                                 trust_start=0.015, regularization=1e-12)
                        population.append(opt)
                    except:
                        pass
                
                # Crossover and mutate
                if len(population) >= 2:
                    parent1, parent2 = np.random.choice(population, 2, replace=False)
                    alpha = 0.3 + 0.4 * np.random.random()
                    child = alpha * parent1 + (1 - alpha) * parent2
                    candidate, _, _ = reclosure.reclose(child, seed=seed,
                                                       trust=0.22, tie=0.22,
                                                       rounds=8, seconds=30)
                else:
                    candidate = best_p
            
            elif strategy == 7:
                # Multi-scale optimization
                for scale in [0.05, 0.02, 0.01, 0.005]:
                    gradient = np.zeros_like(best_p)
                    current_L = pg.side(best_p)
                    
                    epsilon = scale * 0.01
                    sample_size = min(20, len(best_p))
                    indices = np.random.choice(len(best_p), sample_size, replace=False)
                    
                    for i in indices:
                        for j in range(2):
                            perturbed = best_p.copy()
                            perturbed[i, j] += epsilon
                            try:
                                L_plus = pg.side(perturbed)
                                gradient[i, j] = (L_plus - current_L) / epsilon
                            except:
                                gradient[i, j] = 0
                    
                    grad_norm = np.linalg.norm(gradient)
                    if grad_norm > 3.0:
                        gradient = gradient * (3.0 / grad_norm)
                    
                    best_p = best_p - scale * gradient
                
                candidate, _, _ = polish.polish(best_p, seed=seed, rounds=10, max_seconds=40,
                                               trust_start=0.015, regularization=1e-12)
            
            elif strategy == 8:
                # Extreme parameter sweep
                best_sweep = best_p
                best_sweep_L = best_L
                
                for trust in [0.008, 0.012, 0.016, 0.020, 0.025]:
                    for reg_exp in [-14, -13, -12]:
                        try:
                            sweep, _, _ = polish.polish(best_p, seed=seed,
                                                       rounds=8, max_seconds=25,
                                                       trust_start=trust,
                                                       regularization=10**reg_exp)
                            sweep_L = pg.side(sweep)
                            if sweep_L < best_sweep_L:
                                best_sweep_L = sweep_L
                                best_sweep = sweep
                        except:
                            pass
                
                candidate = best_sweep
            
            else:
                # Quantum-inspired superposition
                quantum_states = []
                for q_seed in range(10):
                    try:
                        if q_seed % 2 == 0:
                            state, _, _ = polish.polish(best_p, seed=seed+q_seed,
                                                       rounds=5, max_seconds=15,
                                                       trust_start=0.015,
                                                       regularization=1e-12)
                        else:
                            state, _, _ = reclosure.reclose(best_p, seed=seed+q_seed,
                                                           trust=0.22, tie=0.22,
                                                           rounds=5, seconds=15)
                        quantum_states.append(state)
                    except:
                        pass
                
                if quantum_states:
                    # Interference pattern (weighted average)
                    weights = np.array([1/(i+1) for i in range(len(quantum_states))])
                    weights /= weights.sum()
                    
                    superposition = np.zeros_like(best_p)
                    for state, weight in zip(quantum_states, weights):
                        superposition += weight * state
                    
                    candidate, _, _ = polish.polish(superposition, seed=seed,
                                                   rounds=10, max_seconds=40,
                                                   trust_start=0.015,
                                                   regularization=1e-12)
                else:
                    candidate = best_p
            
            candidate_L = pg.side(candidate)
            if candidate_L < best_L - 1e-14:
                improvement = best_L - candidate_L
                improvements.append(improvement)
                best_L = candidate_L
                best_p = candidate.copy()
                print(f"    → NEW BEST: {best_L:.9f} (Δ={improvement:.2e})")
        
        except Exception as e:
            pass
    
    print(f"\n  Final L = {best_L:.9f}")
    print(f"  Total improvements: {len(improvements)}")
    if improvements:
        print(f"  Cumulative gain: {sum(improvements):.6f}")
    print(f"{'='*60}\n")
    
    return best_p, best_L

def main():
    print("=" * 80)
    print("⚡ TITAN OPTIMIZER - MAXIMUM IMPACT PUZZLES ⚡")
    print("=" * 80)
    print("2000 attempts per puzzle | 10 strategies | n=700-1000 focus")
    print("=" * 80)
    
    submission_files = sorted(Path('output').glob('submission_22.*.csv'))
    best_file = submission_files[0]
    print(f"\nFrom: {best_file.name}\n")
    
    df = pd.read_csv(best_file)
    
    # Focus on absolute highest impact (n >= 700)
    targets = list(range(700, 1001))
    print(f"Targeting {len(targets)} TITAN puzzles (n≥700)")
    print(f"These have maximum score impact due to 1/√n weighting\n")
    
    wins = {}
    start_time = time.time()
    
    for n in targets:
        rows = df[df['n'] == n]
        if len(rows) == 0:
            continue
        
        p_base = rows[['x', 'y', 'angle']].values
        original_L = pg.side(p_base)
        
        best_p, best_L = titan_level_optimization(p_base, n)
        
        improvement = original_L - best_L
        if improvement > 1e-12:
            wins[n] = best_p
    
    elapsed = time.time() - start_time
    
    print("=" * 80)
    print(f"⚡ TITAN COMPLETE in {elapsed/60:.1f} minutes")
    print(f"Found {len(wins)} TITAN improvements")
    print("=" * 80)
    
    if wins:
        timestamp = int(time.time())
        np.savez_compressed(f"output/titan_wins_{len(wins)}_{timestamp}.npz",
                           **{str(k): v for k, v in wins.items()})
        
        df_new = df.copy()
        for n, pack in wins.items():
            df_new.loc[df_new['n'] == n, ['x', 'y', 'angle']] = pack
        
        total = sum(pg.side(df_new[df_new['n']==n][['x','y','angle']].values)/np.sqrt(n)-1 
                   for n in range(1,1001) if len(df_new[df_new['n']==n])>0)
        
        df_new.to_csv(f"output/submission_TITAN_{total:.6f}.csv", index=False)
        print(f"\n✓ TITAN SCORE: {total:.12f}")

if __name__ == '__main__':
    main()
