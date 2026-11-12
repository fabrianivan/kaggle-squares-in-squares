#!/usr/bin/env python3
"""
ALL PUZZLES SWEEP - Optimize EVERY puzzle with moderate intensity
Coverage over depth
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import json

sys.path.insert(0, str(Path(__file__).parent / 'tools'))
import packing_geometry as pg
import cpu_axis_reclosure as reclosure
import cpu_contact_polish as polish

def quick_deep_optimize(n, p_base, seeds=40):
    """Quick but reasonably deep optimization"""
    try:
        L0 = pg.side(p_base)
        best_L = L0
        best_p = p_base.copy()
        
        for seed in range(seeds):
            # Varied reclosure
            for trust in [0.25, 0.4, 0.55]:
                for tie in [0.15, 0.25]:
                    try:
                        q, _, _ = reclosure.reclose(best_p, seed=seed, trust=trust, tie=tie, rounds=25, seconds=2.5)
                        if pg.side(q) < best_L - 1e-11:
                            best_L = pg.side(q)
                            best_p = q.copy()
                    except:
                        pass
            
            # Polish
            try:
                q, _, _ = polish.polish(best_p, seed=seed, rounds=50, max_seconds=2.5, trust_start=0.02)
                q = pg.repair(q, clearance=1e-10)
                if q is not None and pg.side(q) < best_L - 1e-11:
                    best_L = pg.side(q)
                    best_p = q.copy()
            except:
                pass
        
        if best_L < L0 - 1e-11:
            return (n, L0, best_L, best_p)
    except:
        pass
    return None

def main():
    print("=" * 80)
    print("ALL PUZZLES SWEEP - Every single puzzle!")
    print("=" * 80)
    
    baseline_path = 'output/submission_22.251122.csv'
    df = pd.read_csv(baseline_path)
    
    print(f"\nOptimizing ALL 1000 puzzles with 40 seeds each\n")
    
    wins = []
    for n in range(1, 1001):
        g = df[df['n'] == n].sort_values('square_id')
        if len(g) == 0:
            continue
        
        p = g[['x', 'y', 'angle']].to_numpy(float)
        result = quick_deep_optimize(n, p, seeds=40)
        
        if result is not None:
            wins.append(result)
            print(f"✓ n={n:4d}: gain={result[1]-result[2]:.12e}")
        
        if n % 50 == 0:
            print(f"  Progress: {n}/1000 - {len(wins)} wins so far")
    
    print(f"\nAll puzzles sweep: {len(wins)} wins")
    if wins:
        np.savez('output/all_puzzles_wins.npz', **{str(n): p for n, _, _, p in wins})
        with open('output/all_puzzles_summary.json', 'w') as f:
            json.dump({'wins': len(wins), 'total_gain': float(sum(L0-L for n,L0,L,p in wins))}, f)

if __name__ == '__main__':
    main()
