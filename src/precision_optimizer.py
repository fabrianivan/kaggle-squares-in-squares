#!/usr/bin/env python3
"""
PRECISION OPTIMIZER - Ultra-precise optimization on medium puzzles
Target: Puzzles n=200-400 with maximum precision
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

def precision_optimize(n, p_base, num_seeds=25):
    """High-precision optimization with tight tolerances"""
    try:
        L0 = pg.side(p_base)
        best_L = L0
        best_p = p_base.copy()
        
        for seed in range(num_seeds):
            # Vary parameters systematically
            trust_values = np.linspace(0.25, 0.65, 5)
            tie_values = np.linspace(0.12, 0.32, 5)
            
            for trust in trust_values:
                for tie in tie_values:
                    try:
                        # Precise reclosure
                        q, _, _ = reclosure.reclose(
                            p_base if seed < 5 else best_p,
                            seed=seed*211,
                            trust=trust,
                            tie=tie,
                            rounds=35,
                            seconds=3.5
                        )
                        if pg.side(q) < best_L - 5e-13:
                            best_L = pg.side(q)
                            best_p = q.copy()
                    except:
                        pass
            
            # High-precision polish
            for trust_start in [0.01, 0.015, 0.02, 0.025, 0.03]:
                try:
                    q, _, _ = polish.polish(
                        best_p,
                        seed=seed*103,
                        rounds=70,
                        max_seconds=3.5,
                        trust_start=trust_start,
                        regularization=0.0
                    )
                    q = pg.repair(q, clearance=3e-10)
                    if q is not None and pg.side(q) < best_L - 5e-13:
                        best_L = pg.side(q)
                        best_p = q.copy()
                except:
                    pass
        
        # Ultra-precise final repair
        best_p = pg.repair(best_p, clearance=1e-10)
        if best_p is not None:
            best_L = pg.side(best_p)
            if best_L < L0 - 5e-13:
                return (n, L0, best_L, best_p)
    
    except Exception as e:
        pass
    
    return None

def main():
    print("=" * 80)
    print("PRECISION OPTIMIZER")
    print("Target: n=200-400 with ultra-high precision")
    print("=" * 80)
    
    baseline_path = 'output/submission_22.251122.csv'
    print(f"\nLoading: {baseline_path}")
    df = pd.read_csv(baseline_path)
    
    # Target medium-sized puzzles
    puzzles = []
    for n in range(200, 401):
        g = df[df['n'] == n].sort_values('square_id')
        if len(g) > 0:
            p = g[['x', 'y', 'angle']].to_numpy(float)
            L = pg.side(p)
            waste = L / np.sqrt(n) - 1
            puzzles.append((waste, n, p))
    
    puzzles.sort(reverse=True)
    targets = puzzles[:80]  # Top 80
    
    print(f"\nTargeting top 80 medium puzzles (n=200-400)")
    print(f"Top 10 by waste: {[n for _, n, _ in targets[:10]]}")
    print(f"\nRunning precision optimization (25 seeds × systematic parameter sweep)\n")
    
    wins = []
    start_time = time.time()
    
    for i, (waste, n, p) in enumerate(targets):
        result = precision_optimize(n, p, num_seeds=25)
        
        if result is not None:
            n, L0, L_best, p_best = result
            gain = L0 - L_best
            wins.append(result)
            print(f"✓ WIN #{len(wins):3d} - n={n:4d}: {L0:.15f} -> {L_best:.15f} (gain={gain:.15f})")
        
        if (i + 1) % 10 == 0:
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            remaining = (len(targets) - i - 1) / rate if rate > 0 else 0
            print(f"  Progress: {i+1}/{len(targets)} - {len(wins)} wins - "
                  f"{elapsed/60:.1f}m elapsed, ~{remaining/60:.1f}m remaining")
    
    print(f"\n{'=' * 80}")
    print(f"PRECISION OPTIMIZATION COMPLETE: {len(wins)} improvements")
    print(f"Time: {(time.time() - start_time)/60:.1f} minutes")
    
    if wins:
        total_gain = sum(L0 - L_best for n, L0, L_best, p in wins)
        print(f"Total gain: {total_gain:.15f}")
        
        patch_data = {str(n): p for n, L0, L_best, p in wins}
        np.savez('output/precision_wins.npz', **patch_data)
        
        summary = {'wins': len(wins), 'total_gain': float(total_gain)}
        with open('output/precision_summary.json', 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"Saved: output/precision_wins.npz")
    else:
        print("No improvements found")

if __name__ == '__main__':
    main()
