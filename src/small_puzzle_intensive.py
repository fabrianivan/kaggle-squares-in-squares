#!/usr/bin/env python3
"""
SMALL PUZZLE INTENSIVE OPTIMIZER
Even small improvements on n=50-150 add up!
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import time
import json

sys.path.insert(0, str(Path(__file__).parent / 'tools'))
import packing_geometry as pg
import cpu_axis_reclosure as reclosure
import cpu_contact_polish as polish

def intensive_small_optimize(n, p_base, num_seeds=60):
    """Intensive optimization for small-medium puzzles"""
    try:
        L0 = pg.side(p_base)
        best_L = L0
        best_p = p_base.copy()
        
        for seed in range(num_seeds):
            # Very aggressive for small puzzles
            for trust in [0.2, 0.35, 0.5, 0.65, 0.8]:
                for tie in [0.1, 0.18, 0.26, 0.35]:
                    try:
                        q, _, _ = reclosure.reclose(best_p, seed=seed*83, trust=trust, tie=tie, rounds=35, seconds=4.0)
                        if pg.side(q) < best_L - 1e-12:
                            best_L = pg.side(q)
                            best_p = q.copy()
                    except:
                        pass
            
            # Intensive polish
            for trust_start in np.linspace(0.01, 0.04, 7):
                try:
                    q, _, _ = polish.polish(best_p, seed=seed*67, rounds=90, max_seconds=4.5, trust_start=trust_start)
                    q = pg.repair(q, clearance=5e-11)
                    if q is not None and pg.side(q) < best_L - 1e-12:
                        best_L = pg.side(q)
                        best_p = q.copy()
                except:
                    pass
        
        best_p = pg.repair(best_p, clearance=1e-11)
        if best_p is not None and pg.side(best_p) < L0 - 1e-12:
            return (n, L0, pg.side(best_p), best_p)
    except:
        pass
    return None

def main():
    print("=" * 80)
    print("SMALL PUZZLE INTENSIVE OPTIMIZER (n=50-150)")
    print("=" * 80)
    
    baseline_path = 'output/submission_22.251122.csv'
    print(f"\nLoading: {baseline_path}")
    df = pd.read_csv(baseline_path)
    
    puzzles = []
    for n in range(50, 151):
        g = df[df['n'] == n].sort_values('square_id')
        if len(g) > 0:
            p = g[['x', 'y', 'angle']].to_numpy(float)
            L = pg.side(p)
            waste = L / np.sqrt(n) - 1
            puzzles.append((waste, n, p))
    
    puzzles.sort(reverse=True)
    
    print(f"\nTargeting {len(puzzles)} small-medium puzzles")
    print(f"Top 10 by waste: {[n for _, n, _ in puzzles[:10]]}\n")
    
    wins = []
    start_time = time.time()
    
    for i, (waste, n, p) in enumerate(puzzles):
        result = intensive_small_optimize(n, p, num_seeds=60)
        if result is not None:
            n, L0, L_best, p_best = result
            wins.append(result)
            print(f"✓ WIN #{len(wins):2d} - n={n:3d}: {L0:.15f} -> {L_best:.15f} (gain={L0-L_best:.15e})")
        
        if (i + 1) % 20 == 0:
            elapsed = time.time() - start_time
            print(f"  Progress: {i+1}/{len(puzzles)} - {len(wins)} wins - {elapsed/60:.1f}m")
    
    print(f"\n{'=' * 80}")
    print(f"COMPLETE: {len(wins)} improvements, Time: {(time.time()-start_time)/60:.1f}m")
    
    if wins:
        total_gain = sum(L0 - L_best for n, L0, L_best, p in wins)
        print(f"Total gain: {total_gain:.15f}")
        
        np.savez('output/small_puzzle_wins.npz', **{str(n): p for n, _, _, p in wins})
        with open('output/small_puzzle_summary.json', 'w') as f:
            json.dump({'wins': len(wins), 'total_gain': float(total_gain)}, f, indent=2)
        print(f"Saved: output/small_puzzle_wins.npz")

if __name__ == '__main__':
    main()
