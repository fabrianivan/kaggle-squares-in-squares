#!/usr/bin/env python3
"""
NUCLEAR OPTION - Most aggressive optimization possible
1000+ attempts per puzzle with all known best methods
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
import multiprocessing as mp

def nuclear_single_puzzle(args):
    """Nuclear-level optimization on single puzzle"""
    n, p_base = args
    
    original_L = pg.side(p_base)
    best_p = p_base.copy()
    best_L = original_L
    
    # 1000 attempts with absolute best methods
    for attempt in range(1000):
        seed = attempt * 24680
        
        method = attempt % 8
        
        try:
            if method == 0:
                # Ultra-precision polish
                candidate, _, _ = polish.polish(best_p, seed=seed,
                                               rounds=15, max_seconds=60,
                                               trust_start=0.005 + 0.015*np.random.random(),
                                               regularization=10**(-15 + 2*np.random.random()))
            
            elif method == 1:
                # Maximum aggressive reclose
                trust = 0.12 + 0.45 * np.random.random()
                tie = 0.12 + 0.4 * np.random.random()
                candidate, _, _ = reclosure.reclose(best_p, seed=seed,
                                                   trust=trust, tie=tie,
                                                   rounds=15, seconds=60)
            
            elif method == 2:
                # Triple stage optimization
                temp1, _, _ = polish.polish(best_p, seed=seed,
                                           rounds=5, max_seconds=20,
                                           trust_start=0.012,
                                           regularization=8e-13)
                temp2, _, _ = reclosure.reclose(temp1, seed=seed+1,
                                               trust=0.20, tie=0.23,
                                               rounds=5, seconds=20)
                candidate, _, _ = polish.polish(temp2, seed=seed+2,
                                               rounds=5, max_seconds=20,
                                               trust_start=0.016,
                                               regularization=6e-13)
            
            elif method == 3:
                # Multi-angle rotation search
                best_rotated = best_p
                best_rotated_L = best_L
                
                for angle in np.linspace(0, np.pi/2, 8):
                    rotated = best_p.copy()
                    rotated[:, 2] += angle
                    
                    try:
                        opt_rot, _, _ = polish.polish(rotated, seed=seed,
                                                     rounds=6, max_seconds=20,
                                                     trust_start=0.017,
                                                     regularization=7e-13)
                        opt_rot_L = pg.side(opt_rot)
                        
                        if opt_rot_L < best_rotated_L:
                            best_rotated_L = opt_rot_L
                            best_rotated = opt_rot
                    except:
                        pass
                
                candidate = best_rotated
            
            elif method == 4:
                # Gradient-inspired perturbation
                epsilon = 0.001
                gradient = np.zeros_like(best_p)
                current_L = pg.side(best_p)
                
                # Sample gradient
                for i in range(min(len(best_p), 10)):
                    for j in range(2):
                        perturbed = best_p.copy()
                        perturbed[i, j] += epsilon
                        try:
                            L_plus = pg.side(perturbed)
                            gradient[i, j] = (L_plus - current_L) / epsilon
                        except:
                            gradient[i, j] = 0
                
                # Move opposite to gradient
                lr = 0.01 + 0.04 * np.random.random()
                moved = best_p - lr * gradient
                
                candidate, _, _ = polish.polish(moved, seed=seed,
                                               rounds=8, max_seconds=30,
                                               trust_start=0.015,
                                               regularization=1e-12)
            
            elif method == 5:
                # Simulated annealing style
                T = 1.0 * np.exp(-attempt / 200)
                noise_scale = 0.02 * T
                
                perturbed = best_p.copy()
                perturbed[:, :2] += np.random.randn(*perturbed[:, :2].shape) * noise_scale
                
                candidate, _, _ = reclosure.reclose(perturbed, seed=seed,
                                                   trust=0.18 + 0.25*T,
                                                   tie=0.18 + 0.22*T,
                                                   rounds=10, seconds=40)
            
            elif method == 6:
                # Hybrid random exploration
                if np.random.random() < 0.5:
                    candidate, _, _ = polish.polish(best_p, seed=seed,
                                                   rounds=10 + np.random.randint(10),
                                                   max_seconds=50,
                                                   trust_start=0.008 + 0.022*np.random.random(),
                                                   regularization=10**(-14 + 3*np.random.random()))
                else:
                    candidate, _, _ = reclosure.reclose(best_p, seed=seed,
                                                       trust=0.1 + 0.5*np.random.random(),
                                                       tie=0.1 + 0.45*np.random.random(),
                                                       rounds=10 + np.random.randint(10),
                                                       seconds=50)
            
            else:
                # Ensemble of previous bests
                candidates_pool = [best_p]
                
                for mini_seed in range(5):
                    try:
                        mini_opt, _, _ = polish.polish(best_p, seed=seed+mini_seed,
                                                      rounds=4, max_seconds=15,
                                                      trust_start=0.015,
                                                      regularization=1e-12)
                        candidates_pool.append(mini_opt)
                    except:
                        pass
                
                # Average and optimize
                if len(candidates_pool) > 1:
                    avg_candidate = np.mean(candidates_pool, axis=0)
                    candidate, _, _ = reclosure.reclose(avg_candidate, seed=seed,
                                                       trust=0.22, tie=0.22,
                                                       rounds=8, seconds=30)
                else:
                    candidate = best_p
            
            candidate_L = pg.side(candidate)
            if candidate_L < best_L - 1e-14:
                best_L = candidate_L
                best_p = candidate.copy()
        
        except:
            pass
    
    improvement = original_L - best_L
    
    if improvement > 1e-12:
        return (n, best_p, best_L, improvement)
    return None

def main():
    print("=" * 80)
    print("☢️  NUCLEAR OPTION - MAXIMUM POSSIBLE EFFORT ☢️")
    print("=" * 80)
    print("1000 attempts/puzzle | 8 methods | Gradient+SA+Ensemble | Parallel")
    print("=" * 80 + "\n")
    
    submission_files = sorted(Path('output').glob('submission_22.*.csv'))
    best_file = submission_files[0]
    print(f"From: {best_file.name}\n")
    
    df = pd.read_csv(best_file)
    
    # Target high-impact puzzles (large n has bigger effect on score)
    targets = list(range(200, 1001))
    print(f"Targeting {len(targets)} HIGH-IMPACT puzzles (n≥200)")
    print(f"Using {mp.cpu_count()} parallel workers")
    print(f"Total attempts: {len(targets)} × 1000 = {len(targets)*1000:,}\n")
    
    work = []
    for n in targets:
        rows = df[df['n'] == n]
        if len(rows) > 0:
            work.append((n, rows[['x', 'y', 'angle']].values))
    
    print(f"Processing {len(work)} puzzles...\n")
    
    start_time = time.time()
    
    with mp.Pool(mp.cpu_count()) as pool:
        results = pool.map(nuclear_single_puzzle, work)
    
    wins = {}
    total_improvement = 0.0
    
    for result in results:
        if result:
            n, best_p, best_L, improvement = result
            wins[n] = best_p
            total_improvement += improvement
            print(f"✓ n={n:4d} Δ={improvement:.2e}")
    
    elapsed = time.time() - start_time
    
    print(f"\n{'='*80}")
    print(f"☢️  NUCLEAR COMPLETE in {elapsed/60:.1f}min")
    print(f"Found {len(wins)} improvements")
    print(f"Estimated score improvement: {total_improvement:.9f}")
    print("=" * 80)
    
    if wins:
        timestamp = int(time.time())
        np.savez_compressed(f"output/nuclear_wins_{len(wins)}_{timestamp}.npz",
                           **{str(k): v for k, v in wins.items()})
        
        df_new = df.copy()
        for n, pack in wins.items():
            df_new.loc[df_new['n'] == n, ['x', 'y', 'angle']] = pack
        
        total = sum(pg.side(df_new[df_new['n']==n][['x','y','angle']].values)/np.sqrt(n)-1 
                   for n in range(1,1001) if len(df_new[df_new['n']==n])>0)
        
        df_new.to_csv(f"output/submission_NUCLEAR_{total:.6f}.csv", index=False)
        print(f"\n✓ NEW SCORE: {total:.12f}")
        print(f"  File: output/submission_NUCLEAR_{total:.6f}.csv")

if __name__ == '__main__':
    main()
