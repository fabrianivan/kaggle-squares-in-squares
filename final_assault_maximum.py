#!/usr/bin/env python3
"""
FINAL ASSAULT - Maximum effort to reach 22.11
All optimizations, maximum attempts, best parameters
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

def maximum_effort_single(args):
    """Maximum optimization effort on single puzzle"""
    n, p_base = args
    
    original_L = pg.side(p_base)
    best_p = p_base.copy()
    best_L = original_L
    
    # 500 attempts with best methods
    for attempt in range(500):
        seed = attempt * 13579
        
        # Cycle through proven methods
        method = attempt % 5
        
        try:
            if method == 0:
                # Ultra-tight polish
                candidate, _, _ = polish.polish(best_p, seed=seed,
                                               rounds=12, max_seconds=40,
                                               trust_start=0.008 + 0.02*np.random.random(),
                                               regularization=10**(-14 + 2*np.random.random()))
            elif method == 1:
                # Aggressive reclose
                trust = 0.15 + 0.4 * np.random.random()
                tie = 0.15 + 0.35 * np.random.random()
                candidate, _, _ = reclosure.reclose(best_p, seed=seed,
                                                   trust=trust, tie=tie,
                                                   rounds=12, seconds=40)
            elif method == 2:
                # Two-stage: polish then reclose
                temp, _, _ = polish.polish(best_p, seed=seed,
                                          rounds=6, max_seconds=20,
                                          trust_start=0.015,
                                          regularization=1e-12)
                candidate, _, _ = reclosure.reclose(temp, seed=seed+1,
                                                   trust=0.22, tie=0.22,
                                                   rounds=6, seconds=20)
            elif method == 3:
                # Rotation + optimize
                angle = np.random.uniform(0, np.pi/2)
                rotated = best_p.copy()
                rotated[:, 2] += angle
                candidate, _, _ = polish.polish(rotated, seed=seed,
                                               rounds=8, max_seconds=25,
                                               trust_start=0.018,
                                               regularization=7e-13)
            else:
                # Random exploration
                perturbed = best_p.copy()
                scale = 0.01 + 0.05 * np.random.random()
                perturbed[:, :2] += np.random.randn(*perturbed[:, :2].shape) * scale
                candidate, _, _ = reclosure.reclose(perturbed, seed=seed,
                                                   trust=0.2 + 0.25*np.random.random(),
                                                   tie=0.2 + 0.2*np.random.random(),
                                                   rounds=8, seconds=25)
            
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
    print("🚀 FINAL ASSAULT - MAXIMUM EFFORT 🚀")
    print("=" * 80)
    print("500 attempts per puzzle | All best methods | Parallel processing")
    print("=" * 80 + "\n")
    
    submission_files = sorted(Path('output').glob('submission_22.*.csv'))
    best_file = submission_files[0]
    print(f"From: {best_file.name}\n")
    
    df = pd.read_csv(best_file)
    
    # Target ALL puzzles with maximum effort
    targets = list(range(20, 1001))
    print(f"Targeting {len(targets)} puzzles")
    print(f"Using {mp.cpu_count()} parallel workers\n")
    
    # Prepare work
    work = []
    for n in targets:
        rows = df[df['n'] == n]
        if len(rows) > 0:
            work.append((n, rows[['x', 'y', 'angle']].values))
    
    print(f"Processing {len(work)} puzzles with 500 attempts each...\n")
    
    start_time = time.time()
    
    with mp.Pool(mp.cpu_count()) as pool:
        results = pool.map(maximum_effort_single, work)
    
    wins = {}
    for result in results:
        if result:
            n, best_p, best_L, improvement = result
            wins[n] = best_p
            print(f"✓ n={n:4d} Δ={improvement:.2e}")
    
    elapsed = time.time() - start_time
    
    print(f"\n{'='*80}")
    print(f"COMPLETE in {elapsed/60:.1f}min - {len(wins)} wins")
    print("=" * 80)
    
    if wins:
        timestamp = int(time.time())
        np.savez_compressed(f"output/final_assault_wins_{len(wins)}_{timestamp}.npz",
                           **{str(k): v for k, v in wins.items()})
        
        df_new = df.copy()
        for n, pack in wins.items():
            df_new.loc[df_new['n'] == n, ['x', 'y', 'angle']] = pack
        
        total = sum(pg.side(df_new[df_new['n']==n][['x','y','angle']].values)/np.sqrt(n)-1 
                   for n in range(1,1001) if len(df_new[df_new['n']==n])>0)
        
        df_new.to_csv(f"output/submission_final_assault_{total:.6f}.csv", index=False)
        print(f"\n✓ Score: {total:.12f}")

if __name__ == '__main__':
    main()
