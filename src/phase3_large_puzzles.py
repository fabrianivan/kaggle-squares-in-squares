import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'tools'))

import numpy as np
import pandas as pd
import packing_geometry as pg
import cpu_axis_reclosure as reclosure
import cpu_contact_polish as polish
from concurrent.futures import ProcessPoolExecutor
import math
import json

def optimize_large(args):
    n, p_base, seed = args
    L0 = pg.side(p_base)
    best_L = L0
    best_p = None
    
    # Extra intensive for large puzzles
    for seed_offset in range(80):
        s = seed + seed_offset * 100
        
        for trust in [0.25, 0.35, 0.45, 0.55]:
            try:
                q, _, _ = reclosure.reclose(p_base, seed=s, trust=trust, tie=trust*0.5, rounds=30, seconds=6.0)
                q, _, _ = polish.polish(q, seed=s+7, rounds=80, max_seconds=6.0, trust_start=0.015)
                q = pg.repair(q, clearance=1e-9)
                
                if q is not None:
                    L = pg.side(q)
                    if L < best_L - 1e-12:
                        best_L = L
                        best_p = q.copy()
            except:
                pass
    
    if best_p is not None and best_L < L0 - 1e-12:
        gain = (L0 - best_L) / math.sqrt(n)
        return (n, L0, best_L, best_p, gain)
    return None

def main():
    import sys
    baseline = sys.argv[1] if len(sys.argv) > 1 else 'output/submission_final.csv'
    
    print(f"Loading {baseline}...")
    df = pd.read_csv(baseline)
    
    targets = []
    for n in range(500, 1001):
        g = df[df['n'] == n].sort_values('square_id')
        if len(g) > 0:
            p = g[['x', 'y', 'angle']].to_numpy(float)
            targets.append((n, p, n * 42))
    
    print(f"Optimizing {len(targets)} large puzzles (n >= 500)...")
    
    wins = []
    completed = 0
    
    with ProcessPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(optimize_large, args) for args in targets]
        
        for future in futures:
            completed += 1
            result = future.result()
            if result:
                n, L0, L_best, p_best, gain = result
                wins.append(result)
                print(f"  ✓ n={n}: gain={gain:.12f}")
            
            if completed % 25 == 0:
                print(f"  Progress: {completed}/{len(targets)}, Wins: {len(wins)}")
    
    print(f"\nTotal wins: {len(wins)}")
    
    if wins:
        patch_data = {str(n): p for n, L0, L_best, p, gain in wins}
        np.savez('output/phase3_wins.npz', **patch_data)
        print("Saved to output/phase3_wins.npz")

if __name__ == '__main__':
    main()
