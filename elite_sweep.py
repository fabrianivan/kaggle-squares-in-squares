#!/usr/bin/env python3
"""Elite Sweep - Ultra-intensive optimization across all puzzle sizes"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'tools'))

import numpy as np
import pandas as pd
import packing_geometry as pg
import cpu_axis_reclosure as reclosure
import cpu_contact_polish as polish
import time
import multiprocessing as mp

def optimize_single_puzzle(args):
    """Optimize a single puzzle with elite strategies"""
    n, p_base = args
    
    best_p = p_base.copy()
    best_L = pg.side(best_p)
    original_L = best_L
    
    # Elite strategy: 200 attempts with mixed methods
    for attempt in range(200):
        seed = np.random.randint(1000000)
        
        # Alternate between three approaches
        method = attempt % 3
        
        try:
            if method == 0:
                # Aggressive reclosure
                trust = 0.12 + 0.4 * np.random.random()
                tie = 0.12 + 0.35 * np.random.random()
                q, _, _ = reclosure.reclose(best_p, seed=seed, trust=trust, tie=tie,
                                           rounds=8, seconds=20)
            elif method == 1:
                # Tight contact polish
                trust_start = 0.005 + 0.03 * np.random.random()
                reg = 10 ** (-14 + 3 * np.random.random())
                q, _, _ = polish.polish(best_p, seed=seed, rounds=8, max_seconds=20,
                                       trust_start=trust_start, regularization=reg)
            else:
                # Medium polish
                trust_start = 0.02 + 0.04 * np.random.random()
                reg = 10 ** (-12 + 1 * np.random.random())
                q, _, _ = polish.polish(best_p, seed=seed, rounds=6, max_seconds=15,
                                       trust_start=trust_start, regularization=reg)
            
            if pg.side(q) < best_L - 1e-14:
                best_p = q
                best_L = pg.side(q)
        except:
            pass
    
    # Return if improved
    if best_L < original_L - 1e-12:
        improvement = original_L - best_L
        return (n, best_p, best_L, improvement)
    
    return None

def main():
    print("=" * 80)
    print("ELITE SWEEP - Ultra-intensive parallel optimization")
    print("=" * 80)
    
    df = pd.read_csv("output/submission_final.csv")
    
    # Target puzzles that are likely to yield improvements
    # Focus on challenging mid-to-large range
    targets = list(range(150, 800))
    
    print(f"Targeting {len(targets)} puzzles (n=150-800)")
    print(f"200 optimization attempts per puzzle")
    print(f"Using {mp.cpu_count()} parallel workers")
    print("=" * 80 + "\n")
    
    # Prepare work items
    work_items = []
    for n in targets:
        rows = df[df['n'] == n]
        if len(rows) > 0:
            p_base = rows[['x', 'y', 'angle']].values
            work_items.append((n, p_base))
    
    print(f"Processing {len(work_items)} puzzles...\n")
    
    start_time = time.time()
    
    # Parallel processing
    with mp.Pool(mp.cpu_count()) as pool:
        results = pool.map(optimize_single_puzzle, work_items)
    
    # Collect wins
    wins = {}
    for result in results:
        if result is not None:
            n, best_p, best_L, improvement = result
            wins[n] = best_p
            print(f"✓ n={n:4d}: Δ={improvement:.2e} → L={best_L:.12f}")
    
    elapsed = time.time() - start_time
    
    print("\n" + "=" * 80)
    print(f"COMPLETE in {elapsed/60:.1f} minutes")
    print(f"Found {len(wins)} improvements")
    print("=" * 80)
    
    if wins:
        # Save wins
        timestamp = int(time.time())
        wins_file = f"output/elite_wins_{len(wins)}_{timestamp}.npz"
        np.savez_compressed(wins_file, **{str(k): v for k, v in wins.items()})
        print(f"\nSaved: {wins_file}")
        
        # Create new submission
        df_new = df.copy()
        for n, packing in wins.items():
            df_new.loc[df_new['n'] == n, ['x', 'y', 'angle']] = packing
        
        # Score it
        from src.tools.reference_sources.official_metric import score
        new_score = score(df_new, 'id', 'n')
        
        sub_path = f"output/submission_elite_{new_score:.6f}.csv"
        df_new.to_csv(sub_path, index=False)
        
        print(f"\n✓ NEW SUBMISSION")
        print(f"  Score: {new_score:.12f}")
        print(f"  File: {sub_path}")
        print(f"  Wins: {len(wins)} puzzles")
        
        best_known = 22.250971
        if new_score < best_known:
            print(f"\n🎉 NEW RECORD!")
            print(f"   Improvement: {(best_known - new_score):.2e}")
    else:
        print("\nNo improvements found")

if __name__ == '__main__':
    main()
